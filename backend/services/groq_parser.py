from groq import Groq
import instructor
from models.resume_schema import ResumeData
from config.local_config import GROQ_API_KEY

def get_groq_client():
    """Get Groq client with instructor."""
    client = Groq(api_key=GROQ_API_KEY)
    return instructor.from_groq(client)

def parse_resume_with_groq(resume_text: str) -> ResumeData:
    """Parse resume with MAXIMUM extraction: Name, Email, Role, Experience Summary, Primary Skills, 
    Hierarchical Skills, Enhanced Projects with DATES, Certifications."""

    inst_client = get_groq_client()

    prompt = f"""
You are an EXPERT resume parser with EXTREME attention to detail.
Extract ALL information following the ResumeData schema EXACTLY.

==================== CRITICAL EXTRACTION RULES ====================

🔴 PRIORITY 1: CONTACT INFORMATION (NEVER MISS!)

Location: VERY FIRST LINES of resume (before any sections)
Extract these 3 fields FIRST:

1. candidate_name: Full name at TOP of resume
   Example: "Name: Abhay Pratap Singh" → extract "Abhay Pratap Singh"
   Example: "Abhay Pratap Singh" (standalone at top) → extract "Abhay Pratap Singh"
   NEVER return null if name exists in first 5 lines

2. email: Email address (look for @ symbol)
   Example: "Happiest Minds Email id: abhay.pratap@happiestminds.com"
   Example: "Email: avikatoch1211@gmail.com"
   Extract: abhay.pratap@happiestminds.com
   NEVER return null if email exists

3. phone: Phone number
   Example: "Phone: +918374469079" or "+91-8374469079"
   Extract: +918374469079

CRITICAL: Scan the FIRST 10 LINES of resume for these fields!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

0. NEVER INVENT DATA
- Extract ONLY what exists in the resume text
- If field missing → set to null/empty
- NEVER fabricate "John Doe" or placeholder names
- NEVER make up example data

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. EXPERIENCE SUMMARY

Location: Usually FIRST section after contact info
Look for: "Experience Summary:", "Professional Summary:"

Example:
"▪ I received training in Data Engineering with Microsoft Azure and worked on a capstone 
project focused on data analysis using PySpark, ADLS, ADB, ADF, SQL.
▪ As an Associate Data Scientist, I collaborated in research and document unique domain-specific 
use cases of Generative AI..."

Extract AS-IS → experience_summary field

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

2. PRIMARY SKILLS (5-10 items at TOP)

Section: "Primary Skills:", "Key Skills:"

Example:
"Primary Skills:
• Data Engineering with Azure
• Reinforcement Learning using Python
• Machine Learning with Python
• Git
• Gen AI"

Extract as list: primary_skills = ["Data Engineering with Azure", "Reinforcement Learning using Python", ...]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

3. HIERARCHICAL TECHNICAL SKILLS

Section: "Technical Skills:" with subsections

Example:
"• Database Systems:
  o MySQL, HiveQL, Microsoft SQL Server
• Big Data Platforms:
  o Apache Spark, Azure Hadoop"

Extract:
skill_categories = [
  {{"category": "Database Systems", "skills": ["MySQL", "HiveQL", "Microsoft SQL Server"]}},
  {{"category": "Big Data Platforms", "skills": ["Apache Spark", "Azure Hadoop"]}}
]

ALSO: technical_skills = flat list of ALL skills

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

4. PROJECTS 🔴 WITH DATE EXTRACTION! (CRITICAL)

For EACH project extract ALL 7 fields:

1. name: "Ryder" (clean name without dates)
2. description: Full text about the project
3. role: "Data Analyst", "Senior Data Engineer"
4. responsibilities: ["Created SSIS packages...", "Optimized stored procedures..."]
5. technical_tools: ["SSMS", "Power BI", "Snowflake", "Git"]
6. start_date: 🔴 EXTRACT FROM PROJECT TITLE/DESCRIPTION
7. end_date: 🔴 EXTRACT FROM PROJECT TITLE/DESCRIPTION

🔴 DATE EXTRACTION RULES (CRITICAL!):

Look for dates in THESE LOCATIONS:
✅ Project title with parentheses: "Ryder (June 2024 – December 2024)"
   → name: "Ryder"
   → start_date: "June 2024"
   → end_date: "December 2024"

✅ Project title with dash: "Project 1: Ryder (June 2024 – December 2024)"
   → Extract dates from parentheses

✅ Dates in description: "Description of the Project: Designed and implemented..."
   → Check if first line has dates like "(May 2024 - June 2024)"

✅ Common date formats:
   - "June 2024 – December 2024"
   - "(June 2024 – December 2024)"
   - "May 2024 - June 2024"
   - "(February 2024 – March 2024)"
   - "Jan 2023 - Present"

🔴 DATE EXTRACTION EXAMPLES:

Example 1:
"Project 1: Ryder (June 2024 – December 2024)
Description: Designed and implemented changes in Power BI Reports..."

Extract:
- name: "Ryder"
- start_date: "June 2024"
- end_date: "December 2024"
- description: "Designed and implemented changes in Power BI Reports..."

Example 2:
"Project 2: EBE Power Platform (May 2024 – June 2024)
Description: Created SSIS packages..."

Extract:
- name: "EBE Power Platform"
- start_date: "May 2024"
- end_date: "June 2024"
- description: "Created SSIS packages..."

Example 3:
"Project 3: Forever New (February 2024 – March 2024)
Description: Created and migrated Power BI Reports..."

Extract:
- name: "Forever New"
- start_date: "February 2024"
- end_date: "March 2024"
- description: "Created and migrated Power BI Reports..."

Example 4:
"Current Project: Data Pipeline
Description: Building real-time data pipeline..."

Extract:
- name: "Data Pipeline"
- start_date: null
- end_date: "Present"
- description: "Building real-time data pipeline..."

Example 5:
"Legacy System Migration
Description: Migrated old system to new platform..."

Extract:
- name: "Legacy System Migration"
- start_date: null  (no dates visible)
- end_date: null    (will default to archived)
- description: "Migrated old system to new platform..."

🔴 IMPORTANT:
- ALWAYS check project title for dates in parentheses FIRST
- Remove date information from name field (clean name only)
- If dates exist, ALWAYS extract both start_date and end_date
- If project ongoing: end_date = "Present"
- If NO dates found: start_date = null, end_date = null (will be archived)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

5. CERTIFICATIONS AND TRAININGS (NEW!)

Section: "Certificate and Trainings:", "Certifications:"

Example:
"Data Engineering with Azure Stack Route | Stack Route | 16th Oct, 2023 – 8th Dec, 2023"

Extract:
certifications = [
  {{
    "name": "Data Engineering with Azure Stack Route",
    "issued_by": "Stack Route (In Association with Happiest Minds)",
    "issued_date": "16th Oct, 2023 – 8th Dec, 2023"
  }}
]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

6. WORK EXPERIENCE

Extract all jobs with:
- company_name, job_title, start_date, end_date
- responsibilities (ALL bullet points)
- achievements ("40% cost reduction", "25% accuracy improvement")
- technologies_used

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

7. EDUCATION

Extract: institution, degree, field_of_study, graduation_year, gpa

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

8. TOTAL EXPERIENCE & PRIMARY ROLE

- total_experience_years: Calculate from dates OR look for "Total Industry Experience: 1 Years & 7 Months" → 1.58
- primary_role: Most recent job_title from work_experiences OR role from latest project

====================================================

==================== RESUME TEXT ====================

{resume_text}

====================================================

Extract complete JSON following ResumeData schema.

🔴 EXTRACTION PRIORITY:
1. candidate_name (FIRST LINE)
2. email (@ symbol)
3. phone
4. primary_role (latest job title)
5. Experience Summary
6. Primary Skills
7. Projects (name, description, role, responsibilities, technical_tools, 🔴 start_date, 🔴 end_date)
8. Hierarchical skills
9. Certifications
10. Work experience, education

🔴 REMINDER: For projects, ALWAYS check title for dates like "(June 2024 – December 2024)" and extract them!
"""

    try:
        response = inst_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a precise resume parser extracting MAXIMUM data for ranking. "
                        "NEVER skip: 1) candidate_name, 2) email, 3) primary_role, "
                        "4) Experience Summary, 5) Primary Skills (5-10), "
                        "6) Projects (name, description, role, responsibilities LIST, technical_tools LIST, start_date, end_date), "
                        "7) Hierarchical skill categories, 8) Certifications with dates, "
                        "9) Work experience with achievements. "
                        "🔴 CRITICAL: Extract project dates from title/description like '(June 2024 – December 2024)'. "
                        "NEVER invent data. Return 0.0 for total_experience_years if unknown."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            response_model=ResumeData,
            temperature=0.1,
            max_tokens=14000,
        )
        return response
    except Exception as e:
        print(f"❌ Error parsing resume with Groq: {str(e)}")
        raise


