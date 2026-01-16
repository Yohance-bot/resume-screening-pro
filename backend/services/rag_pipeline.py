import os
import uuid
from typing import List, Dict
from docx import Document
from groq import Groq
from services.pdf_extractor import extract_text_from_pdf
from services.groq_parser import parse_resume_with_groq, validate_parsed_data
from services.local_storage import LocalStorageManager
from services.vector_db import VectorDatabase
from services.embeddings import EmbeddingGenerator
from models import db, Candidate
from models.resume_schema import ResumeData
import re

def extract_experience_from_summary(parsed_data) -> float:
    """
    Extract total experience from experience_summary or professional_summary.
    Handles formats like:
    - "9+ years" → 9.0
    - "6 years and 8 months" → 6.67
    - "6.5 years" → 6.5
    - "2+ years in CFD/CAE" → 2.0
    """
    summary = ""
    
    # Handle both dict and object
    if isinstance(parsed_data, dict):
        summary = parsed_data.get("experience_summary") or parsed_data.get("professional_summary") or ""
    else:
        summary = getattr(parsed_data, "experience_summary", "") or getattr(parsed_data, "professional_summary", "") or ""
    
    if not summary:
        return 0.0
    
    # Pattern 1: "X+ years" or "X years"
    match = re.search(r'(\d+\.?\d*)\+?\s*years?', summary, re.IGNORECASE)
    if match:
        years = float(match.group(1))
        
        # Pattern 2: Look for additional months (e.g., "6 years 8 months" or "6 years and 8 months")
        months_match = re.search(r'(\d+)\s*months?', summary, re.IGNORECASE)
        if months_match:
            months = float(months_match.group(1))
            years += months / 12.0
        
        return round(years, 2)
    
    return 0.0


def calculate_experience_from_jobs(work_experiences: list) -> float:
    """Calculate total experience from work_experiences list"""
    if not work_experiences:
        return 0.0
    
    total_months = 0
    for job in work_experiences:
        if isinstance(job, dict):
            duration = job.get("duration_months") or 0
        else:
            duration = getattr(job, "duration_months", 0) or 0
        total_months += duration
    
    return round(total_months / 12.0, 2)


def extract_text_from_docx(path: str) -> str:
    doc = Document(path)
    parts = []
    for para in doc.paragraphs:
        if para.text:
            parts.append(para.text)
    return "\n".join(parts)


