from pydantic import BaseModel, Field, validator
from typing import List, Optional
from datetime import datetime


# ==================== UTILITY FUNCTIONS ====================

def clean_null_string(value):
    """Convert string 'null' or empty string to None"""
    if value == "null" or value == "" or value is None:
        return None
    return value


def clean_null_list(value):
    """Remove 'null' strings from lists and return empty list if None"""
    if value is None:
        return []
    if isinstance(value, list):
        cleaned = [item for item in value if item != "null" and item != "" and item is not None]
        return cleaned if cleaned else []
    return []


def clean_null_int(value):
    """Convert string 'null' to None, else parse as int"""
    if value == "null" or value == "" or value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def clean_null_float(value):
    """Convert string 'null' to None, else parse as float"""
    if value == "null" or value == "" or value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


# ==================== SCHEMA CLASSES ====================

class TeamMember(BaseModel):
    """Team member information for project collaboration tracking"""
    name: str
    role: Optional[str] = None
    id: Optional[int] = None

    @validator('role', pre=True)
    def clean_role(cls, v):
        return clean_null_string(v)


class SkillCategory(BaseModel):
    """Hierarchical skill categorization - CRITICAL for your requirements"""
    category: str = Field(
        description="Category name (e.g., 'Database Systems', 'Big Data Platforms', 'Language/Platforms', 'Subject Area')"
    )
    skills: Optional[List[str]] = Field(
        default=None, 
        description="Skills under this category"
    )

    @validator('skills', pre=True)
    def clean_skills(cls, v):
        return clean_null_list(v)


class WorkExperience(BaseModel):
    """Individual work experience - ALL FIELDS OPTIONAL"""
    company_name: Optional[str] = Field(
        default=None,
        description="Exact company/organization name",
    )
    job_title: Optional[str] = Field(
        default=None,
        description="Exact job title/role",
    )
    start_date: Optional[str] = Field(
        default=None,
        description="Start date (format: 'Month Year' or 'YYYY')",
    )
    end_date: Optional[str] = Field(
        default=None,
        description="End date or 'Present'",
    )
    duration_months: Optional[int] = Field(
        default=None,
        description="Total months worked in this role",
    )
    location: Optional[str] = Field(
        default=None,
        description="Job location if mentioned",
    )
    responsibilities: Optional[List[str]] = Field(
        default=None,
        description="ALL bullet points/mission statements for this role",
    )
    technologies_used: Optional[List[str]] = Field(
        default=None,
        description="Technologies/tools mentioned for this role",
    )
    is_current: Optional[bool] = Field(
        default=False,
        description="True if currently working here",
    )
    achievements: Optional[List[str]] = Field(
        default=None,
        description="Quantified achievements (e.g., '40% cost reduction', '25% accuracy improvement')"
    )
    team_size: Optional[int] = Field(
        default=None,
        description="Team size led/managed"
    )
    impact_metrics: Optional[List[str]] = Field(
        default=None,
        description="Specific metrics (e.g., 'Processed 10TB/day', '35% CTR improvement')"
    )

    @validator('company_name', 'job_title', 'start_date', 'end_date', 'location', pre=True)
    def clean_string_fields(cls, v):
        return clean_null_string(v)

    @validator('duration_months', 'team_size', pre=True)
    def clean_int_fields(cls, v):
        return clean_null_int(v)

    @validator('responsibilities', 'technologies_used', 'achievements', 'impact_metrics', pre=True)
    def clean_list_fields(cls, v):
        return clean_null_list(v)

