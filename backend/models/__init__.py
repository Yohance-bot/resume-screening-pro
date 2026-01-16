from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, Boolean

from extensions import db


class JobDescription(db.Model):
    __tablename__ = "job_description"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    domain = db.Column(db.String(100))
    min_experience_years = db.Column(db.Float)
    required_skills = db.Column(db.JSON, default=list)
    bonus_skills = db.Column(db.JSON, default=list)
    location = db.Column(db.String(200))
    employment_type = db.Column(db.String(50))
    seniority_level = db.Column(db.String(50))
    salary_min = db.Column(db.Float)
    salary_max = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "domain": self.domain,
            "min_experience_years": self.min_experience_years,
            "required_skills": self.required_skills or [],
            "bonus_skills": self.bonus_skills or [],
            "location": self.location,
            "employment_type": self.employment_type,
            "seniority_level": self.seniority_level,
            "salary_min": self.salary_min,
            "salary_max": self.salary_max,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Candidate(db.Model):
    __tablename__ = "candidate"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    full_name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200))
    phone = db.Column(db.String(50))
    raw_text = db.Column(db.Text)
    parsed = db.Column(db.JSON, default=dict)
    pdf_path = db.Column(db.String(500))
    linkedin = db.Column(db.String(300))
    github = db.Column(db.String(300))
    portfolio = db.Column(db.String(300))
    total_experience_years = db.Column(db.Float)
    primary_role = db.Column(db.String(200))
    primary_domain = db.Column(db.String(200))
    skills = db.Column(db.JSON, default=list)
    education = db.Column(db.JSON, default=list)
    work_experiences = db.Column(db.JSON, default=list)
    certifications = db.Column(db.JSON, default=list)
    languages = db.Column(db.JSON, default=list)
    projects = db.Column(db.JSON, default=list)
    source = db.Column(db.String(100))
    notes = db.Column(db.Text)
    role_bucket = db.Column(db.String(20), default="data_practice")
    on_bench = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        import json
        parsed = self.parsed
        if isinstance(parsed, str):
            try:
                parsed = json.loads(parsed)
            except Exception:
                parsed = {}
        if not isinstance(parsed, dict):
            parsed = {}

        return {
            "id": self.id,
            "full_name": self.full_name,
            "email": self.email,
            "phone": self.phone,
            "pdf_path": getattr(self, "pdf_path", None),
            "skills": self.skills or [],
            "education": self.education or [],
            "work_experiences": self.work_experiences or [],
            "certifications": self.certifications or [],
            "languages": self.languages or [],
            "sections": parsed.get("sections", {}),
            "summary": parsed.get("summary", ""),
            "parsed": parsed,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ScreeningResult(db.Model):
    __tablename__ = "screening_result"

    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey("job_description.id"), nullable=True)
    candidate_id = db.Column(db.String(64), db.ForeignKey("candidate.id"))
    stage = db.Column(db.Integer)
    final_score = db.Column(db.Float)
    llm_score = db.Column(db.Float)
    confidence = db.Column(db.Float)
    reasoning = db.Column(db.Text)
    strengths = db.Column(db.JSON, default=list)
    weaknesses = db.Column(db.JSON, default=list)
    recommendations = db.Column(db.JSON, default=list)
    passed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    candidate = db.relationship("Candidate", backref="screening_results")
    job_description = db.relationship("JobDescription", backref="screening_results")

    def to_dict(self):
        return {
            "id": self.id,
            "profile_id": self.profile_id,
            "candidate_id": self.candidate_id,
            "stage": self.stage,
            "final_score": self.final_score,
            "llm_score": self.llm_score,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "strengths": self.strengths or [],
            "weaknesses": self.weaknesses or [],
            "recommendations": self.recommendations or [],
            "passed": self.passed,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ProjectDB(db.Model):
    """Stores unique projects across all candidates"""
    __tablename__ = "project"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(300), nullable=False, index=True)
    organization = db.Column(db.String(200), index=True)
    start_date = db.Column(db.String(50))
    end_date = db.Column(db.String(50))
    duration_months = db.Column(db.Integer)
    is_academic = db.Column(db.Boolean, default=False)
    summary = db.Column(db.Text)
    all_technologies = db.Column(db.JSON, default=list)
    team_size_estimate = db.Column(db.Integer)
    total_contributors = db.Column(db.Integer, default=0)
    impact_metrics = db.Column(db.JSON, default=list)
    merged_into_id = db.Column(db.Integer, db.ForeignKey("project.id"), index=True)
    merged_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    contributions = db.relationship("CandidateProject", back_populates="project", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "organization": self.organization,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "duration_months": self.duration_months,
            "is_academic": self.is_academic,
            "summary": self.summary,
            "all_technologies": self.all_technologies or [],
            "team_size_estimate": self.team_size_estimate,
            "total_contributors": self.total_contributors,
            "impact_metrics": self.impact_metrics or [],
            "merged_into_id": self.merged_into_id,
            "merged_at": self.merged_at.isoformat() if self.merged_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class CandidateProject(db.Model):
    """Links candidates to projects with their specific contributions"""
    __tablename__ = "candidate_project"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    candidate_id = db.Column(db.Integer, db.ForeignKey("candidate.id", ondelete="CASCADE"), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id", ondelete="CASCADE"), nullable=False)
    role = db.Column(db.String(200))
    description = db.Column(db.Text)
    responsibilities = db.Column(db.JSON, default=list)
    technical_tools = db.Column(db.JSON, default=list)
    contribution = db.Column(db.Text)
    impact = db.Column(db.Text)
    candidate_start_date = db.Column(db.String(50))
    candidate_end_date = db.Column(db.String(50))
    candidate_duration_months = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    candidate = db.relationship("Candidate", backref="project_contributions")
    project = db.relationship("ProjectDB", back_populates="contributions")

    def to_dict(self):
        return {
            "id": self.id,
            "candidate_id": self.candidate_id,
            "project_id": self.project_id,
            "role": self.role,
            "description": self.description,
            "responsibilities": self.responsibilities or [],
            "technical_tools": self.technical_tools or [],
            "contribution": self.contribution,
            "impact": self.impact,
            "candidate_start_date": self.candidate_start_date,
            "candidate_end_date": self.candidate_end_date,
            "candidate_duration_months": self.candidate_duration_months,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ProjectMergeHistory(db.Model):
    __tablename__ = "project_merge_history"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    source_project_id = db.Column(db.Integer, db.ForeignKey("project.id", ondelete="CASCADE"), nullable=False, index=True)
    target_project_id = db.Column(db.Integer, db.ForeignKey("project.id", ondelete="CASCADE"), nullable=False, index=True)
    source_project_before = db.Column(db.JSON, default=dict)
    target_project_before = db.Column(db.JSON, default=dict)
    moved_links = db.Column(db.JSON, default=list)  # [{candidate_project_id, action, snapshot?}]
    llm_reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reversed_at = db.Column(db.DateTime)

    source_project = db.relationship("ProjectDB", foreign_keys=[source_project_id])
    target_project = db.relationship("ProjectDB", foreign_keys=[target_project_id])


# ✅ Chat models (keeping them here to avoid circular import)
class ChatSession(db.Model):
    __tablename__ = "chat_sessions"
    id = db.Column(db.Integer, primary_key=True)
    session_uuid = db.Column(db.String(36), unique=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("chat_sessions.id"))
    role = db.Column(db.String(20))  # "user" or "assistant"
    content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    session = db.relationship("ChatSession", backref="messages")



class JD(db.Model):
    __tablename__ = "jds"
    
    id = Column(Integer, primary_key=True)
    sid = Column(String(20), unique=True, nullable=False, index=True)
    
    # Core identifiers
    comments = Column(Text)
    sub_bu = Column(String(255))
    account = Column(String(255))
    project = Column(String(255))
    sub_practice_name = Column(String(255))
    
    # Job details
    competency = Column(String(255))
    designation = Column(String(255))
    job_description = Column(Text)
    skills = Column(Text)  # Added ✅
    
    # Billing
    billability = Column(String(255))
    billing_type = Column(String(255))
    probability = Column(Float)  # Numeric
    billed_pct = Column(String(255))  # "Billed %"
    project_type = Column(String(255))
    governance_category = Column(String(255))
    
    # Position/Location
    customer_interview = Column(String(255))
    position_type = Column(String(255))
    location_type = Column(String(255))
    base_location_country = Column(String(255))
    base_location_city = Column(String(255))
    facility = Column(String(255))
    fulfilment_type = Column(String(255))
    
    # Status
    approval_status = Column(String(255))
    sid_status = Column(String(255))
    identified_empid = Column(String(255))
    identified_empname = Column(String(255))
    
    # Dates (String for CSV flexibility)
    original_billable_date = Column(String(255))
    updated_billable_date = Column(String(255))
    billing_end_date = Column(String(255))
    requirement_expiry_date = Column(String(255))
    resource_required_date = Column(String(255))
    requirement_initiated_date = Column(String(255))
    
    month = Column(String(255))
    request_initiated_by = Column(String(255))
    dm = Column(String(255))
    bdm = Column(String(255))
    
    # Misc
    remarks = Column(Text)
    reason_for_cancel = Column(Text)
    reason_for_lost = Column(Text)
    replacement_employee = Column(String(255))
    urgent = Column(String(50))  # "Yes/No"
    ctc_rate = Column(String(255))  # "CTC / Rate"
    customer_reference_id = Column(String(255))
    billing_loss_status = Column(String(255))
    aging = Column(Float)  # Numeric
    action_items = Column(Text)
    
    parsed = Column(db.JSON, default=dict)  # LLM extras: required_skills etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<JD sid={self.sid} designation={self.designation}>"
