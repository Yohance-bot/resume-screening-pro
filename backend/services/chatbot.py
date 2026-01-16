import uuid
from collections import Counter
from typing import List, Dict, Optional, Tuple
import json
from groq import Groq
from flask import current_app
from sqlalchemy.orm.attributes import flag_modified
from models import db, Candidate
from models import ChatSession, ChatMessage, JD
from services.rag_pipeline import RAGResumePipeline
from config.local_config import GROQ_API_KEY
from services.smart_screening import smart_screen_candidate
from services.general_queries import get_query_handler
from typing import Dict, List, Any, Optional
from datetime import datetime
import re
from sqlalchemy import func

TEAM_SIZE_PATTERNS = [
    re.compile(r"\bprojects?\s+(with|which\s+have|having)\s+(?P<n>\d+)\s+(team\s+members?|members?|contributors?|people)\b", re.I),
    re.compile(r"\bprojects?\s+where\s+team\s+size\s*(=|is|equals?)\s*(?P<n>\d+)\b", re.I),
    re.compile(r"\bteam\s+size\s*(=|is|equals?)\s*(?P<n>\d+)\s+projects?\b", re.I),
]

def _extract_team_size_query(text: str):
    text = (text or "").strip()
    for pat in TEAM_SIZE_PATTERNS:
        m = pat.search(text)
        if m:
            return int(m.group("n"))
    return None

ROLE_TEMPLATES: Dict[str, str] = {
    "data scientist": """
Senior Data Scientist role.

Must-haves:
- Strong Python and SQL.
- Experience with machine learning and deep learning.
- Experience with model deployment (Flask/FastAPI, MLflow, Azure/AWS/GCP, Databricks).
- Experience with NLP / GenAI is a plus.
""",
    "data engineer": """
Senior Data Engineer role.

Must-haves:
- Strong SQL and Python/Scala.
- Experience with ETL/ELT pipelines on cloud (Azure/AWS/GCP).
- Tools like Databricks, Spark, Airflow/ADF, Kafka.
- Good understanding of data modeling and warehousing.
""",
    "ml engineer": """
ML Engineer role.

Must-haves:
- Strong software engineering in Python.
- Experience with training/serving ML models at scale.
- Tools like TensorFlow/PyTorch, MLflow, Docker, Kubernetes, cloud ML services.
""",
    "backend engineer": """
Backend Engineer role.

Must-haves:
- Strong backend language (Python/Node/Java) and REST APIs.
- Databases (SQL/NoSQL).
- Cloud deployment, logging, and monitoring.
""",
}

# ---------------- bucket classifier ---------------- #

def classify_candidate_bucket(parsed: Dict[str, Any], primary_role: str = "") -> str:
    title = (primary_role or parsed.get("primary_role") or "").lower()

    # Hard overrides on title
    if any(k in title for k in [
        "data scientist",
        "data analyst/scientist",
        "data analyst / scientist",
        "ml scientist",
        "machine learning scientist",
    ]):
        return "data_scientist"

    sci_skills = {
        "scikit", "sklearn", "xgboost", "lightgbm",
        "pytorch", "tensorflow", "regression", "classification",
        "clustering", "forecast", "predictive",
    }
    practice_skills = {
        "spark", "pyspark", "airflow", "dbt",
        "snowflake", "redshift", "bigquery",
        "hadoop", "kafka", "etl", "elt",
    }

    skills = {
        str(s).lower()
        for src in [parsed.get("technical_skills") or [], parsed.get("skills") or []]
        for s in src
    }

    if any(kw in s for s in skills for kw in sci_skills):
        return "data_scientist"
    if any(kw in s for s in skills for kw in practice_skills):
        return "data_practice"

    return "data_practice"