class Project(BaseModel):
    """Enhanced project with COMPLETE extraction - ALL FIELDS OPTIONAL except name"""
    name: Optional[str] = Field(
        default="Unnamed Project",
        description="EXACT project name (e.g., 'Ryder', 'EBE Power Platform')"
    )
    
    description: Optional[str] = Field(
        default=None, 
        description="""FULL project description including ALL details about what was done. 
        CRITICAL: If the description contains date ranges like 'June 2024 - December 2024' or '(May 2024 - June 2024)', 
        extract those dates and populate start_date and end_date fields. Keep the full description here."""
    )
    
    role: Optional[str] = Field(
        default=None, 
        description="Candidate's specific role (e.g., 'Data Analyst', 'Senior Data Engineer')"
    )
    
    responsibilities: Optional[List[str]] = Field(
        default=None, 
        description="LIST of what candidate DID (all numbered/bullet points under project)"
    )
    
    technical_tools: Optional[List[str]] = Field(
        default=None, 
        description="ALL tools/technologies mentioned for THIS specific project"
    )
    
    organization: Optional[str] = Field(
        default=None, 
        description="Client/company name if mentioned (e.g., 'Ryder', 'Forever New')"
    )
    
    # ✅ CRITICAL: Better date extraction with examples
    start_date: Optional[str] = Field(
        default=None, 
        description="""Project start date. LOOK FOR:
        - Date ranges in project title/description: '(June 2024 – December 2024)' → extract 'June 2024'
        - Parentheses after project name: 'Ryder (June 2024 – December 2024)' → 'June 2024'
        - Text phrases: 'from June 2024', 'started in June 2024', 'since June 2024'
        - Any format: 'June 2024', 'Jun 2024', '2024-06', '06/2024'
        ALWAYS extract if present in description or title."""
    )
    
    end_date: Optional[str] = Field(
        default=None, 
        description="""Project end date. LOOK FOR:
        - Date ranges: '(June 2024 – December 2024)' → extract 'December 2024'
        - Status words: 'Present', 'Current', 'Ongoing', 'In Progress'
        - Text phrases: 'to December 2024', 'until December 2024', 'ended December 2024'
        - Any format: 'December 2024', 'Dec 2024', '2024-12', '12/2024'
        If project is ongoing/current, use 'Present'."""
    )
    
    duration_months: Optional[int] = Field(
        default=None, 
        description="""Project duration in months. Calculate from start_date and end_date if both available.
        Examples: June 2024 to December 2024 = 7 months (inclusive)
        Also look for explicit mentions: '6 months project', '1 year' (12 months), '2.5 years' (30 months)"""
    )
    
    technologies_used: Optional[List[str]] = Field(
        default=None, 
        description="Technologies (backward compatibility with technical_tools)"
    )
    
    is_academic: Optional[bool] = Field(
        default=False, 
        description="True if university/college project"
    )
    
    contribution: Optional[str] = Field(
        default=None, 
        description="Candidate's specific contribution summary"
    )
    
    impact: Optional[str] = Field(
        default=None, 
        description="Quantified results/impact with metrics"
    )
    
    team_size: Optional[int] = Field(
        default=None, 
        description="Team size if mentioned"
    )
    
    team_members: Optional[List[TeamMember]] = Field(
        default=None, 
        description="Team members (ONLY if names explicitly mentioned)"
    )

    @validator('name', 'role', 'organization', 'description', 'start_date', 'end_date', 
               'contribution', 'impact', pre=True)
    def clean_string_fields(cls, v):
        if v is None:
            return None
        return clean_null_string(v)

    @validator('team_size', 'duration_months', pre=True)
    def clean_int_fields(cls, v):
        return clean_null_int(v)

    @validator('responsibilities', 'technical_tools', 'technologies_used', pre=True)
    def clean_list_fields(cls, v):
        return clean_null_list(v)

