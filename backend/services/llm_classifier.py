def classify_file_content(text):
    """Simple heuristic: JD has 'requirements', 'responsibilities', etc."""
    jd_keywords = ['requirements', 'responsibilities', 'qualifications', 'experience required', 'must have']
    resume_keywords = ['experience', 'projects', 'education', 'linkedin', 'email']
    
    jd_score = sum(1 for kw in jd_keywords if kw.lower() in text.lower())
    resume_score = sum(1 for kw in resume_keywords if kw.lower() in text.lower())
    
    return 'job_description' if jd_score > resume_score else 'resume'
