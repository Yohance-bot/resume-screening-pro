# backend/services/smart_screening.py
from typing import Dict, Any
from services.screening1 import build_candidate_result as tech_match
from services.screening2 import analyze_experience
from services.screening3 import compute_matrix_score

def smart_screen_candidate(candidate: Dict[str, Any], jd: Dict[str, Any]) -> Dict[str, Any]:
    """
    Combine tech match, experience quality, and recency matrix
    into one normalized 0–100 score + explanations.
    """
    skills = candidate.get("skills") or []
    roles = candidate.get("roles") or []

    jd_required = jd.get("required_skills", []) or []
    jd_bonus = jd.get("bonus_skills", []) or []

    tech = tech_match(
        {"skills": skills},
        jd,
    )
    tech_score = tech["tech_score"]

    exp = analyze_experience(roles, jd_required, skills)
    exp_score = 0.6 * exp["stickiness_score"] + 0.4 * exp["role_relevance"]

    matrix = compute_matrix_score(
        {"roles": roles, "skills": skills},
        jd,
    )
    matrix_score = matrix["matrix_score"]

    final_score = (
        0.45 * tech_score +
        0.30 * exp_score +
        0.25 * matrix_score
    )

    return {
        "candidate_id": candidate.get("id"),
        "candidate_name": candidate.get("full_name") or candidate.get("name") or "Unknown",
        "final_score": round(final_score, 1),
        "tech_score": round(tech_score, 1),
        "experience_score": round(exp_score, 1),
        "matrix_score": round(matrix_score, 1),

        "matched_required_skills": tech["matched_required"],
        "matched_bonus_skills": tech["matched_bonus"],
        "missing_required_skills": tech["missing_required"],
        "tech_confidence": tech["confidence"],

        "total_experience_years": exp["total_years"],
        "avg_tenure_years": exp["avg_tenure"],
        "num_role_hops": exp["num_hops"],
        "stickiness_score": exp["stickiness_score"],
        "experience_flags": exp["role_flags"],

        "role_scores": matrix["role_scores"],
        "skill_scores": matrix["skill_scores"],
        "total_role_score": matrix["total_role_score"],
        "total_skill_score": matrix["total_skill_score"],
    }