class ChatOrchestrator:
    def _handle_projects_by_team_size(self, n: int):
        # Import models the same way as elsewhere in this file
        from models import ProjectDB, CandidateProject  # adjust path if your imports differ
        from app import db
        from sqlalchemy import func

        rows = (
            db.session.query(
                ProjectDB.id,
                ProjectDB.name,
                func.count(func.distinct(CandidateProject.candidate_id)).label("team_size"),
            )
            .join(CandidateProject, CandidateProject.project_id == ProjectDB.id)
            .group_by(ProjectDB.id, ProjectDB.name)
            .having(func.count(func.distinct(CandidateProject.candidate_id)) == n)
            .order_by(ProjectDB.name.asc())
            .all()
        )

        if not rows:
            return f"No projects found with team size {n}."

        lines = [f"Projects with {n} team members:"]
        for pid, name, team_size in rows:
            lines.append(f"- {name} (id={pid})")

        return "\n".join(lines)
    """
    Database-aware chat assistant for your resume RAG system.

    Capabilities:
    - Rank candidates for example roles (Data Scientist, Data Engineer, etc.).
    - Answer questions about emails, phones, skills, projects, and experience.
    - Handle general queries about candidates (counts, lists, filters, stats).
    - Behave gracefully even with vague or "bad" prompts by inferring intent.
    """

    def __init__(self):
        self.rag = RAGResumePipeline()
        self.llm = Groq(api_key=GROQ_API_KEY)

    # ---------------- session + history ---------------- #

    def get_or_create_session(self, session_uuid: str = None) -> ChatSession:
    # ✅ If session_uuid provided, try to find existing session
        if session_uuid:
            sess = ChatSession.query.filter_by(session_uuid=session_uuid).first()
            if sess:
                print(f"♻️ REUSING EXISTING SESSION: {session_uuid}")
                return sess
            else:
                print(f"🔄 SESSION NOT IN DB, CREATING WITH PROVIDED ID: {session_uuid}")
        
        # ✅ Use provided session_uuid OR generate new one
        if not session_uuid:
            session_uuid = str(uuid.uuid4())
            print(f"🆕 NEW SESSION CREATED: {session_uuid}")
        
        # ✅ Create new session with the correct UUID
        sess = ChatSession(session_uuid=session_uuid)
        db.session.add(sess)
        db.session.commit()
        return sess

    def save_message(self, session: 'ChatSession', role: str, content):
        """Save a message to the chat session with proper JSON serialization."""
        from models import ChatMessage
        import json
        
        # ✅ Convert dict to JSON string if needed
        if isinstance(content, dict):
            content_str = json.dumps(content)
        elif isinstance(content, str):
            content_str = content
        else:
            content_str = str(content)
        
        msg = ChatMessage(
            session_id=session.id,
            role=role,
            content=content_str,  # ✅ Now always a string
            created_at=datetime.now()
        )
        db.session.add(msg)
        db.session.commit()

    def get_history(self, session: ChatSession, limit: int = 20) -> List[Dict]:
        """Get chat history with JSON parsing for structured content."""
        import json
        
        messages = (
            ChatMessage.query
            .filter_by(session_id=session.id)
            .order_by(ChatMessage.created_at.asc())
            .limit(limit)
            .all()
        )
        
        # ✅ Parse JSON strings back to dicts
        parsed_messages = []
        for msg in messages:
            content = msg.content
            
            # Try to parse JSON string back to dict
            if isinstance(content, str):
                try:
                    content = json.loads(content)
                except (json.JSONDecodeError, TypeError, ValueError):
                    pass  # Keep as string if not valid JSON
            
            parsed_messages.append({
                'role': msg.role,
                'content': content,
                'created_at': msg.created_at.isoformat() if msg.created_at else None
            })
        
        return parsed_messages

    # ---------------- public entrypoint ---------------- #

    def handle_chat(self, user_message: str, session_uuid: str = None) -> Dict:
        """
        Main chat handler with conversation memory and context tracking.
        """
        session = self.get_or_create_session(session_uuid)
        self.save_message(session, "user", user_message)
        history = self.get_history(session)

        intent = self._classify_intent(user_message, history)
        print(f"🎯 FINAL INTENT: {intent}")

        response = "I couldn't process that message. Please try again."
        structured = None

        # ✅ New: robust compound filtering for candidates
        if intent.get("type") == "filter_candidates":
            from services.candidate_filters import parse_candidate_filters, run_candidate_filter_query

            spec = parse_candidate_filters(user_message)
            if not spec:
                response = "I couldn't reliably extract filters from that query. Try: 'c4 and certified in machine learning'."
                structured = None
            else:
                out = run_candidate_filter_query(spec)
                response = out.get('message', '')
                warnings = out.get('warnings') or []
                if warnings:
                    response = response + "\n\nWarnings:\n- " + "\n- ".join([str(w) for w in warnings if w])
                structured = {
                    "type": "candidate_table",
                    "headers": ["ID", "Name", "Role", "Bucket", "Experience", "Top Skills", "Email"],
                    "rows": out.get('rows', []),
                    # For curl-only debugging/verification (safe, non-sensitive)
                    "applied_filters": out.get('applied_filters') or [],
                    "warnings": warnings,
                    "scanned": out.get('scanned'),
                    "matched": out.get('matched'),
                    "spec": out.get('spec'),
                }

        # ✨ Route general queries to GeneralQueryHandler WITH CONTEXT AND SESSION
        elif intent.get("type") == "general_query":
            handler = get_query_handler()

            # ✅ Build context from chat history for entity tracking
            context = []
            for i, m in enumerate(history):
                if m.get("role") == "user":
                    assistant_msg = ""
                    if i + 1 < len(history) and history[i + 1].get("role") == "assistant":
                        assistant_msg = history[i + 1].get("content", "")
                    context.append({"user": m.get("content", ""), "assistant": assistant_msg})

            print(f"🔗 PASSING CONTEXT TO HANDLER: {len(context)} previous exchanges")
            print(f"🔑 SESSION ID: {session.session_uuid}")

            # ✅ Pass context AND session_id to handler for persistent filter memory
            query_response = handler.handle_query(
                user_message,
                context=context,
                session_id=session.session_uuid
            )

            # ✅ Guard clause: handler must return a dict with "type"
            if not isinstance(query_response, dict) or "type" not in query_response:
                response = "Query handler returned an invalid response."
                structured = None
            else:
                qtype = query_response.get("type")

                if qtype == "text":
                    response = query_response.get("message", "")
                    structured = None

                elif qtype == "skills_display":
                    response = query_response.get("message", "")
                    structured = {
                        "type": "skills_display",
                        "data": query_response.get("data") or {}
                    }

                elif qtype == "table":
                    response = query_response.get("message", "")
                    candidates = ((query_response.get("data") or {}).get("candidates")) or []

                    rows = []
                    for c in candidates:
                        if not isinstance(c, dict):
                            continue

                        skills = c.get("skills") or c.get("technical_skills") or []
                        if not isinstance(skills, list):
                            skills = []

                        skills = [str(s) for s in skills if s]
                        top_skills = ", ".join(skills[:3])
                        if len(skills) > 3:
                            top_skills += f" +{len(skills) - 3}"

                        bucket = c.get("bucket")
                        bucket_label = (
                            "Data Scientist" if bucket == "data_scientist"
                            else "Data Practice" if bucket
                            else ""
                        )

                        exp_val = c.get("experience") or 0
                        try:
                            exp_str = f"{float(exp_val):.1f} yrs"
                        except Exception:
                            exp_str = "0.0 yrs"

                        rows.append({
                            "id": c.get("id"),
                            "cells": [
                                str(c.get("id", "")),
                                c.get("name", "") or "",
                                c.get("role", "") or "",
                                bucket_label,
                                exp_str,
                                top_skills,
                                c.get("email", "") or "",
                            ]
                        })

                    structured = {
                        "type": "candidate_table",
                        "headers": ["ID", "Name", "Role", "Bucket", "Experience", "Top Skills", "Email"],
                        "rows": rows,
                    }

                elif qtype == "candidate_table":
                    # Pass-through structured table from GeneralQueryHandler (used by certification queries)
                    response = query_response.get("message", "")
                    data = query_response.get("data") or {}
                    headers = data.get("headers") or []
                    rows_in = data.get("rows") or []

                    rows = []
                    for r in rows_in:
                        if isinstance(r, dict):
                            # Support either {cells:[...]} or dict-of-values
                            cells = r.get("cells")
                            if cells is None:
                                cells = list(r.values())
                            rows.append({"cells": [str(c) if c is not None else "" for c in cells]})
                        elif isinstance(r, (list, tuple)):
                            rows.append({"cells": [str(c) if c is not None else "" for c in r]})

                    structured = {
                        "type": "candidate_table",
                        "headers": headers,
                        "rows": rows,
                    }

                elif qtype == "error":
                    response = query_response.get("message", "An error occurred while handling the query.")
                    structured = None

                else:
                    response = "I couldn't process that query. Please try rephrasing!"
                    structured = None

        # Determine response + structured payload for other intent types
        elif intent.get("type") == "ask_rank" and not intent.get("role"):
            response = (
                "For which role should I rank your candidates? "
                "For example: 'Data Scientist', 'Data Engineer', 'Backend Engineer'."
            )
            structured = None

        elif intent.get("type") == "provide_role":
            role = intent.get("role")
            response, structured = self._rank_for_role(role)

        elif intent.get("type") == "edit_candidate":
            response, structured = self._handle_edit(intent, user_message, history)

        elif intent.get("type") == "team_management":
            response, structured = self._handle_team_management(intent, user_message, history)

        else:
            # 🔍 Team size analytics (projects by team size)
            n = _extract_team_size_query(user_message)
            if n is not None:
                answer = self._handle_projects_by_team_size(n)
                return {
                    "session_id": session.session_uuid,
                    "message": answer,
                    "structured": None,
                }
            response, structured = self._handle_generic_query(user_message, history)

        # Persist assistant message
        self.save_message(session, "assistant", response)

        return {
            "session_id": session.session_uuid,
            "message": response,
            "structured": structured,
        }


    # ---------------- intent classification ---------------- #

    def _classify_intent(self, user_message: str, history: List[ChatMessage]) -> Dict:
        """
        FIXED: JD lookup + Ranking priority order
        """
        import re
        
        raw = user_message.strip()
        text = raw.lower()
        
        print(f"🔍 DEBUG INTENT: raw='{raw}' | lower='{text}'")
        
        # ==================== PRIORITY #1: JD LOOKUP ====================
        # ✅ FIXED: Escape # and match properly
        if re.search(r'#\d+', text):
            print("📄 JD LOOKUP DETECTED: #\d+")
            return self._handle_jd_lookup(user_message, history)
        
        # ==================== PRIORITY #2: TEAM ====================
        team_action_keywords = [
            'assign', 'add to team', 'create team', 'build team',
            'add to project', 'remove from team', 'remove from project'
        ]
        if raw.upper().startswith("TEAM") or any(keyword in text for keyword in team_action_keywords):
            print("🎉 TEAM MANAGEMENT DETECTED")
            return {"type": "team_management", "raw": raw}
        
        # ==================== PRIORITY #5: ADVANCED RANK OPTIONS ====================
        if raw.startswith("RANK") and ("bucket=" in text or "bench=" in text):
            print("📊 RANK ADVANCED OPTIONS DETECTED")
            return {"type": "rank_advanced", "raw": raw}
        
        # ==================== PRIORITY #6: SIMPLE RANK ====================
        if raw.startswith("RANK"):
            print("📊 SIMPLE RANK DETECTED")
            role = raw[len("RANK"):].strip() or "data scientist"
            return {"type": "provide_role", "role": role, "via_command": True}
        
        # ==================== PRIORITY #7: EDIT ====================
        if raw.upper().startswith("EDIT"):
            print("✏️ EDIT DETECTED")
            return {"type": "edit_candidate", "instruction": raw[len("EDIT"):].strip()}
        
        # ==================== PRIORITY #8: GENERAL QUERY ====================
        general_query_keywords = [
            "how many", "show me", "list", "find", "search", "who",
            "candidates with", "people with", "data scientist", "bucket"
        ]

        # ✅ Hard-priority: candidate filtering queries
        # If the user explicitly asks about candidates AND mentions constraint words, route to filter.
        # This avoids falling into general_query handlers like skills listing.
        try:
            t = text
            if (
                ('candidate' in t or 'candidates' in t)
                and any(k in t for k in ['skill', 'skills', 'certification', 'certifications', 'certified', 'experience', 'years', 'role', 'title', 'worked at', 'project', 'projects', 'worked on'])
                and any(k in t for k in ['and', 'or', 'with', 'has', 'have', 'who'])
            ):
                print("🧰 FILTER_CANDIDATES DETECTED (keyword priority)")
                return {"type": "filter_candidates", "raw": raw}
        except Exception:
            pass

        # ✅ FILTER_CANDIDATES (compound constraints)
        # Keep this before general_query so filter queries don't fall back to the LLM summary.
        try:
            from services.candidate_filters import parse_candidate_filters
            if parse_candidate_filters(raw):
                print("🧰 FILTER_CANDIDATES DETECTED")
                return {"type": "filter_candidates", "raw": raw}
        except Exception:
            pass
        
        if any(keyword in text for keyword in general_query_keywords):
            print("🔎 GENERAL QUERY DETECTED")
            return {"type": "general_query", "raw": raw}
        
        print("💬 GENERIC INTENT (DEFAULT)")
        return {"type": "generic"}

    def _rank_for_role(self, role: str):
        print(f"*** DEBUG: running _rank_for_role for role={role}")
        jd_text = self._role_template(role)
        job_description = f"""
Example job description for: {role}

{jd_text}
"""

        # 1) Get candidate pool via RAG
        candidates = self.rag.search_candidates(
            job_description=job_description,
            top_k=20,
            min_experience_years=1.0,
        )

        if not candidates:
            return (
                "There are no candidates stored yet. Upload some resumes first.",
                {"type": "empty"},
            )

        # 2) Temporary JD skill profile (later: parse real JD)
        jd = {
            "required_skills": ["python", "sql", "machine learning"],
            "bonus_skills": ["aws", "pyspark"],
        }

        # 3) Smart-screen each candidate
        scored: List[Dict[str, Any]] = []
        for c in candidates:
            cand_struct = {
                "id": c.get("candidate_id"),
                "full_name": c.get("candidate_name"),
                "skills": c.get("skills") or [],
                "roles": c.get("roles") or c.get("work_experiences") or [],
            }
            s = smart_screen_candidate(cand_struct, jd)
            s["similarity_score"] = float(c.get("similarity_score", 0.0))
            scored.append(s)

        # 4) Sort by final smart score then similarity
        scored.sort(key=lambda x: (x["final_score"], x["similarity_score"]), reverse=True)
        top = scored[:8]

        # 5) Build table rows with better reasons
        table_rows = []
        for i, s in enumerate(top, 1):
            matched = s.get("matched_required_skills", [])
            missing = s.get("missing_required_skills", [])
            flags = s.get("experience_flags", [])

            parts = []
            if matched:
                parts.append(f"Matches {', '.join(matched[:3])}")
            if missing:
                parts.append(f"missing {', '.join(missing[:2])}")
            if s.get("total_experience_years", 0) >= 5:
                parts.append("strong overall experience")
            if "excessive_hopping" in flags:
                parts.append("many short stints")
            reason = "; ".join(parts) or "Good overall fit for the role"

            table_rows.append(
                {
                    "rank": i,
                    "name": (s["candidate_name"] or "Unknown")[:40],
                    "score": f"{s['final_score']:.1f}",
                    "experience": f"{s.get('total_experience_years', 0.0):.1f} yrs",
                    "skills": ", ".join(matched[:4]) or ", ".join(
                        s.get("matched_bonus_skills", [])[:4]
                    ),
                    "reason": reason[:140],
                }
            )

        explanation = (
            f"Ranking your candidates for **{role}** using a multi-factor screening score.\n\n"
            f"- Evaluated {len(candidates)} candidate(s).\n"
            f"- Score combines technical skill match, experience quality, and recency of relevant roles.\n"
            f"- The table shows the top candidates and a short explanation for each fit."
        )

        return explanation, {
            "type": "ranking",
            "role": role,
            "total_candidates": len(candidates),
            "rows": table_rows,
        }

    # ---------------- generic Q&A over candidates ---------------- #

    def _handle_generic_query(self, query: str, history: List[ChatMessage]):
        q_lower = query.lower()

        cert_lookup = self._handle_certification_lookup(query)
        if cert_lookup is not None:
            return cert_lookup

        # Only run direct lookup when user clearly wants contact info or name search
        if any(w in q_lower for w in ["email", "phone"]) or q_lower.startswith(
            ("find ", "show ")
        ):
            direct = self._handle_direct_lookup(query)
            if direct is not None:
                return direct

        # ✅ Candidate-id-specific queries must NOT go through RAG top_k subset.
        # Example: "what are the skills of candidate 9"
        try:
            import re

            m = re.search(r"\bcandidate\s*(?:id\s*)?(\d+)\b", q_lower)
            if m:
                cand_id = int(m.group(1))
                cand = db.session.get(Candidate, cand_id)
                if not cand:
                    # Give a useful fallback instead of LLM hallucinating from a tiny subset
                    recent = Candidate.query.order_by(Candidate.created_at.desc()).limit(10).all()
                    ids = [c.id for c in recent]
                    return (
                        f"I couldn't find a candidate with ID {cand_id} in the database.",
                        {
                            "type": "summary",
                            "count": 0,
                            "available_recent_ids": ids,
                        },
                    )

                parsed = getattr(cand, "parsed", {}) or {}
                if isinstance(parsed, str):
                    try:
                        parsed = json.loads(parsed)
                    except Exception:
                        parsed = {}

                # Prefer top-level skills column; fallback to parsed
                skills = getattr(cand, "skills", None)
                if not isinstance(skills, list):
                    skills = []
                if not skills and isinstance(parsed, dict):
                    maybe = parsed.get("technical_skills") or parsed.get("skills") or parsed.get("primary_skills")
                    if isinstance(maybe, list):
                        skills = [str(s).strip() for s in maybe if str(s).strip()]

                # If user asked for skills (or similar), return a table (user requirement)
                if any(k in q_lower for k in ["skill", "skills", "technical", "technologies", "tech stack", "expertise"]):
                    rows_out = [
                        {
                            "cells": [
                                cand.id,
                                cand.full_name,
                                cand.primary_role or "",
                                ", ".join(skills) if skills else "N/A",
                            ]
                        }
                    ]
                    msg = f"Here are the skills for candidate {cand.id} ({cand.full_name})."
                    return msg, {
                        "type": "candidate_table",
                        "headers": ["ID", "Name", "Role", "Skills"],
                        "rows": rows_out,
                    }

                # Default candidate-id lookup: return a small candidate table row
                rows_out = [
                    {
                        "cells": [
                            cand.id,
                            cand.full_name,
                            cand.email or "",
                            cand.primary_role or "",
                            f"{cand.total_experience_years or 0} yrs",
                        ]
                    }
                ]
                return (
                    f"Candidate {cand.id} details:",
                    {
                        "type": "candidate_table",
                        "headers": ["ID", "Name", "Email", "Role", "Experience"],
                        "rows": rows_out,
                    },
                )
        except Exception:
            # Never break chat if parsing fails
            pass

        # ✅ Name-based skills lookup should also bypass RAG subset.
        # Example: "what are the skills of merril"
        try:
            import re

            if any(k in q_lower for k in ["skill", "skills", "technical", "technologies", "tech stack", "expertise"]):
                mname = re.search(r"\bskills?\s+(?:of|for)\s+([a-zA-Z][a-zA-Z\s\.-]{1,60})\b", query, flags=re.I)
                if mname:
                    name_term = (mname.group(1) or "").strip()
                    if name_term:
                        hits = (
                            Candidate.query.filter(Candidate.full_name.ilike(f"%{name_term}%"))
                            .order_by(Candidate.created_at.desc())
                            .limit(15)
                            .all()
                        )

                        if not hits:
                            return (
                                f"I couldn't find any candidate matching '{name_term}'.",
                                {"type": "summary", "count": 0},
                            )

                        rows_out = []
                        for cand in hits:
                            parsed = getattr(cand, "parsed", {}) or {}
                            if isinstance(parsed, str):
                                try:
                                    parsed = json.loads(parsed)
                                except Exception:
                                    parsed = {}

                            skills = getattr(cand, "skills", None)
                            if not isinstance(skills, list):
                                skills = []
                            if not skills and isinstance(parsed, dict):
                                maybe = parsed.get("technical_skills") or parsed.get("skills") or parsed.get("primary_skills")
                                if isinstance(maybe, list):
                                    skills = [str(s).strip() for s in maybe if str(s).strip()]

                            rows_out.append(
                                {
                                    "cells": [
                                        cand.id,
                                        cand.full_name,
                                        cand.primary_role or "",
                                        ", ".join(skills) if skills else "N/A",
                                    ]
                                }
                            )

                        msg = (
                            f"Here are the skills for {len(rows_out)} candidate(s) matching '{name_term}'."
                            if len(rows_out) > 1
                            else f"Here are the skills for {hits[0].full_name}."
                        )

                        return msg, {
                            "type": "candidate_table",
                            "headers": ["ID", "Name", "Role", "Skills"],
                            "rows": rows_out,
                        }
        except Exception:
            pass

        # build short user context
        context = " ".join([m.get("content", "") for m in history[-3:] if m.get("role") == "user"])
        full_query = f"{context}\n\n{query}".strip()

        candidates = self.rag.search_candidates(
            job_description=full_query,
            top_k=10,
        )

        if not candidates:
            return (
                "There are no candidates in the database yet. "
                "Upload some resumes on the 'Upload resumes' tab and try again.",
                {"type": "empty"},
            )

        # build JSON for LLM
        llm_candidates = []
        for c in candidates[:5]:  # limit to top 5
            details = self.rag.get_candidate_details(str(c["candidate_id"])) or {}
            parsed = details.get("parsed") or {}

            # truncate long arrays
            tech_skills = (parsed.get("technical_skills") or [])[:25]
            work_exps = (parsed.get("work_experiences") or [])[:3]
            projects = (parsed.get("projects") or [])[:3]
            education = (parsed.get("education") or [])[:3]

            llm_candidates.append(
                {
                    "id": c["candidate_id"],
                    "name": c["candidate_name"],
                    "primary_role": c.get("primary_role"),
                    "primary_domain": c.get("primary_domain"),
                    "total_experience_years": c.get("total_experience_years"),
                    "email": parsed.get("email"),
                    "phone": parsed.get("phone"),
                    "technical_skills": tech_skills,
                    "work_experiences": work_exps,
                    "projects": projects,
                    "education": education,
                }
            )

        system_prompt = """
You are a helpful recruiting assistant with access to structured JSON for many candidates.

You MUST:
- Answer naturally in plain English.
- When asked for specific facts (emails, phones, roles, projects, skills, years of experience),
  read them from the JSON and return them explicitly.
- When asked to "show", "list", or "summarize" candidates, provide a clear textual summary
  (names, roles, years of experience, and key skills).
- When the user mentions a role (e.g. "data scientist"), highlight which candidates best match it.
- If the query is vague or poorly worded, infer the most likely intent,
  still give a useful answer, and suggest a clearer follow-up question.

Never say "no matching candidates" as long as at least one candidate object is provided.
"""

        user_prompt = f"""
User query:
{query}

Recent conversation context:
{context}

Candidates (JSON):
{json.dumps(llm_candidates, indent=2)}

Tasks:
1. Decide what the user is really asking (ranking, contacts, skills, projects, experience summary, etc.).
2. Use ONLY the JSON data above; do not invent details.
3. Produce a concise, directly useful answer.
4. If helpful, add one short suggestion for a better follow-up question.
"""

        chat = self.llm.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.25,
            max_tokens=900,
        )
        answer = chat.choices[0].message.content

        top_names = [c["candidate_name"] for c in candidates[:3]]
        return answer, {
            "type": "summary",
            "count": len(candidates),
            "top_candidates": top_names,
        }

    def _handle_certification_lookup(self, query: str):
        import re
        import json
        from difflib import SequenceMatcher

        q = (query or "").strip()
        q_lower = q.lower()

        if not any(k in q_lower for k in ["certification", "certificate", "certified", "certifications"]):
            # Also catch common phrasing without the keyword
            if not any(k in q_lower for k in ["az-", "dp-", "aws", "gcp", "databricks", "snowflake"]):
                return None

        def _norm(s: str) -> str:
            s = str(s or "").strip().lower()
            s = re.sub(r"\s+", " ", s)
            return s

        def _score(a: str, b: str) -> float:
            a2 = _norm(a)
            b2 = _norm(b)
            if not a2 or not b2:
                return 0.0
            ratio = SequenceMatcher(None, a2, b2).ratio() * 100.0
            # token containment boosts
            tokens = [t for t in re.split(r"[^a-z0-9]+", a2) if t]
            if tokens and all(t in b2 for t in tokens[:3]):
                ratio += 10.0
            if a2 in b2:
                ratio += 10.0
            return min(100.0, ratio)

        # Try to extract the certification name from the query
        cert_term = None
        patterns = [
            r"completed\s+(.+?)\s+(?:certification|certificate)s?\b",
            r"(?:certification|certificate)s?\s+(?:in|for|on)?\s*(.+)$",
            r"who\s+(?:has|have)\s+(?:completed\s+)?(.+?)\s+(?:certification|certificate)s?\b",
            r"who\s+(?:is\s+)?(?:certified\s+)?(?:in\s+)?(.+)$",
        ]
        for pat in patterns:
            m = re.search(pat, q_lower, flags=re.I)
            if m:
                cert_term = (m.group(1) or "").strip()
                break

        # Fallback: remove generic words and treat remainder as the cert term
        if not cert_term:
            cert_term = q_lower
            cert_term = re.sub(r"\b(who|have|has|completed|done|with|the|a|an|any|candidate|candidates|people|person|certification|certifications|certificate|certified|show|list|find)\b", " ", cert_term)
            cert_term = re.sub(r"\s+", " ", cert_term).strip()

        if not cert_term or len(cert_term) < 3:
            return None

        # Collect all certifications from DB
        rows = Candidate.query.order_by(Candidate.created_at.desc()).all()
        all_cert_names = []
        matches = []

        for cand in rows:
            # Prefer top-level certifications column; fallback to parsed
            certs = getattr(cand, "certifications", None)
            if not isinstance(certs, list):
                certs = []

            parsed = getattr(cand, "parsed", {}) or {}
            if isinstance(parsed, str):
                try:
                    parsed = json.loads(parsed)
                except Exception:
                    parsed = {}
            if isinstance(parsed, dict) and not certs:
                maybe = parsed.get("certifications")
                if isinstance(maybe, list):
                    certs = maybe

            best = None
            for c in certs:
                if isinstance(c, dict):
                    name = c.get("name") or ""
                    issuer = c.get("issued_by") or ""
                    year = c.get("issued_date") or c.get("issued_year") or ""
                else:
                    name = str(c)
                    issuer = ""
                    year = ""

                if name:
                    all_cert_names.append(str(name))

                sc = _score(cert_term, name)
                if best is None or sc > best["score"]:
                    best = {
                        "score": sc,
                        "cert_name": name,
                        "issuer": issuer,
                        "year": year,
                    }

            if best and best["score"] >= 70:
                matches.append({
                    "id": cand.id,
                    "name": cand.full_name,
                    "primary_role": cand.primary_role or "",
                    "score": round(best["score"], 1),
                    "cert_name": best["cert_name"],
                    "issuer": best["issuer"],
                    "year": best["year"],
                })

        # If no matches, offer suggestions
        if not matches:
            # Suggest closest cert names from global list
            uniq = []
            seen = set()
            for n in all_cert_names:
                nn = _norm(n)
                if nn and nn not in seen:
                    seen.add(nn)
                    uniq.append(n)

            scored = sorted(
                [(n, _score(cert_term, n)) for n in uniq],
                key=lambda x: x[1],
                reverse=True,
            )[:8]

            suggestion_lines = "\n".join([f"- {n}" for n, s in scored if s >= 40])
            msg = (
                f"I couldn't find anyone with a certification matching: '{cert_term}'.\n\n"
                "If you meant one of these, reply with the exact name:\n"
                f"{suggestion_lines if suggestion_lines else '- (no close matches found)'}"
            )
            return msg, {"type": "summary", "count": 0}

        matches.sort(key=lambda m: (m["score"], m["name"]), reverse=True)
        rows_out = []
        for m in matches[:25]:
            rows_out.append({
                "cells": [
                    m["id"],
                    m["name"],
                    m["primary_role"],
                    m["cert_name"],
                    m["issuer"],
                    m["year"],
                ]
            })

        msg = f"Found {len(matches)} candidate(s) with a certification matching '{cert_term}'."
        return msg, {
            "type": "candidate_table",
            "headers": ["ID", "Name", "Role", "Certification", "Issuer", "Year"],
            "rows": rows_out,
        }

    # ---------------- direct lookups (email/phone/by name) ---------------- #

    def _handle_direct_lookup(self, query: str) -> Optional[tuple]:
        """
        Fast path for:
        - "email for sandeep"
        - "phone of sachin"
        - "find abhimanyu"
        - "show archie"
        """
        q = query.lower()

        wants_email = "email" in q
        wants_phone = "phone" in q
        wants_contact = wants_email or wants_phone

        tokens = [
            t
            for t in q.replace("?", "").split()
            if t not in {"email", "phone", "of", "for", "show", "find"}
        ]
        name_fragment = tokens[-1] if tokens else ""

        if not name_fragment and not wants_contact:
            return None

        like = f"%{name_fragment}%" if name_fragment else "%"

        rows = (
            Candidate.query.filter(Candidate.full_name.ilike(like))
            .order_by(Candidate.created_at.desc())
            .limit(10)
            .all()
        )
        if not rows:
            return (
                f"I could not find any candidate whose name looks like '{name_fragment}'. "
                "Open the Candidates tab to check exact names or IDs.",
                {"type": "summary", "count": 0},
            )

        lines = []
        for c in rows:
            if wants_contact:
                parts = []
                if wants_email or not wants_phone:
                    parts.append(f"email={c.email or 'N/A'}")
                if wants_phone:
                    parts.append(f"phone={c.phone or 'N/A'}")
                contact_str = ", ".join(parts)
                lines.append(f"- {c.full_name} (ID {c.id}): {contact_str}")
            else:
                exp = c.total_experience_years or 0.0
                lines.append(
                    f"- {c.full_name} (ID {c.id}), role={c.primary_role or '-'}, "
                    f"experience={exp:.1f} yrs"
                )

        header = (
            "Here is the contact information I found:\n"
            if wants_contact
            else "Here are candidates that match your description:\n"
        )
        text = header + "\n".join(lines)
        return text, {"type": "summary", "count": len(rows)}

    # ---------------- edit candidate ---------------- #

    def _handle_edit(self, intent: Dict, user_message: str, history: List[ChatMessage]):
        """
        Powerful edit handler:
        - User calls: EDIT <instruction>
        - LLM turns instruction + current candidate JSON into a structured patch.
        - Backend validates and applies patch, then returns a confirmation + snapshot.

        Patch improvements:
        - When appending/removing skills via /parsed/skills OR /parsed/technical_skills:
        mirror changes across technical_skills, skills, AND skill_categories
        so UI sections (e.g., Cloud platforms) update correctly.
        - Uses reassignment patterns + flag_modified to avoid JSON mutation tracking issues.
        """
        instruction = intent.get("instruction") or user_message

        # 1) Find candidate(s) we might be editing.
        q = instruction.lower()
        cand_id = None
        name_fragment = None

        import re
        import json
        from typing import Any, Dict, List
        from sqlalchemy.orm.attributes import flag_modified

        m = re.search(r"(candidate|id)\s+(\d+)", q)
        if m:
            cand_id = int(m.group(2))
        else:
            tokens = [
                t
                for t in q.replace("?", "").split()
                if t not in {"edit", "update", "change", "set", "email", "phone", "of", "for", "to"}
            ]
            name_fragment = tokens[-1] if tokens else None

        candidates_q = Candidate.query

        if cand_id is not None:
            candidates_q = candidates_q.filter(Candidate.id == cand_id)
        elif name_fragment:
            like = f"%{name_fragment}%"
            candidates_q = candidates_q.filter(Candidate.full_name.ilike(like))

        candidates_rows = (
            candidates_q
            .order_by(Candidate.created_at.desc())
            .limit(5)
            .all()
        )

        if not candidates_rows:
            return (
                "I could not find any candidate matching your EDIT command. "
                "Try including an ID (e.g. 'EDIT candidate 3 ...') or a clearer name.",
                {"type": "summary", "count": 0},
            )

        # 2) Prepare minimal JSON view of candidates for the LLM.
        llm_candidates: List[Dict[str, Any]] = []
        for c in candidates_rows:
            parsed_c = c.parsed or {}
            llm_candidates.append(
                {
                    "id": c.id,
                    "name": c.full_name,
                    "email": c.email,
                    "phone": c.phone,
                    "primary_role": c.primary_role,
                    "parsed": {
                        "technical_skills": parsed_c.get("technical_skills") or [],
                        "skills": parsed_c.get("skills") or [],
                        "skill_categories": parsed_c.get("skill_categories") or [],
                        "projects": parsed_c.get("projects") or [],
                        "work_experiences": parsed_c.get("work_experiences") or [],
                        "education": parsed_c.get("education") or [],
                    },
                }
            )

        system_prompt = """
    You are an assistant that edits candidate records.

    You will receive:
    - A free-form user instruction starting with EDIT.
    - A JSON array 'candidates' containing one or more candidate objects with:
    - id, name, email, phone, primary_role
    - parsed.technical_skills, parsed.skills, parsed.skill_categories,
        parsed.projects, parsed.work_experiences, parsed.education

    You MUST respond with a SINGLE JSON object only, no prose, of this shape:

    {
    "target_id": <int>,               // candidate id to modify
    "ops": [                          // list of edit operations
        {
        "op": "set" | "remove" | "append",
        "path": "<field_path>",
        "value": <any>                // required for "set"/"append", optional for "remove"
        }
    ],
    "requires_clarification": false | true,
    "message": "<short human explanation of what you changed or why you need clarification>"
    }

    Field path rules:
    - Top level fields:
    - "/email"
    - "/phone"
    - "/primary_role"
    - Parsed JSON fields:
    - "/parsed/projects"              (array)
    - "/parsed/projects/0"            (a specific project object)
    - "/parsed/technical_skills"
    - "/parsed/skills"
    - "/parsed/skill_categories"
    - "/parsed/work_experiences"
    - "/parsed/education"

    If the instruction is ambiguous about which candidate to edit, set
    "requires_clarification": true and describe the ambiguity in "message". DO NOT guess.

    If the instruction is clear but the change is unsafe or unsupported, also set
    "requires_clarification": true and explain.

    Examples of allowed changes:
    - Updating email or phone.
    - Adding a new project object to parsed.projects.
    - Removing a project by index.
    - Appending to skills arrays.
    - Removing a specific skill from a skills array by using:
    { "op": "remove", "path": "/parsed/technical_skills", "value": "<skill name>" }
    """

        user_prompt = {
            "instruction": instruction,
            "candidates": llm_candidates,
        }

        chat = self.llm.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_prompt, indent=2)},
            ],
            temperature=0.1,
            max_tokens=600,
        )
        raw = chat.choices[0].message.content
        print("RAW EDIT LLM OUTPUT:", raw)

        # 3) Parse JSON response safely (strip ```)
        raw_clean = raw.strip()
        if raw_clean.startswith("```"):
            raw_clean = raw_clean.strip("`").strip()
            if raw_clean.lower().startswith("json"):
                raw_clean = raw_clean[4:].strip()

        try:
            patch = json.loads(raw_clean)
        except Exception:
            return (
                "I tried to interpret your EDIT instruction but could not parse a valid edit plan. "
                "Please restate the edit more concretely (e.g. 'EDIT change phone of candidate 2 to +91-90000-00000').",
                {"type": "summary", "count": 0},
            )

        print("APPLYING EDIT PATCH:", json.dumps(patch, indent=2))
        if patch.get("requires_clarification"):
            msg = patch.get("message") or "I need more details before editing this candidate."
            return msg, {"type": "summary", "count": 0}

        target_id = patch.get("target_id")
        ops = patch.get("ops") or []
        if not target_id or not ops:
            return (
                "The edit plan was incomplete (missing target_id or ops). "
                "Try specifying exactly which candidate and field you want to change.",
                {"type": "summary", "count": 0},
            )

        cand = Candidate.query.get(target_id)
        if not cand:
            return (
                f"I could not find candidate with ID {target_id}. No changes were made.",
                {"type": "summary", "count": 0},
            )

        # Some rows may have parsed stored as a JSON string; normalize to dict before edits.
        if isinstance(cand.parsed, str):
            try:
                cand.parsed = json.loads(cand.parsed) or {}
            except Exception:
                cand.parsed = {}
        if not isinstance(cand.parsed, dict):
            cand.parsed = {}

        print("CURRENT PARSED FOR TARGET BEFORE OPS:", json.dumps(cand.parsed or {}, indent=2))

        # 4) Apply operations
        parsed = cand.parsed or {}

        def _norm(x: Any) -> str:
            return str(x or "").strip().lower()

        CLOUD_PLATFORMS = {
            "aws", "amazon web services",
            "azure", "azure ml",
            "gcp", "google cloud", "google cloud platform",
        }

        def _ensure_list(key: str) -> List[Any]:
            arr = parsed.get(key)
            if not isinstance(arr, list):
                arr = []
            parsed[key] = arr
            return arr

        def _ensure_skill_categories() -> List[Dict[str, Any]]:
            cats = parsed.get("skill_categories")
            if not isinstance(cats, list):
                cats = []
            parsed["skill_categories"] = cats
            return cats

        def _add_skill_to_category(skill: str):
            s = (skill or "").strip()
            if not s:
                return

            cat_name = "Cloud platforms" if _norm(s) in CLOUD_PLATFORMS else "Other Skills"
            cats = _ensure_skill_categories()

            cat = next(
                (
                    c for c in cats
                    if isinstance(c, dict) and _norm(c.get("category")) == _norm(cat_name)
                ),
                None,
            )
            if not cat:
                cat = {"category": cat_name, "skills": []}
                cats.append(cat)

            skills_list = cat.get("skills")
            if not isinstance(skills_list, list):
                skills_list = []

            if _norm(s) not in {_norm(x) for x in skills_list}:
                skills_list = list(skills_list) + [s]   # reassign (safer for nested JSON)
            cat["skills"] = skills_list

            # Reassign to ensure SQLAlchemy sees the updated list object
            parsed["skill_categories"] = list(cats)

        def _remove_skill_from_categories(skill: str):
            s = (skill or "").strip()
            if not s:
                return
            cats = parsed.get("skill_categories")
            if not isinstance(cats, list):
                return

            new_cats = []
            for c in cats:
                if not isinstance(c, dict):
                    new_cats.append(c)
                    continue
                skills_list = c.get("skills")
                if isinstance(skills_list, list):
                    c = dict(c)
                    c["skills"] = [v for v in skills_list if _norm(v) != _norm(s)]
                new_cats.append(c)

            parsed["skill_categories"] = new_cats

        def _append_skill_everywhere(skill: Any):
            s = (skill or "").strip()
            if not s:
                return

            # Ensure both arrays exist + mirror into both
            for key in ["technical_skills", "skills", "primary_skills"]:
                arr = _ensure_list(key)
                if _norm(s) not in {_norm(x) for x in arr}:
                    parsed[key] = list(arr) + [s]  # reassign

            _add_skill_to_category(s)

        def _remove_skill_everywhere(skill: Any):
            s = (skill or "").strip()
            if not s:
                return

            for key in ["technical_skills", "skills", "primary_skills"]:
                arr = parsed.get(key)
                if isinstance(arr, list):
                    parsed[key] = [v for v in arr if _norm(v) != _norm(s)]

            _remove_skill_from_categories(s)

            # scrub inside projects[].technologies_used (existing behavior)
            projects = parsed.get("projects")
            if isinstance(projects, list):
                new_projects = []
                for p in projects:
                    if isinstance(p, dict):
                        p2 = dict(p)
                        techs = p2.get("technologies_used")
                        if isinstance(techs, list):
                            p2["technologies_used"] = [v for v in techs if _norm(v) != _norm(s)]
                        new_projects.append(p2)
                    else:
                        new_projects.append(p)
                parsed["projects"] = new_projects

        def apply_op(op: Dict[str, Any]):
            op_type = op.get("op")
            path = op.get("path") or ""
            value = op.get("value", None)

            if not path.startswith("/"):
                return

            # Top-level fields
            if path == "/email":
                if op_type == "set":
                    cand.email = value
                return
            if path == "/phone":
                if op_type == "set":
                    cand.phone = value
                return
            if path == "/primary_role":
                if op_type == "set":
                    cand.primary_role = value
                return

            # Parsed JSON
            if not path.startswith("/parsed/"):
                return

            sub = path[len("/parsed/"):]
            parts = sub.split("/")
            root_key = parts[0]
            rest = parts[1:]

            # Whole array/object: "/parsed/technical_skills", "/parsed/skills", "/parsed/projects", "/parsed/skill_categories"
            if not rest:
                if op_type == "set":
                    parsed[root_key] = value
                    return

                if op_type == "append":
                    # Special handling for skills paths
                    if root_key in {"technical_skills", "skills"}:
                        _append_skill_everywhere(value)
                        return

                    # Generic append to list
                    cur = parsed.get(root_key)
                    if not isinstance(cur, list):
                        cur = []
                    parsed[root_key] = list(cur) + [value]  # reassign
                    return

                if op_type == "remove":
                    # Special handling for skills paths
                    if root_key in {"technical_skills", "skills"}:
                        _remove_skill_everywhere(value)
                        return

                    cur = parsed.get(root_key)
                    if isinstance(cur, list):
                        if value is None:
                            parsed[root_key] = []
                        else:
                            parsed[root_key] = [v for v in cur if _norm(v) != _norm(value)]
                    return

                return

            # Indexed element: "/parsed/projects/0"
            arr = parsed.get(root_key)
            if arr is None:
                arr = []
                parsed[root_key] = arr

            try:
                idx = int(rest[0])
            except ValueError:
                return

            if not isinstance(arr, list) or idx < 0 or idx >= len(arr):
                return

            if op_type == "set":
                new_arr = list(arr)
                new_arr[idx] = value
                parsed[root_key] = new_arr
                return

            if op_type == "remove":
                new_arr = list(arr)
                new_arr.pop(idx)
                parsed[root_key] = new_arr
                return

            if op_type == "append":
                # Append into nested list inside an indexed dict: "/parsed/projects/0/technical_tools"
                if len(rest) > 1 and isinstance(arr[idx], dict):
                    inner_key = rest[1]
                    new_arr = list(arr)
                    obj = dict(new_arr[idx])
                    inner = obj.get(inner_key)
                    if not isinstance(inner, list):
                        inner = []
                    obj[inner_key] = list(inner) + [value]
                    new_arr[idx] = obj
                    parsed[root_key] = new_arr
                return

        # Actually apply all ops
        for op in ops:
            apply_op(op)

            # Backward-compatible scrub: if LLM uses remove on technical_skills, also scrub elsewhere
            if op.get("op") == "remove" and op.get("path") in {"/parsed/technical_skills", "/parsed/skills"}:
                _remove_skill_everywhere(op.get("value"))

        # Debug: see in-memory skills before saving
        print("TECHNICAL_SKILLS BEFORE COMMIT:", parsed.get("technical_skills"))
        print("SKILLS BEFORE COMMIT:", parsed.get("skills"))
        print("SKILL_CATEGORIES BEFORE COMMIT:", parsed.get("skill_categories"))

        # Sync parsed fields into top-level Candidate columns (these drive /api/candidates and tables)
        try:
            merged_skills = []
            for key in ["skills", "technical_skills", "primary_skills"]:
                v = parsed.get(key)
                if isinstance(v, list):
                    merged_skills.extend(v)

            # de-dupe while preserving order
            seen = set()
            merged_skills = [x for x in merged_skills if not (_norm(x) in seen or seen.add(_norm(x)))]
            cand.skills = list(merged_skills)
            cand.projects = list(parsed.get("projects") or [])
            cand.work_experiences = list(parsed.get("work_experiences") or [])
            cand.education = list(parsed.get("education") or [])
            cand.certifications = list(parsed.get("certifications") or [])
            cand.languages = list(parsed.get("languages") or [])

            flag_modified(cand, "skills")
            flag_modified(cand, "projects")
            flag_modified(cand, "work_experiences")
            flag_modified(cand, "education")
            flag_modified(cand, "certifications")
            flag_modified(cand, "languages")
        except Exception as e:
            print("⚠️ Failed syncing parsed → candidate columns:", e)

        # Persist (ONLY ONCE!)
        cand.parsed = parsed
        flag_modified(cand, "parsed")
        db.session.add(cand)
        db.session.commit()

        # Verify persistence by reloading the row from the DB
        try:
            fresh = Candidate.query.get(target_id)
            fresh_parsed = fresh.parsed
            if isinstance(fresh_parsed, str):
                try:
                    fresh_parsed = json.loads(fresh_parsed)
                except Exception:
                    fresh_parsed = {}
            print("✅ DB RELOAD skills:", getattr(fresh, "skills", None))
            print("✅ DB RELOAD parsed.skills:", (fresh_parsed or {}).get("skills") if isinstance(fresh_parsed, dict) else None)
            print("✅ DB RELOAD parsed.technical_skills:", (fresh_parsed or {}).get("technical_skills") if isinstance(fresh_parsed, dict) else None)
        except Exception as e:
            print("⚠️ Failed DB reload verification:", e)

        # ✅ Clear any cached query results for this candidate
        if hasattr(self, "query_cache") and self.query_cache:
            keys_to_remove = []
            for cache_key in list(self.query_cache.keys()):
                cache_key_lower = str(cache_key).lower()
                if (str(cand.id) in cache_key_lower or
                        (cand.full_name and cand.full_name.lower() in cache_key_lower)):
                    keys_to_remove.append(cache_key)

            for key in keys_to_remove:
                del self.query_cache[key]
                print(f"🧹 CLEARED CACHE KEY: {key}")

            if not keys_to_remove:
                self.query_cache.clear()
                print("🧹 CLEARED ENTIRE QUERY CACHE (no specific keys matched)")

        # Debug: see in-memory skills after saving
        print("TECHNICAL_SKILLS AFTER COMMIT:", (cand.parsed or {}).get("technical_skills"))
        print("SKILLS AFTER COMMIT:", (cand.parsed or {}).get("skills"))
        print("SKILL_CATEGORIES AFTER COMMIT:", (cand.parsed or {}).get("skill_categories"))

        # 5) Build confirmation message + structured payload for UI card
        short_msg = patch.get("message") or "Changes applied successfully."

        summary = {
            "id": cand.id,
            "name": cand.full_name,
            "email": cand.email,
            "phone": cand.phone,
            "primary_role": cand.primary_role,
            "experience_years": cand.total_experience_years,
            "technical_skills": (cand.parsed or {}).get("technical_skills") or [],
            "skill_categories": (cand.parsed or {}).get("skill_categories") or [],
        }

        message = f"{short_msg}\n\nHere is the updated candidate profile."

        structured = {
            "type": "edit_summary",
            "candidate": summary,
        }

        return message, structured
    
    def _extract_skills_from_jd(self, jd_text: str) -> list:
        """Extract JD skills"""
        if not jd_text:
            return []
        
        # Parse skills from JD.skills column too
        jd_skills = []
        
        # From JD.skills JSON
        if hasattr(self, 'jd_record') and self.jd_record.skills:
            try:
                skills_json = json.loads(self.jd_record.skills)
                jd_skills.extend(skills_json.get("skills", []))
            except:
                pass
        
        # Keyword match
        keywords = ["python", "sql", "aws", "data analysis", "statistics", "tableau", "power bi"]
        jd_skills.extend([k for k in keywords if k in jd_text.lower()])
        
        return list(set(jd_skills))[:10]

    def _get_jd_by_sid(self, sid: str) -> dict:
        """
        Get COMPLETE JD record (ALL columns) by sid
        """
        jd_record = JD.query.filter_by(sid=sid).first()
        if not jd_record:
            return {"error": f"JD sid={sid} not found"}
        
        # ✅ ALL JD columns
        jd_full = {
            "sid": jd_record.sid,
            "job_description": jd_record.job_description or "",
            "designation": jd_record.designation or "",
            "competency": jd_record.competency or "",
            "sub_practice_name": jd_record.sub_practice_name or "",
            "sub_bu": jd_record.sub_bu or "",
            "account": jd_record.account or "",
            "project": jd_record.project or "",
            "skills": jd_record.skills or "",
            "billability": jd_record.billability or "",
            "position_type": jd_record.position_type or "",
            "location_type": jd_record.location_type or "",
            "base_location_city": jd_record.base_location_city or "",
            "ctc_rate": jd_record.ctc_rate or "",
            "parsed": getattr(jd_record, 'parsed', {}) or {},
            "remarks": jd_record.remarks or "",
            "created_at": str(jd_record.created_at) if jd_record.created_at else ""
        }
        
        # Parse skills JSON
        if jd_full["skills"]:
            try:
                jd_full["parsed_skills"] = json.loads(jd_full["skills"]).get("skills", [])
            except:
                jd_full["parsed_skills"] = []
        
        print(f"📄 FULL JD #{sid}: {jd_full['designation']} | Skills: {len(jd_full.get('parsed_skills', []))}")
        return jd_full

    def _handle_jd_lookup(self, user_message: str, history: List[ChatMessage]):
        """
        #52810 → Full JD details JSON
        """
        import re
        sid = re.search(r'#(\d+)', user_message)
        sid = sid.group(1) if sid else None
        
        if not sid:
            return None  # Not a JD lookup
        
        jd_record = JD.query.filter_by(sid=sid).first()
        if not jd_record:
            return {
                "text": f"❌ JD #{sid} not found",
                "structured": {"type": "jd_not_found", "sid": sid}
            }
        
        # FULL JD JSON
        jd_json = {
            "sid": jd_record.sid,
            "designation": jd_record.designation,
            "job_description": jd_record.job_description,
            "competency": jd_record.competency,
            "sub_practice_name": jd_record.sub_practice_name,
            "project": jd_record.project,
            "skills": jd_record.skills,
            "billability": jd_record.billability,
            "ctc_rate": jd_record.ctc_rate,
            "base_location_city": jd_record.base_location_city,
            "parsed": getattr(jd_record, 'parsed', {}),
            "remarks": jd_record.remarks
        }
        
        text = f"**JD #{sid}: {jd_json['designation']}**\n\n📄 {jd_json['job_description'][:200]}...\n\n💼 {jd_json['competency']} | {jd_json['sub_practice_name']}"
        
        return {
            "text": text,
            "structured": {
                "type": "jd_details",
                "sid": sid,
                "jd_json": jd_json
            }
        }

    def _extract_team_intent(self, query: str) -> Dict[str, Any]:
        """Extract intent for team queries using LLM."""
        prompt = f"""Extract intent from team management query: "{query}"
        
    Return JSON:
    {{
    "type": "projects|availability|allocations|general",
    "person": "name if mentioned, else null"
    }}"""
        
        try:
            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            return json.loads(response.choices[0].message.content)
        except:
            return {"type": "general", "person": None}

    def _get_team_projects(self) -> Dict[str, Any]:
        """Get all active projects."""
        # TODO: Query your projects database/table
        return {
            "message": "Active Projects:\n- Resume Screening Pro (5 members)\n- Data Pipeline V2 (3 members)\n- Analytics Dashboard (2 members)",
            "type": "text"
        }

    def _get_team_availability(self) -> Dict[str, Any]:
        """Get team member availability."""
        # TODO: Query availability from database
        return {
            "message": "Available Team Members:\n- Sarah (Data Scientist) - 20h/week\n- Mike (Data Engineer) - Full time\n- Lisa (Analyst) - 15h/week",
            "type": "text"
        }

    def _get_team_allocations(self, person: Optional[str]) -> Dict[str, Any]:
        """Get project allocations for a person."""
        if person:
            return {
                "message": f"{person}'s Current Projects:\n- Resume Screening Pro (50%)\n- Analytics Dashboard (30%)\n- Available: 20%",
                "type": "text"
            }
        return self._get_team_availability()


    def handle_message(self, user_message: str, session_uuid: str = None, conversation_history: list = None) -> dict:
    # Just forward properly
        resp = self.handle_chat(user_message, session_uuid=session_uuid, conversation_history=conversation_history)

        # Normalize tuple responses: (message, structured)
        if isinstance(resp, tuple) and len(resp) == 2:
            msg, structured = resp
            return {
                "session_id": session_uuid,
                "message": msg,
                "structured": structured,
            }

        return resp

    def _handle_team_management(self, intent: Dict, user_message: str, history: List[Dict]) -> Tuple[Dict, Dict]:
        """Handle team management queries."""
        
        team_intent = self._extract_team_intent(user_message)
        
        if team_intent["type"] == "projects":
            result = self._get_team_projects()
        elif team_intent["type"] == "availability":
            result = self._get_team_availability()
        elif team_intent["type"] == "allocations":
            result = self._get_team_allocations(team_intent.get("person"))
        else:
            result = {
                "message": "**Team Management Features:**\n\n" +
                        "- 📊 View projects: *'show all projects'*\n" +
                        "- ✅ Check availability: *'who is available?'*\n" +
                        "- 👤 View allocations: *'what is [name] working on?'*\n\n" +
                        "This feature is under construction. Coming soon!",
                "type": "text"
            }
        
        structured = {
            "type": result.get("type", "text"),
            "message": result.get("message", ""),
            "data": result.get("data", {})
        }
        
        return result, structured


    def _extract_team_intent(self, query: str) -> Dict[str, Any]:
        """Extract intent for team queries using LLM."""
        
        prompt = f"""Extract intent from team management query: "{query}"
        
    Return JSON with:
    {{
    "type": "projects|availability|allocations|general",
    "person": "name if mentioned, else null"
    }}

    Examples:
    - "show all projects" -> {{"type": "projects", "person": null}}
    - "who is available?" -> {{"type": "availability", "person": null}}
    - "what is John working on?" -> {{"type": "allocations", "person": "John"}}

    Return ONLY valid JSON."""
        
        try:
            response = self.llm.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are an intent extraction AI. Return ONLY JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=200
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"❌ Team intent extraction failed: {e}")
            return {"type": "general", "person": None}


    def _get_team_projects(self) -> Dict[str, Any]:
        """Get all active projects."""
        return {
            "message": "🚧 **Team Projects** (Coming Soon)\n\n" +
                    "This feature will show:\n" +
                    "- Active projects with team members\n" +
                    "- Project timelines and deadlines\n" +
                    "- Resource allocation percentages\n" +
                    "- Project status and updates",
            "type": "text",
            "data": {"projects": []}
        }


    def _get_team_availability(self) -> Dict[str, Any]:
        """Get team member availability."""
        return {
            "message": "🚧 **Team Availability** (Coming Soon)\n\n" +
                    "This feature will show:\n" +
                    "- Available team members\n" +
                    "- Current capacity (hours/week)\n" +
                    "- Upcoming availability\n" +
                    "- Skill-based availability",
            "type": "text",
            "data": {"availability": []}
        }


    def _get_team_allocations(self, person: Optional[str]) -> Dict[str, Any]:
        """Get project allocations for a person."""
        if person:
            return {
                "message": f"🚧 **{person}'s Allocations** (Coming Soon)\n\n" +
                        "This feature will show:\n" +
                        f"- {person}'s current projects\n" +
                        "- Allocation percentages\n" +
                        "- Time commitments\n" +
                        "- Available capacity",
                "type": "text",
                "data": {"person": person, "allocations": []}
            }
        else:
            return self._get_team_availability()


    def handle_message(self, user_message: str, session_uuid: str = None) -> Dict:
        """Backward compatibility wrapper for handle_chat."""
        return self.handle_chat(user_message, session_uuid)

    def _extract_team_intent(self, query: str) -> Dict[str, Any]:
        """Extract intent for team queries using LLM."""
        
        prompt = f"""Extract intent from team management query: "{query}"
        
    Return JSON with:
    {{
    "type": "projects|availability|allocations|general",
    "person": "name if mentioned, else null"
    }}

    Examples:
    - "show all projects" -> {{"type": "projects", "person": null}}
    - "who is available?" -> {{"type": "availability", "person": null}}
    - "what is John working on?" -> {{"type": "allocations", "person": "John"}}

    Return ONLY valid JSON."""
        
        try:
            response = self.llm.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are an intent extraction AI. Return ONLY JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=200
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"❌ Team intent extraction failed: {e}")
            return {"type": "general", "person": None}


    def _get_team_projects(self) -> Dict[str, Any]:
        """Get all active projects."""
        return {
            "message": "🚧 **Team Projects** (Coming Soon)\n\n" +
                    "This feature will show:\n" +
                    "- Active projects with team members\n" +
                    "- Project timelines and deadlines\n" +
                    "- Resource allocation percentages\n" +
                    "- Project status and updates",
            "type": "text",
            "data": {"projects": []}
        }


    def _get_team_availability(self) -> Dict[str, Any]:
        """Get team member availability."""
        return {
            "message": "🚧 **Team Availability** (Coming Soon)\n\n" +
                    "This feature will show:\n" +
                    "- Available team members\n" +
                    "- Current capacity (hours/week)\n" +
                    "- Upcoming availability\n" +
                    "- Skill-based availability",
            "type": "text",
            "data": {"availability": []}
        }


    def _get_team_allocations(self, person: Optional[str]) -> Dict[str, Any]:
        """Get project allocations for a person."""
        if person:
            return {
                "message": f"🚧 **{person}'s Allocations** (Coming Soon)\n\n" +
                        "This feature will show:\n" +
                        f"- {person}'s current projects\n" +
                        "- Allocation percentages\n" +
                        "- Time commitments\n" +
                        "- Available capacity",
                "type": "text",
                "data": {"person": person, "allocations": []}
            }
        else:
            return self._get_team_availability()


    def handle_message(self, user_message: str, session_uuid: str = None) -> Dict:
        """Backward compatibility wrapper for handle_chat."""
        return self.handle_chat(user_message, session_uuid)

    
