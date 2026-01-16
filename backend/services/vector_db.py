# services/vector_db.py
import chromadb
from typing import List, Dict, Optional
from config.local_config import VECTOR_DB_PATH
import json

class VectorDatabase:
    def __init__(self):
        VECTOR_DB_PATH = "chroma_db_v2"
        self.client = chromadb.PersistentClient(path=VECTOR_DB_PATH)
        self.collection = self.client.get_or_create_collection(
            name="resumes",
            metadata={"description": "Resume embeddings for RAG search"},
        )

    def add_candidate(
        self,
        candidate_id: int,              # SQL PK
        parsed_data: dict,
        embeddings: Dict[str, List[float]],
        pdf_path: str,
    ):
        summary_meta = {
            "candidate_pk": candidate_id,  # used for lookups
            "candidate_name": parsed_data.get("candidate_name"),
            "email": parsed_data.get("email"),
            "phone": parsed_data.get("phone", ""),
            "pdf_path": pdf_path,
            "total_experience_years": parsed_data.get("total_experience_years"),
            "skills": json.dumps(parsed_data.get("technical_skills", [])),
            "parsed_data": json.dumps(parsed_data),
            "doc_type": "summary",
        }
        summary_meta = self._clean_metadata(summary_meta)

        self.collection.add(
            ids=[str(candidate_id)],
            embeddings=[embeddings["summary"]],
            metadatas=[summary_meta],
            documents=[self._create_summary_text(parsed_data)],
        )

        for idx, (exp, exp_embedding) in enumerate(
            zip(parsed_data.get("work_experiences", []), embeddings["experiences"])
        ):
            exp_id = f"{candidate_id}_exp_{idx}"
            exp_meta = {
                "candidate_pk": candidate_id,
                "candidate_name": parsed_data.get("candidate_name"),
                "company": exp.get("company_name"),
                "job_title": exp.get("job_title"),
                "duration_months": exp.get("duration_months"),
                "doc_type": "experience",
            }
            exp_meta = self._clean_metadata(exp_meta)

            self.collection.add(
                ids=[exp_id],
                embeddings=[exp_embedding],
                metadatas=[exp_meta],
                documents=[self._create_experience_text(exp)],
            )

    def semantic_search(
        self,
        query_embedding=None,
        query_text=None,
        top_k: int = 50,
        candidate_ids: List[int] | None = None,  # ✅ ADD THIS PARAMETER
    ):
        if query_embedding is None and query_text is None:
            raise ValueError("Provide query_embedding or query_text")

        # ✅ Build where filter if candidate_ids provided
        where_filter = None
        if candidate_ids:
            where_filter = {"candidate_pk": {"$in": candidate_ids}}
            print(f"🔍 ChromaDB filter: candidate_pk in {candidate_ids}")

        if query_embedding is not None:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                include=["metadatas", "distances"],
                where=where_filter,  # ✅ APPLY FILTER
            )
        else:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=top_k,
                include=["metadatas", "distances"],
                where=where_filter,  # ✅ APPLY FILTER
            )

        metadatas = results.get("metadatas") or [[]]
        distances = results.get("distances") or [[]]

        if not metadatas or not metadatas[0]:
            return []

        hits = []
        for i, meta in enumerate(metadatas[0]):
            if not meta:
                continue
            cand_pk = meta.get("candidate_pk")
            if cand_pk is None:
                continue
            
            # ✅ Double-check filter (redundant but safe)
            if candidate_ids and int(cand_pk) not in candidate_ids:
                continue
            
            hits.append({
                "candidate_id": int(cand_pk),
                "score": float(distances[0][i]),
            })
        
        print(f"✓ Filtered to {len(hits)} results")
        return hits

    def get_candidate_by_id(self, candidate_id: int) -> Optional[Dict]:
        results = self.collection.get(
            ids=[str(candidate_id)],
            where={"doc_type": "summary"},
        )
        if not results.get("ids"):
            return None

        metadata = results["metadatas"][0]
        parsed_data_raw = metadata.get("parsed_data")
        try:
            parsed_data = json.loads(parsed_data_raw) if parsed_data_raw else {}
        except Exception:
            parsed_data = {}

        candidate_name = (
            metadata.get("candidate_name")
            or parsed_data.get("candidate_name")
            or parsed_data.get("full_name")
            or parsed_data.get("name")
            or "Unknown"
        )

        return {
            "candidate_id": metadata["candidate_pk"],
            "candidate_name": candidate_name,
            "email": metadata.get("email") or parsed_data.get("email") or "",
            "phone": metadata.get("phone", ""),
            "pdf_path": metadata["pdf_path"],
            "parsed_data": parsed_data,
        }

    def delete_candidate(self, candidate_id: int):
        cid = str(candidate_id)
        self.collection.delete(ids=[cid])
        all_docs = self.collection.get(include=[])
        exp_ids = [
            doc_id for doc_id in all_docs.get("ids", [])
            if doc_id.startswith(f"{cid}_exp_")
        ]
        if exp_ids:
            self.collection.delete(ids=exp_ids)

    def _create_summary_text(self, parsed_data: dict) -> str:
        """Create rich summary text for embedding - ✅ FIXED"""
        parts = []
        
        # Name
        if parsed_data.get("candidate_name"):
            parts.append(parsed_data["candidate_name"])
        
        # Experience summary (prioritize this over professional_summary)
        summary = parsed_data.get("experience_summary") or parsed_data.get("professional_summary")
        if summary:
            parts.append(summary[:500])  # First 500 chars
        
        # Primary skills (new field)
        primary_skills = parsed_data.get("primary_skills", [])
        if primary_skills and isinstance(primary_skills, list):
            parts.append(f"Primary Skills: {', '.join(primary_skills[:15])}")
        
        # Technical skills - ✅ FIX: Handle None and non-list values
        technical_skills = parsed_data.get("technical_skills", [])
        if technical_skills:
            if isinstance(technical_skills, list):
                parts.append(f"Technical Skills: {', '.join(technical_skills[:15])}")
            elif isinstance(technical_skills, str):
                parts.append(f"Technical Skills: {technical_skills}")
        
        # General skills fallback
        if not technical_skills:
            skills = parsed_data.get("skills", [])
            if skills and isinstance(skills, list):
                parts.append(f"Skills: {', '.join(skills[:15])}")
        
        # Primary role
        if parsed_data.get("primary_role"):
            parts.append(f"Role: {parsed_data['primary_role']}")
        
        # Domain
        if parsed_data.get("primary_domain"):
            parts.append(f"Domain: {parsed_data['primary_domain']}")
        
        # Experience years
        exp_years = parsed_data.get("total_experience_years", 0)
        if exp_years:
            parts.append(f"Experience: {exp_years} years")
        
        return " | ".join(parts) if parts else "Resume data"

    def _create_experience_text(self, experience: dict) -> str:
        """Create experience text for embedding"""
        parts = []
        
        job_title = experience.get("job_title", "")
        company = experience.get("company_name", "")
        
        if job_title and company:
            parts.append(f"{job_title} at {company}")
        elif job_title:
            parts.append(job_title)
        elif company:
            parts.append(company)
        
        # Add responsibilities
        responsibilities = experience.get("responsibilities", [])
        if responsibilities and isinstance(responsibilities, list):
            parts.append(" ".join(responsibilities[:5]))  # First 5 responsibilities
        
        # Add technologies
        technologies = experience.get("technologies_used", [])
        if technologies and isinstance(technologies, list):
            parts.append(f"Technologies: {', '.join(technologies[:10])}")
        
        return " ".join(parts) if parts else "Work experience"

    def _clean_metadata(self, meta: dict) -> dict:
        """Clean metadata for ChromaDB (only supports str, int, float, bool)"""
        cleaned = {}
        for k, v in meta.items():
            if v is None:
                continue
            if isinstance(v, (str, int, float, bool)):
                cleaned[k] = v
            else:
                cleaned[k] = str(v)
        return cleaned

    def clear_all(self):
        """Delete all documents from the collection"""
        ids = self.collection.get(include=[]).get("ids", [])
        if ids:
            self.collection.delete(ids=ids)
