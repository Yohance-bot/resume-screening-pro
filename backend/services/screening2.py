from datetime import datetime
from typing import Dict, Any, List, Tuple
import re
from services.skill_ontology import expand_skills, normalize

# Extended month name → number mapping
MONTH_MAP = {
    'jan': 1, 'january': 1,
    'feb': 2, 'february': 2,
    'mar': 3, 'march': 3,
    'apr': 4, 'april': 4,
    'may': 5,
    'jun': 6, 'june': 6,
    'jul': 7, 'july': 7,
    'aug': 8, 'august': 8,
    'sep': 9, 'sept': 9, 'september': 9,
    'oct': 10, 'october': 10,
    'nov': 11, 'november': 11,
    'dec': 12, 'december': 12,
}

def parse_date_flexible(s: str) -> float:
    """Parse various date formats → approximate year as float."""
    if not s or not isinstance(s, str):
        return None
    
    s = s.strip().lower()
    
    if s in {"present", "current", "now"}:
        return datetime.now().year + (datetime.now().month / 12.0)
    
    year_match = re.search(r'(\d{4})', s)
    if not year_match:
        return None
    
    year = float(year_match.group(1))
    
    month_match = re.search(r'(\w{3,})\s*(?:\d{4})?', s)
    if month_match:
        month_name = month_match.group(1).lower().strip()
        if month_name in MONTH_MAP:
            month_frac = MONTH_MAP[month_name] / 12.0
            return year + month_frac
    
    return year

def score_role_relevance(role: Dict, jd_required: List[str], candidate_skills: List[str] = None) -> Dict:
    """Score how well one role matches JD requirements."""
    # Use candidate-level skills as fallback
    role_skills_raw = (role.get("skills", []) or 
                      candidate_skills or 
                      role.get("description", "").split())
    role_skills = expand_skills(role_skills_raw)
    jd_skills = {normalize(s) for s in jd_required}
    
    matched = role_skills & jd_skills
    relevance = len(matched) / max(len(jd_skills), 1) * 100
    
    # Fake experience flags
    flags = []
    title = role.get("title", "").lower()
    company = role.get("company", "").lower()
    
    if any(word in title for word in ["intern", "trainee", "fresher"]):
        flags.append("entry_level")
    if len(title) < 3 or len(company) < 3:
        flags.append("suspicious_short")
    
    return {
        "relevance": round(relevance, 1),
        "matched_skills": list(matched),
        "flags": flags,
    }

from datetime import datetime
import re

def parse_date_flexible(date_str):
    """Parse various date formats into a year (int)"""
    if not date_str or not isinstance(date_str, str):
        return None
    
    date_str = date_str.strip().lower()
    
    # Handle "ongoing", "present", "current", "till date"
    if any(word in date_str for word in ["ongoing", "present", "current", "till date"]):
        return datetime.now().year
    
    # Try to extract year (4 digits)
    year_match = re.search(r'\b(19|20)\d{2}\b', date_str)
    if year_match:
        return int(year_match.group())
    
    # Try common formats
    formats = [
        "%b %Y",      # Oct 2019
        "%B %Y",      # October 2019
        "%m/%Y",      # 10/2019
        "%Y-%m-%d",   # 2019-10-01
        "%Y",         # 2019
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).year
        except:
            continue
    
    return None

def parse_duration_string(duration_str):
    """Parse 'Oct 2019 - Ongoing' into (start_year, end_year)"""
    if not duration_str or not isinstance(duration_str, str):
        return (None, None)
    
    # Split on common separators
    parts = re.split(r'\s*[-–—to]\s*', duration_str, maxsplit=1)
    
    if len(parts) == 2:
        start = parse_date_flexible(parts[0])
        end = parse_date_flexible(parts[1])
        return (start, end)
    elif len(parts) == 1:
        # Single date
        year = parse_date_flexible(parts[0])
        return (year, year)
    
    return (None, None)

def analyze_experience(roles, jd_required_skills, candidate_skills):
    """
    Analyze candidate experience with robust date parsing.
    Handles multiple field name variations.
    """
    if not roles:
        return {
            "total_years": 0.0,
            "avg_tenure": 0.0,
            "num_hops": 0,
            "gaps": [],
            "stickiness_score": 0.0,
            "role_relevance": 0.0,
            "role_flags": []
        }
    
    total_years = 0.0
    tenures = []
    flags = []
    
    for role in roles:
        if not isinstance(role, dict):
            continue
        
        # Get start and end dates from various field names
        start_year = None
        end_year = None
        
        # Try start_date/end_date fields first
        if role.get("start_date"):
            start_year = parse_date_flexible(str(role.get("start_date")))
        if role.get("end_date"):
            end_year = parse_date_flexible(str(role.get("end_date")))
        
        # If not found, try parsing duration or dates string
        if start_year is None or end_year is None:
            duration_str = role.get("duration") or role.get("dates") or role.get("period")
            if duration_str:
                start_year, end_year = parse_duration_string(duration_str)
        
        # Calculate tenure if we have valid dates
        if start_year and end_year:
            tenure = end_year - start_year
            if tenure < 0:
                tenure = 0
            total_years += tenure
            tenures.append(tenure)
            
            # Flag very short tenure (< 6 months = 0.5 years)
            if tenure < 0.5:
                flags.append("short_tenure")
    
    # Calculate metrics
    num_roles = len(roles)
    num_hops = max(0, num_roles - 1)
    avg_tenure = sum(tenures) / len(tenures) if tenures else 0.0
    
    # Stickiness score (0-100)
    # Penalize job hopping, reward longer tenures
    if total_years == 0:
        stickiness_score = 0.0
    elif num_roles == 1:
        # Single role: score based on tenure
        stickiness_score = min(100, total_years * 20)  # 5 years = 100
    else:
        # Multiple roles: consider avg tenure and number of hops
        base_score = min(100, avg_tenure * 30)
        hop_penalty = min(30, (num_roles - 1) * 5)  # -5 per hop, max -30
        stickiness_score = max(0, base_score - hop_penalty)
    
    # Role relevance (0-100)
    # Check if candidate skills match JD requirements
    if not jd_required_skills or not candidate_skills:
        role_relevance = 50.0  # Neutral if no skills to compare
    else:
        # Normalize skills for comparison
        jd_skills_lower = [s.lower() for s in jd_required_skills]
        cand_skills_lower = [s.lower() for s in candidate_skills]
        
        matches = sum(1 for skill in cand_skills_lower if any(req in skill or skill in req for req in jd_skills_lower))
        role_relevance = min(100, (matches / len(jd_required_skills)) * 100)
    
    # Flag if too many hops
    if num_roles > 5:
        flags.append("excessive_hopping")
    
    return {
        "total_years": round(total_years, 1),
        "avg_tenure": round(avg_tenure, 1),
        "num_hops": num_hops,
        "gaps": [],  
        "stickiness_score": round(stickiness_score, 1),
        "role_relevance": round(role_relevance, 1),
        "role_flags": list(set(flags))  # Remove duplicates
    }