class Certification(BaseModel):
    """Certifications and Trainings - NEW REQUIREMENT"""
    name: str = Field(
        description="Certification/training name (e.g., 'Data Engineering with Azure Stack Route')"
    )
    issued_by: Optional[str] = Field(
        default=None, 
        description="Issuing organization (e.g., 'Stack Route', 'Databricks')"
    )
    issued_date: Optional[str] = Field(
        default=None, 
        description="Issue/completion date (e.g., '16th Oct, 2023 – 8th Dec, 2023', 'Oct 2023')"
    )
    issued_month: Optional[str] = Field(
        default=None, 
        description="Issue month if only month provided"
    )
    expiry_date: Optional[str] = Field(
        default=None, 
        description="Expiry date if mentioned"
    )
    credential_id: Optional[str] = Field(
        default=None, 
        description="Credential ID/certificate number"
    )
    description: Optional[str] = Field(
        default=None,
        description="Training description or topics covered"
    )

    @validator('issued_by', 'issued_date', 'issued_month', 'expiry_date', 'credential_id', 'description', pre=True)
    def clean_string_fields(cls, v):
        return clean_null_string(v)


class Education(BaseModel):
    """Individual education entry - ALL FIELDS OPTIONAL"""
    institution: Optional[str] = Field(default=None, description="University/college/school name")
    degree: Optional[str] = Field(default=None, description="Degree type")
    qualification: Optional[str] = Field(default=None, description="Alternative to degree")
    field_of_study: Optional[str] = Field(default=None, description="Major/specialization")
    field: Optional[str] = Field(default=None, description="Alternative to field_of_study")
    start_date: Optional[str] = Field(default=None, description="Start date")
    end_date: Optional[str] = Field(default=None, description="Graduation date")
    graduation_year: Optional[str] = Field(default=None, description="Graduation year")
    year: Optional[str] = Field(default=None, description="Year")
    gpa: Optional[float] = Field(default=None, description="GPA/percentage")
    achievements: Optional[List[str]] = Field(default=None, description="Academic honors")
    relevant_coursework: Optional[List[str]] = Field(default=None, description="Relevant courses")

    @validator('institution', 'degree', 'qualification', 'field_of_study', 'field', 
               'start_date', 'end_date', 'graduation_year', 'year', pre=True)
    def clean_string_fields(cls, v):
        return clean_null_string(v)

    @validator('gpa', pre=True)
    def clean_gpa(cls, v):
        return clean_null_float(v)

    @validator('achievements', 'relevant_coursework', pre=True)
    def clean_list_fields(cls, v):
        return clean_null_list(v)


