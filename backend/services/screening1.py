from typing import List, Dict, Any
from .skill_ontology import expand_skills, normalize

def compute_tech_score(resume_skills: List[str], jd_required: List[str], jd_bonus: List[str]):
    resume_set = expand_skills(resume_skills)
    req_set = {normalize(s) for s in jd_required}
    bonus_set = {normalize(s) for s in jd_bonus}

    matched_required = req_set & resume_set
    matched_bonus = bonus_set & resume_set

    required_coverage = (len(matched_required) / len(req_set)) if req_set else 0.0
    bonus_coverage = (len(matched_bonus) / len(bonus_set)) if bonus_set else 0.0

    tech_score = required_coverage * 70 + bonus_coverage * 30  # 0–100

    # confidence: low if required coverage is very low or resume has very few skills
    if len(resume_set) < 5 or required_coverage < 0.3:
        confidence = "low"
    elif required_coverage < 0.6:
        confidence = "medium"
    else:
        confidence = "high"

    return {
        "tech_score": round(tech_score, 1),
        "matched_required": sorted(matched_required),
        "matched_bonus": sorted(matched_bonus),
        "missing_required": sorted(req_set - matched_required),
        "confidence": confidence,
    }

def build_candidate_result(candidate: Dict[str, Any], jd: Dict[str, Any]):
    jd_required = jd.get("required_skills", []) or []
    jd_bonus = jd.get("bonus_skills", []) or []

    skills = candidate.get("skills") or []
    base = compute_tech_score(skills, jd_required, jd_bonus)

    return {
        "candidate": candidate,
        **base,
    }