def validate_parsed_data(parsed_data: ResumeData) -> dict:
    """Enhanced validation with ALL new fields including certifications and project dates."""
    
    def safe_sum(items, attr):
        """Sum attribute values, treating None as 0"""
        total = 0
        for item in items:
            val = getattr(item, attr, None)
            if val is not None:
                total += val
        return total
    
    def safe_len(lst):
        """Get length of list, treating None as 0"""
        if lst is None:
            return 0
        return len(lst)
    
    stats = {
        "candidate_name": parsed_data.candidate_name or "Unknown",
        "email": parsed_data.email or "Not found",
        "phone": parsed_data.phone or "Not found",
        
        # NEW: Experience Summary
        "has_experience_summary": bool(
            parsed_data.experience_summary or parsed_data.professional_summary
        ),
        
        # NEW: Primary Skills
        "primary_skills_count": len(parsed_data.primary_skills or []),
        
        # NEW: Hierarchical Skills
        "skill_categories_count": len(parsed_data.skill_categories or []),
        "skill_categories_breakdown": [
            {
                "category": cat.category,
                "skills_count": len(cat.skills or [])
            }
            for cat in (parsed_data.skill_categories or [])
        ],
        
        # Projects with enhanced tracking including dates
        "total_projects": len(parsed_data.projects or []),
        "projects_with_description": sum(
            1 for p in (parsed_data.projects or [])
            if p.description
        ),
        "projects_with_role": sum(
            1 for p in (parsed_data.projects or [])
            if p.role
        ),
        "projects_with_responsibilities": sum(
            1 for p in (parsed_data.projects or [])
            if p.responsibilities and len(p.responsibilities) > 0
        ),
        "projects_with_technical_tools": sum(
            1 for p in (parsed_data.projects or [])
            if (p.technical_tools and len(p.technical_tools) > 0) or 
               (p.technologies_used and len(p.technologies_used) > 0)
        ),
        "projects_with_dates": sum(
            1 for p in (parsed_data.projects or [])
            if p.start_date or p.end_date
        ),
        "project_breakdown": [
            {
                "name": proj.name or "Unnamed Project",
                "has_description": bool(proj.description),
                "has_role": bool(proj.role),
                "responsibilities_count": safe_len(proj.responsibilities),
                "technical_tools_count": len(proj.technical_tools or proj.technologies_used or []),
                "has_dates": bool(proj.start_date or proj.end_date),
                "start_date": proj.start_date,
                "end_date": proj.end_date,
                "has_impact": bool(getattr(proj, 'impact', None)),
            }
            for proj in (parsed_data.projects or [])
        ],
        
        # NEW: Certifications
        "certifications_count": len(parsed_data.certifications or []),
        "certifications_breakdown": [
            {
                "name": cert.name,
                "has_issuer": bool(cert.issued_by),
                "has_date": bool(cert.issued_date)
            }
            for cert in (parsed_data.certifications or [])
        ],
        
        # Work experience
        "total_jobs": len(parsed_data.work_experiences or []),
        "total_responsibilities": sum(
            safe_len(exp.responsibilities) 
            for exp in (parsed_data.work_experiences or [])
        ),
        "total_achievements": sum(
            safe_len(getattr(exp, 'achievements', None)) 
            for exp in (parsed_data.work_experiences or [])
        ),
        "jobs_breakdown": [
            {
                "company": exp.company_name or "Unknown",
                "title": exp.job_title or "Unknown",
                "duration_months": exp.duration_months or 0,
                "responsibilities_count": safe_len(exp.responsibilities),
                "achievements_count": safe_len(getattr(exp, 'achievements', None)),
            }
            for exp in (parsed_data.work_experiences or [])
        ],
        
        # Experience and skills
        "total_experience_years": parsed_data.total_experience_years or 0.0,
        "primary_role": parsed_data.primary_role or "Not found",
        "education_count": len(parsed_data.education or []),
        "technical_skills_count": len(parsed_data.technical_skills or []),
        "has_contact_info": bool(parsed_data.email and parsed_data.phone),
    }
    return stats