class ResumeData(BaseModel):
    """Complete structured resume data - EVERYTHING OPTIONAL"""

    # Personal Info - ALL OPTIONAL
    candidate_name: Optional[str] = Field(default=None, description="Full name of candidate")
    email: Optional[str] = Field(default=None, description="Email address")
    phone: Optional[str] = Field(default=None, description="Phone number")
    linkedin: Optional[str] = Field(default=None, description="LinkedIn profile URL")
    github: Optional[str] = Field(default=None, description="GitHub profile URL")
    portfolio: Optional[str] = Field(default=None, description="Portfolio/personal website")
    location: Optional[str] = Field(default=None, description="Current location/city")

    # NEW REQUIREMENT: Experience Summary
    experience_summary: Optional[str] = Field(
        default=None,
        description="Experience Summary paragraph (usually at TOP of resume after contact info)"
    )
    professional_summary: Optional[str] = Field(
        default=None,
        description="Professional Summary/Career objective (alternative to experience_summary)"
    )

    # NEW REQUIREMENT: Primary Skills (top-level)
    primary_skills: Optional[List[str]] = Field(
        default=None,
        description="Primary/Key Skills listed prominently at top (5-10 items)"
    )

    # Work Experience - OPTIONAL
    work_experiences: Optional[List[WorkExperience]] = Field(
        default=None,
        description="SEPARATE WorkExperience object for EACH job"
    )

    # NEW REQUIREMENT: Projects with ALL 4 fields
    projects: Optional[List[Project]] = Field(
        default=None,
        description="All projects with Description, Role, Responsibilities (list), Technical Tools (list)"
    )

    # Education - OPTIONAL
    education: Optional[List[Education]] = Field(
        default=None,
        description="All education entries"
    )

    # NEW REQUIREMENT: Hierarchical Technical Skills
    skill_categories: Optional[List[SkillCategory]] = Field(
        default=None,
        description="Skills organized in categories (Database Systems, Big Data Platforms, Languages, etc.)"
    )

    # Skills (Flat lists) - ALL OPTIONAL
    technical_skills: Optional[List[str]] = Field(
        default=None,
        description="All technical skills combined (flat list from all categories)"
    )
    soft_skills: Optional[List[str]] = Field(
        default=None,
        description="Soft skills (leadership, communication, etc.)"
    )
    skills: Optional[List[str]] = Field(
        default=None,
        description="General skills list"
    )

    # NEW REQUIREMENT: Certifications and Trainings
    certifications: Optional[List[Certification]] = Field(
        default=None,
        description="ALL certifications, trainings, courses with name, issued_by, issued_date"
    )

    # Languages - OPTIONAL
    languages: Optional[List[str]] = Field(
        default=None,
        description="Languages spoken"
    )

    # Career-wide achievements - ALL OPTIONAL
    achievements: Optional[List[str]] = Field(
        default=None,
        description="Major career achievements across all roles"
    )
    leadership_roles: Optional[List[str]] = Field(
        default=None,
        description="Roles/titles indicating leadership"
    )
    impact_metrics: Optional[List[str]] = Field(
        default=None,
        description="Key metrics/quantified results"
    )

    # Calculated Fields - OPTIONAL with defaults
    total_experience_years: Optional[float] = Field(
        default=0.0,
        description="Sum of all work experience durations in years"
    )
    primary_role: Optional[str] = Field(
        default=None,
        description="Most recent/current job title"
    )
    primary_domain: Optional[str] = Field(
        default=None,
        description="Primary technical domain (Data Engineering, Machine Learning, etc.)"
    )


    # ==================== VALIDATORS ====================

    @validator('candidate_name', 'email', 'phone', 'linkedin', 'github', 'portfolio', 'location',
               'experience_summary', 'professional_summary', 'primary_role', 'primary_domain', pre=True)
    def clean_string_fields(cls, v):
        return clean_null_string(v)

    @validator('primary_skills', 'technical_skills', 'soft_skills', 'skills', 
               'languages', 'achievements', 'leadership_roles', 'impact_metrics', pre=True)
    def clean_list_fields(cls, v):
        """All list fields - convert None to empty list"""
        if v is None:
            return []
        return clean_null_list(v)

    @validator('total_experience_years', pre=True)
    def clean_total_experience(cls, v):
        result = clean_null_float(v)
        return result if result is not None else 0.0

    @validator('work_experiences', 'projects', pre=True)
    def clean_object_lists(cls, v):
        """Clean work experiences and projects"""
        if v is None:
            return []
        if isinstance(v, list):
            return [item for item in v if item is not None]
        return []

    @validator('education', pre=True)
    def clean_empty_education(cls, v):
        """Remove education entries where all fields are empty"""
        if not v:
            return []
        cleaned = []
        for edu in v:
            if isinstance(edu, dict):
                has_data = any(
                    edu.get(f) not in [None, "", "null"] 
                    for f in ['institution', 'degree', 'field', 'field_of_study', 'year', 'graduation_year']
                )
                if has_data:
                    cleaned.append(edu)
        return cleaned if cleaned else []

    @validator('skill_categories', pre=True)
    def clean_skill_categories(cls, v):
        """Clean skill categories"""
        if v is None:
            return []
        if isinstance(v, list):
            return [cat for cat in v if cat is not None]
        return []

    @validator('certifications', pre=True)
    def clean_certifications(cls, v):
        """Clean certifications - NEW"""
        if v is None:
            return []
        if isinstance(v, list):
            return [cert for cert in v if cert is not None]
        return []