def extract_resume_text(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return extract_text_from_pdf(path)
    elif ext == ".docx":
        return extract_text_from_docx(path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def _extract_email(resume_text: str) -> str:
    match = re.search(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b", resume_text)
    return match.group(0) if match else ""


def _extract_phone(resume_text: str) -> str:
    # Very tolerant phone capture; keeps separators and optional country code.
    match = re.search(
        r"(?:(?:\+\d{1,3})[\s-]?)?(?:\(?\d{3,5}\)?[\s-]?)?\d{3,5}[\s-]?\d{4,5}",
        resume_text,
    )
    if not match:
        return ""
    phone = match.group(0).strip()
    return phone


def _extract_skills_from_text(resume_text: str) -> List[str]:
    """Lightweight deterministic skill extraction from a predefined list.

    Note: This intentionally mirrors the existing predefined skill list logic used elsewhere
    (e.g., advanced fallback extraction from raw text) to avoid introducing new behavior.
    """
    common_skills = [
        "Python", "SQL", "Java", "JavaScript", "React", "Node.js",
        "AWS", "Azure", "GCP", "Docker", "Kubernetes",
        "Spark", "Hadoop", "Kafka", "Airflow", "Databricks",
        "TensorFlow", "PyTorch", "Scikit-learn",
        "Pandas", "NumPy", "Matplotlib", "Tableau", "Power BI",
        "MongoDB", "PostgreSQL", "MySQL", "Redis",
        "Flask", "FastAPI", "Django", "Spring Boot",
        "R", "RStudio", "Linux", "Bash", "Shell", "Perl",
        "HTML", "CSS", "PHP",
        "Bioinformatics", "Metagenomics", "Microbiome",
        "RNA-seq", "HISAT2", "BWA", "FreeBayes", "FastQC", "Bowtie",
        "BLAST", "Uniprot", "Primer3", "Clustal Omega", "MEGA",
        "MetaPhlAn", "HUMAnN", "MG-RAST", "MGNify", "ImageJ",
    ]

    text_lower = resume_text.lower()
    found: Dict[str, str] = {}
    for skill in common_skills:
        if skill.lower() in text_lower:
            found.setdefault(skill.lower(), skill)
    return list(found.values())


def _infer_primary_role_from_text(resume_text: str) -> str:
    """Best-effort primary role inference without an LLM.

    This is a lightweight heuristic used only for Groq gating and for building
    a minimal parsed object when we skip Groq.
    """
    role_patterns = [
        r"data\s+engineer",
        r"data\s+scientist",
        r"machine\s+learning\s+engineer",
        r"ml\s+engineer",
        r"software\s+engineer",
        r"backend\s+engineer",
        r"frontend\s+engineer",
        r"full\s*stack\s+developer",
        r"devops\s+engineer",
        r"cloud\s+engineer",
        r"data\s+analyst",
        r"business\s+analyst",
        r"product\s+manager",
        r"bioinformatics\s+(engineer|analyst|intern)",
        r"biotechnology\s+(engineer|analyst|intern|research\s+intern)",
        r"research\s+intern",
        r"partner\s+consultant",
        r"consultant\s*\(intern\)",
    ]
    match = re.search(r"(" + "|".join(role_patterns) + r")", resume_text, re.IGNORECASE)
    if not match:
        return ""

    role = match.group(0).strip()
    # Normalize common casing a bit for downstream display.
    return " ".join([w.capitalize() if w.lower() not in {"ml"} else w.upper() for w in role.split()])


def _extract_experience_years_from_text(resume_text: str) -> float:
    """Best-effort total experience estimate using regex only."""
    match = re.search(r"(\d+\.?\d*)\+?\s*years?", resume_text, re.IGNORECASE)
    if not match:
        return 0.0
    try:
        return round(float(match.group(1)), 2)
    except Exception:
        return 0.0


def _extract_experience_years_from_date_ranges(resume_text: str) -> float:
    """Best-effort total experience estimate using date ranges in raw resume text.

    This is used only for Groq gating (and for populating minimal ResumeData when skipping Groq).
    It is intentionally conservative: it estimates experience based on the maximum span found
    across detected ranges like "Jan 2023 - Jun 2023" or "January 2025 – Present".
    """
    if not resume_text:
        return 0.0

    month_map = {
        "jan": 1, "january": 1,
        "feb": 2, "february": 2,
        "mar": 3, "march": 3,
        "apr": 4, "april": 4,
        "may": 5,
        "jun": 6, "june": 6,
        "jul": 7, "july": 7,
        "aug": 8, "august": 8,
        "sep": 9, "sept": 9, "september": 9,
        "oct": 10, "october": 10,
        "nov": 11, "november": 11,
        "dec": 12, "december": 12,
    }

    def _parse_month_year(raw: str):
        raw = (raw or "").strip().lower()
        if not raw:
            return None
        m = re.match(r"^(?P<mon>[a-z]{3,9})\s+(?P<yr>\d{4})$", raw)
        if not m:
            return None
        mon = month_map.get(m.group("mon"))
        if not mon:
            return None
        return int(m.group("yr")), int(mon)

    def _months_between(start, end) -> int:
        if not start or not end:
            return 0
        sy, sm = start
        ey, em = end
        return max(0, (ey - sy) * 12 + (em - sm))

    # Match patterns like:
    # - "January 2025 - Present"
    # - "Jan 2023 – Jun 2023"
    # - "Jan 2023 to Jun 2023"
    date_range_pat = re.compile(
        r"(?P<smon>[A-Za-z]{3,9})\s+(?P<syr>\d{4})\s*(?:to|\-|–|—)\s*(?:(?P<emon>[A-Za-z]{3,9})\s+(?P<eyr>\d{4})|(?P<endtxt>Present|Current|Ongoing))",
        re.IGNORECASE,
    )

    matches = list(date_range_pat.finditer(resume_text))
    if not matches:
        return 0.0

    from datetime import datetime
    now = datetime.utcnow()
    current = (now.year, now.month)

    max_months = 0
    for m in matches:
        start = _parse_month_year(f"{m.group('smon')} {m.group('syr')}")
        if not start:
            continue

        if m.group("endtxt"):
            end = current
        else:
            end = _parse_month_year(f"{m.group('emon')} {m.group('eyr')}")

        months = _months_between(start, end)
        if months > max_months:
            max_months = months

    if max_months <= 0:
        return 0.0

    # Convert months to years, keep it conservative (no +1 inclusive month counting here).
    return round(max_months / 12.0, 2)


class RAGResumePipeline:
    """
    Complete RAG pipeline for resume processing.
    """

    def __init__(self):
        self.storage = LocalStorageManager()
        self.vector_db = VectorDatabase()
        self.embedder = EmbeddingGenerator()
        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        self.llm_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    # ------------------------- MAIN PROCESSING ------------------------- #

    def process_resume(self, file_obj, candidate_id: str | None = None) -> Dict:
        """
        Process single resume through complete pipeline.
        """
        if not candidate_id:
            candidate_id = str(uuid.uuid4())

        print(f"\n{'=' * 60}")
        print(f"Processing Resume: {candidate_id}")
        print(f"{'=' * 60}")

        try:
            # 1) Save file
            print("1. Saving file to local storage...")
            file_path = self.storage.upload_resume(file_obj, candidate_id)
            print(f"   ✓ Saved to: {file_path}")

            # 2) Extract text
            print("2. Extracting text from file...")
            resume_text = extract_resume_text(file_path)
            print(f"   ✓ Extracted {len(resume_text)} characters")

            # 3) Always use Groq parsing for maximum extraction quality
            print("3. Parsing resume with Groq Llama 3.3 70B...")
            parsed_data = parse_resume_with_groq(resume_text)
            print("   ✓ Parsed successfully")

            import json
            parsed_dict = parsed_data.dict()

            print("===== PARSED RESUME (DEBUG) =====")
            print(json.dumps(parsed_dict, indent=2)[:4000])
            print("=================================")

            # 4) Validation stats
            stats = validate_parsed_data(parsed_data)
            
            # ✅ FIXED: Safe stats printing with all new fields
            print("\n   Parsing Statistics:")
            print(f"   - Candidate: {stats.get('candidate_name', 'Unknown')}")
            print(f"   - Email: {stats.get('email', 'Not found')}")
            print(f"   - Phone: {stats.get('phone', 'Not found')}")
            print(f"   - Primary Role: {stats.get('primary_role', 'Not found')}")
            print(f"   - Experience Summary: {'✓' if stats.get('has_experience_summary') else '✗'}")
            print(f"   - Primary Skills: {stats.get('primary_skills_count', 0)}")
            print(f"   - Technical Skills: {stats.get('technical_skills_count', 0)}")
            print(f"   - Skill Categories: {stats.get('skill_categories_count', 0)}")
            print(f"   - Total Jobs: {stats.get('total_jobs', 0)}")
            print(f"   - Total Projects: {stats.get('total_projects', 0)}")
            print(f"   - Projects with Description: {stats.get('projects_with_description', 0)}")
            print(f"   - Projects with Role: {stats.get('projects_with_role', 0)}")
            print(f"   - Projects with Responsibilities: {stats.get('projects_with_responsibilities', 0)}")
            print(f"   - Certifications: {stats.get('certifications_count', 0)}")
            print(f"   - Total Responsibilities: {stats.get('total_responsibilities', 0)}")
            print(f"   - Total Experience: {stats.get('total_experience_years', 0.0)} years")
            print(f"   - Education Entries: {stats.get('education_count', 0)}")
            
            # Print job breakdown if exists
            for job in stats.get("jobs_breakdown", []):
                print(
                    f"     • {job.get('company', 'Unknown')} - {job.get('title', 'Unknown')}: "
                    f"{job.get('responsibilities_count', 0)} responsibilities"
                )
            
            # Print project breakdown if exists
            for proj in stats.get("project_breakdown", []):
                print(
                    f"     • Project '{proj.get('name', 'Unknown')}': "
                    f"{proj.get('responsibilities_count', 0)} responsibilities, "
                    f"{proj.get('technical_tools_count', 0)} tools"
                )

            # 5) Generate embeddings
            print("\n4. Generating embeddings...")
            summary_text = self._create_summary_text(parsed_data)
            summary_embedding = self.embedder.generate_embedding(summary_text)

            experience_texts = [
                self._create_experience_text(exp)
                for exp in (parsed_data.work_experiences or [])
            ]
            experience_embeddings = self.embedder.generate_batch_embeddings(
                experience_texts
            ) if experience_texts else []

            print(f"   ✓ Generated {len(experience_embeddings) + 1} embeddings")

            # 6) Store in SQL
            print("5. Saving candidate record in SQL...")
            from datetime import datetime

            raw_text = resume_text
            parsed = parsed_dict or {}
            sections = parsed.get("sections") or {}

            # ✅ IMPROVED: Better field extraction
            projects = (
                parsed.get("projects") or 
                sections.get("projects") or 
                []
            )
            
            contact = parsed.get("contact") or parsed.get("contact_info") or {}
            phone = (
                parsed.get("phone") or
                contact.get("phone") or
                contact.get("mobile") or
                ""
            )

            roles = (
                parsed.get("work_experiences") or
                parsed.get("roles") or
                parsed.get("experience") or
                sections.get("experience") or
                []
            )

            skills = (
                parsed.get("technical_skills") or
                parsed.get("skills") or
                sections.get("skills") or
                []
            )

            education = (
                parsed.get("education") or
                sections.get("education") or
                []
            )

            certifications = parsed.get("certifications") or []
            languages = parsed.get("languages") or []

            # ✅ IMPROVED: Better primary_role extraction
            primary_role = parsed.get("primary_role")
            if not primary_role and roles:
                first_role = roles[0] if roles else {}
                if isinstance(first_role, dict):
                    primary_role = first_role.get("job_title") or ""
                    
            # ✅ NEW: Also try from latest project role
            if not primary_role and projects:
                first_project = projects[0] if projects else {}
                if isinstance(first_project, dict):
                    primary_role = first_project.get("role") or ""

            # ✅ SMART EXPERIENCE CALCULATION
            # Experience calculation priority (explicit):
            # 1) Parsed LLM output (total_experience_years)
            # 2) Regex extraction from summary text
            # 3) Duration-based calculation from work history
            # Final experience is the MAX across sources.
            llm_experience = float(parsed.get("total_experience_years") or 0.0)
            
            # 2) From experience summary text extraction
            summary_experience = extract_experience_from_summary(parsed)
            
            # 3) From work_experiences duration calculation
            jobs_experience = calculate_experience_from_jobs(roles)
            
            # Use the highest value (most accurate)
            final_experience = max(llm_experience, summary_experience, jobs_experience)
            
            print(f"\n   📊 Experience Sources:")
            print(f"      - LLM parsed: {llm_experience} years")
            print(f"      - Summary extraction: {summary_experience} years")
            print(f"      - Jobs calculation: {jobs_experience} years")
            print(f"      - ✅ Final: {final_experience} years")

            cand = Candidate(
                full_name=parsed.get("candidate_name") or "",
                email=parsed.get("email") or "",
                phone=phone,
                raw_text=raw_text,
                parsed=parsed,
                pdf_path=file_path,
                skills=skills,
                education=education,
                work_experiences=roles,
                certifications=certifications,
                languages=languages,
                projects=projects,
                total_experience_years=final_experience,  # ✅ NEW: Smart calculation
                primary_role=primary_role,
                primary_domain=parsed.get("primary_domain"),
                source="upload",
                created_at=datetime.utcnow(),
            )

            # ✅ Safe bucket classification
            try:
                from services.chatbot import classify_candidate_bucket
                cand.role_bucket = classify_candidate_bucket(parsed, primary_role)
            except Exception as e:
                print(f"   Warning: Bucket classification failed: {e}")
                cand.role_bucket = "general"

            db.session.add(cand)
            db.session.commit()

            print(f"   ✓ Saved candidate in SQL with id={cand.id}")

            # 7) Store in vector DB
            print("6. Storing in vector database...")
            self.vector_db.add_candidate(
                candidate_id=cand.id,
                parsed_data=parsed_dict,
                embeddings={
                    "summary": summary_embedding,
                    "experiences": experience_embeddings,
                },
                pdf_path=file_path,
            )
            print("   ✓ Stored in vector DB")

            print(f"\n{'=' * 60}")
            print(f"✓ Resume processed successfully: {parsed_data.candidate_name}")
            print(f"{'=' * 60}\n")

            return {
                "success": True,
                "candidate_id": cand.id,
                "candidate_name": parsed_data.candidate_name,
                "pdf_path": file_path,
                "parsed_data": parsed_dict,
                "stats": stats,
            }

        except Exception as e:
            import traceback
            print(f"\n✗ Error processing resume: {str(e)}")
            print(traceback.format_exc())
            return {
                "success": False,
                "error": str(e),
                "candidate_id": candidate_id,
            }

    # ------------------------- BATCH ------------------------- #
    def batch_process_resumes(self, files: List) -> Dict:
        results = []
        successful = 0
        failed = 0

        print(f"\n{'=' * 60}")
        print(f"BATCH PROCESSING: {len(files)} resumes")
        print(f"{'=' * 60}\n")

        for idx, f in enumerate(files, 1):
            print(f"[{idx}/{len(files)}] Processing...")
            result = self.process_resume(f)
            results.append(result)
            if result.get("success"):
                successful += 1
            else:
                failed += 1

        print(f"\n{'=' * 60}")
        print("BATCH PROCESSING COMPLETE")
        print(f"✓ Successful: {successful}")
        print(f"✗ Failed: {failed}")
        print(f"{'=' * 60}\n")

        return {
            "total": len(files),
            "successful": successful,
            "failed": failed,
            "results": results,
        }

    def add_to_vector_db(self, candidate_id: int, text: str):
        """Safe wrapper for app.py upload route"""
        try:
            summary_embedding = self.embedder.generate_embedding(text)
            
            minimal_parsed = {
                "text": text[:2000],
                "candidate_id": candidate_id
            }
            
            self.vector_db.add_candidate(
                candidate_id=candidate_id,
                parsed_data=minimal_parsed,
                embeddings={
                    "summary": summary_embedding,
                    "experiences": []
                },
                pdf_path="direct_upload"
            )
            print(f"✅ Vector DB added candidate {candidate_id}")
        except Exception as e:
            print(f"Vector DB add failed (non-critical): {e}")

    # ------------------------- SEARCH ------------------------- #
    def search_candidates(
        self,
        job_description: str,
        top_k: int = 20,
        min_experience_years: float | None = None,
        candidate_ids: List[int] | None = None,  # ✅ ADD THIS
    ) -> List[Dict]:
        from models import Candidate

        print("\nSearching for candidates matching job description...")
        print(f"Job Description: {job_description[:100]}...")
        
        # ✅ If candidate_ids provided, filter by them
        if candidate_ids:
            print(f"🔍 Filtering to candidate IDs: {candidate_ids}")

        jd_embedding = self.embedder.generate_embedding(job_description)
        hits = self.vector_db.semantic_search(
            query_embedding=jd_embedding,
            top_k=top_k,
            candidate_ids=candidate_ids,  # ✅ PASS TO VECTOR DB
        )
        print(f"✓ Raw vector hits: {len(hits)}")

        if not hits:
            print("No vector hits; falling back to latest candidates from SQL.")
            
            # ✅ Apply candidate_ids filter to fallback query too
            query = Candidate.query.order_by(Candidate.created_at.desc())
            if candidate_ids:
                query = query.filter(Candidate.id.in_(candidate_ids))
            rows = query.limit(top_k).all()
            
            enriched = []
            for cand_row in rows:
                years = cand_row.total_experience_years or 0.0
                if min_experience_years is not None and years < min_experience_years:
                    continue

                parsed = cand_row.parsed or {}
                skills = parsed.get("technical_skills") or parsed.get("skills") or []
                roles = parsed.get("work_experiences") or parsed.get("roles") or []

                enriched.append({
                    "candidate_id": cand_row.id,
                    "candidate_name": cand_row.full_name or "Unknown",
                    "similarity_score": 0.5,
                    "total_experience_years": float(years),
                    "skills": skills,
                    "roles": roles,
                    "primary_role": cand_row.primary_role,
                    "primary_domain": cand_row.primary_domain,
                    "match_reason": "Recent candidate (fallback)",
                })
            return enriched

        enriched: List[Dict] = []
        for h in hits:
            cand_id = h["candidate_id"]
            
            # ✅ Skip if not in allowed IDs
            if candidate_ids and cand_id not in candidate_ids:
                continue
            
            cand_row: Candidate | None = Candidate.query.get(cand_id)
            if not cand_row:
                continue

            years = cand_row.total_experience_years or 0.0
            if min_experience_years is not None and years < min_experience_years:
                continue

            parsed = cand_row.parsed or {}
            skills = parsed.get("technical_skills") or parsed.get("skills") or []
            roles = parsed.get("work_experiences") or parsed.get("roles") or []

            enriched.append({
                "candidate_id": cand_row.id,
                "candidate_name": cand_row.full_name or "Unknown",
                "similarity_score": 1.0 - float(h["score"]),
                "total_experience_years": float(years),
                "skills": skills,
                "roles": roles,
                "primary_role": cand_row.primary_role,
                "primary_domain": cand_row.primary_domain,
                "match_reason": f"Skills match: {', '.join(skills[:5])}" if skills else "Semantic match",
            })

        return enriched


    # ------------------------- UTILITIES ------------------------- #
    def get_candidate_details(self, candidate_id: str) -> Dict:
        rec = self.vector_db.get_candidate_by_id(candidate_id)
        if not rec:
            return {}
        return {
            "candidate_id": rec["candidate_id"],
            "candidate_name": rec["candidate_name"],
            "email": rec["email"],
            "phone": rec["phone"],
            "pdf_path": rec["pdf_path"],
            "parsed": rec["parsed_data"],
        }

    def _create_summary_text(self, parsed_data) -> str:
        """Create rich summary text for embedding."""
        parts = []
        
        # Name
        if parsed_data.candidate_name:
            parts.append(parsed_data.candidate_name)
        
        # Experience summary
        if parsed_data.experience_summary:
            parts.append(parsed_data.experience_summary[:500])
        elif parsed_data.professional_summary:
            parts.append(parsed_data.professional_summary[:500])
        
        # Primary skills
        if parsed_data.primary_skills:
            parts.append(f"Skills: {', '.join(parsed_data.primary_skills[:15])}")
        
        # Technical skills
        if parsed_data.technical_skills:
            parts.append(f"Technical: {', '.join(parsed_data.technical_skills[:15])}")
        
        # Primary role
        if parsed_data.primary_role:
            parts.append(f"Role: {parsed_data.primary_role}")
        
        return " ".join(parts)

    def _create_experience_text(self, experience) -> str:
        """Create text from work experience for embedding."""
        parts = []
        
        if experience.job_title:
            parts.append(experience.job_title)
        
        if experience.company_name:
            parts.append(f"at {experience.company_name}")
        
        if experience.responsibilities:
            parts.append(" ".join(experience.responsibilities[:5]))
        
        return " ".join(parts) if parts else "Experience"
