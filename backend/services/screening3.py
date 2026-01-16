from typing import List, Dict, Any
from services.skill_ontology import expand_skills, normalize
from services.screening2 import parse_date_flexible
from datetime import datetime

def score_skill_recency(skill: str, roles: List[Dict]) -> float:
    """Score skill by recency - recent roles weigh more."""
    if not roles:
        return 0.5  # neutral
    
    recent_year = datetime.now().year - 1
    skill_year_weight = 0.0
    
    for role in sorted(roles, key=lambda r: parse_date_flexible(r.get("end_date", "")) or 0, reverse=True):
        role_end = parse_date_flexible(role.get("end_date")) or recent_year
        role_weight = max(0.1, 1.0 - (datetime.now().year - role_end) * 0.2)  # decays 20%/year
        
        # Assume skill appears in recent roles
        if role_end >= recent_year - 2:  # last 2 years
            skill_year_weight += role_weight * 0.6
        else:
            skill_year_weight += role_weight * 0.3
    
    return min(1.0, skill_year_weight / max(len(roles), 1))

def compute_matrix_score(cand: Dict, jd: Dict) -> Dict:
    """Full JD-Resume matrix scoring."""
    roles = cand.get("roles", [])
    skills = cand.get("skills", [])
    
    jd_required = jd.get("required_skills", [])
    jd_bonus = jd.get("bonus_skills", [])
    
    # 1. Role-level relevance (from screening2)
    role_scores = []
    for role in roles:
        role_info = score_role_relevance(role, jd_required, skills)
        role_info["recency_weight"] = score_skill_recency("", [role])
        role_scores.append(role_info)
    
    total_role_score = sum(rs["relevance"] * rs["recency_weight"] for rs in role_scores) / max(len(role_scores), 1)
    
    # 2. Skill matrix with recency
    skill_scores = {}
    for skill in skills:
        recency = score_skill_recency(skill, roles)
        if normalize(skill) in {normalize(s) for s in jd_required}:
            skill_scores[skill] = recency * 1.0  # full weight
        elif normalize(skill) in {normalize(s) for s in jd_bonus}:
            skill_scores[skill] = recency * 0.5  # half weight
    
    total_skill_score = sum(skill_scores.values()) / max(len(skills), 1) if skills else 0.0
    
    # 3. Matrix combined (60% roles + 40% skills)
    matrix_score = 0.6 * total_role_score + 0.4 * total_skill_score
    
    return {
        "matrix_score": round(matrix_score, 1),
        "role_scores": role_scores,
        "skill_scores": skill_scores,
        "total_role_score": round(total_role_score, 1),
        "total_skill_score": round(total_skill_score, 1),
    }

def score_role_relevance(role: Dict, jd_required: List[str], candidate_skills: List[str] = None) -> Dict:
    """Helper from screening2."""
    role_skills_raw = (role.get("skills", []) or candidate_skills or [])
    role_skills = expand_skills(role_skills_raw)
    jd_skills = {normalize(s) for s in jd_required}
    
    matched = role_skills & jd_skills
    relevance = len(matched) / max(len(jd_skills), 1) * 100
    
    flags = []
    title = role.get("title", "").lower()
    if any(word in title for word in ["intern", "trainee", "fresher"]):
        flags.append("entry_level")
    
    return {"relevance": relevance, "matched_skills": list(matched), "flags": flags}
