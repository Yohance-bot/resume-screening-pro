from sentence_transformers import SentenceTransformer
from typing import List
from config.local_config import EMBEDDING_MODEL

class EmbeddingGenerator:
    """Generate embeddings for semantic search"""
    
    def __init__(self):
        print(f"\nLoading embedding model: {EMBEDDING_MODEL}")
        print("(First time may take 1-2 minutes to download ~80MB model...)")
        
        # This will download the model on first run
        self.model = SentenceTransformer(EMBEDDING_MODEL)
        
        print("✓ Embedding model loaded successfully!\n")
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for single text"""
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
    
    def generate_batch_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts (more efficient)"""
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()
    def build_candidate_text(self, candidate) -> str:
        """
        Build a rich text representation of a Candidate using all extracted fields.
        This is what will be embedded & stored in Chroma.
        """
        parsed = candidate.parsed or {}
        sections = parsed.get("sections", {})

        full_name = candidate.full_name or parsed.get("full_name") or ""
        email = candidate.email or parsed.get("email") or ""
        phone = candidate.phone or parsed.get("phone") or ""

        summary = parsed.get("summary") or ""
        primary_role = candidate.primary_role or parsed.get("primary_role") or ""
        primary_domain = candidate.primary_domain or parsed.get("primary_domain") or ""

        skills = parsed.get("skills") or sections.get("skills") or (candidate.skills or [])
        skills_text = ", ".join([str(s) for s in skills])

        edu_entries = parsed.get("education") or sections.get("education") or (candidate.education or [])
        edu_parts = []
        for e in edu_entries:
            if isinstance(e, dict):
                deg = e.get("degree") or ""
                inst = e.get("institution") or ""
                year = e.get("year") or ""
                edu_parts.append(f"{deg} at {inst} ({year})")
            else:
                edu_parts.append(str(e))
        education_text = " | ".join(edu_parts)

        work_entries = parsed.get("roles") or sections.get("experience") or (candidate.work_experiences or [])
        work_parts = []
        for w in work_entries:
            if not isinstance(w, dict):
                continue
            title = w.get("title") or w.get("job_title") or ""
            company = w.get("company") or w.get("company_name") or ""
            start = w.get("start_date") or ""
            end = w.get("end_date") or ""
            responsibilities = w.get("responsibilities") or w.get("description") or ""
            if isinstance(responsibilities, list):
                resp_text = "; ".join(str(r) for r in responsibilities)
            elif isinstance(responsibilities, dict):
                resp_text = "; ".join(str(v) for v in responsibilities.values())
            else:
                resp_text = str(responsibilities)
            work_parts.append(
                f"Role: {title} at {company} from {start} to {end}. Responsibilities: {resp_text}"
            )
        work_text = " || ".join(work_parts)

        certs = parsed.get("certifications") or (candidate.certifications or [])
        cert_parts = []
        for c in certs:
            if isinstance(c, dict):
                cname = c.get("name") or ""
                org = c.get("issuing_organization") or ""
                date = c.get("date_obtained") or ""
                cert_parts.append(f"{cname} by {org} ({date})")
            else:
                cert_parts.append(str(c))
        cert_text = " | ".join(cert_parts)

        # Languages, projects, tools if you store them
        languages = parsed.get("languages") or (candidate.languages or [])
        language_text = ", ".join([str(l) for l in languages])

        projects = parsed.get("projects") or (candidate.projects or [])
        proj_parts = []
        for p in projects:
            if isinstance(p, dict):
                name = p.get("name") or ""
                desc = p.get("description") or ""
                tech = p.get("technologies_used") or p.get("tech_stack") or []
                if isinstance(tech, list):
                    tech_text = ", ".join(str(t) for t in tech)
                else:
                    tech_text = str(tech)
                proj_parts.append(f"Project: {name}. Description: {desc}. Tech: {tech_text}")
            else:
                proj_parts.append(str(p))
        projects_text = " || ".join(proj_parts)

        # Final rich text (order matters for semantics)
        parts = [
            f"Name: {full_name}",
            f"Contact: {email} {phone}",
            f"Summary: {summary}",
            f"Primary role: {primary_role}",
            f"Primary domain: {primary_domain}",
            f"Skills: {skills_text}",
            f"Education: {education_text}",
            f"Work experience: {work_text}",
            f"Certifications: {cert_text}",
            f"Languages: {language_text}",
            f"Projects: {projects_text}",
        ]
        return "\n".join([p for p in parts if p.strip()])