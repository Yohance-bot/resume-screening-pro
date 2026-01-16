from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple

from groq import Groq
from pydantic import BaseModel, Field, ValidationError

from models import Candidate


LogicOp = Literal['AND', 'OR']
ConditionField = Literal[
    'role_bucket',
    'skill',
    'certification',
    'project',
    'work_experience',
    'experience_min_years',
    'experience_max_years',
]


StructuredOp = Literal['AND', 'OR']


class StructuredFilter(BaseModel):
    field: Literal[
        'project',
        'skill',
        'certification',
        'bucket',
        'role',
        'bench',
        'work_experience_years',
    ]
    operator: Literal['contains', 'equals', '>=', '<=', 'between']
    value: Any
    value2: Optional[Any] = None
    proficiency: Optional[Literal['BASIC', 'INTERMEDIATE', 'ADVANCED']] = None


class StructuredFilterRequest(BaseModel):
    op: StructuredOp = 'AND'
    filters: List[StructuredFilter] = Field(default_factory=list)


class Condition(BaseModel):
    field: ConditionField
    value: str


class AllOfGroup(BaseModel):
    all_of: List[Condition] = Field(default_factory=list)


class FilterSpec(BaseModel):
    any_of: List[AllOfGroup] = Field(default_factory=list)


def _debug_enabled() -> bool:
    return str(os.getenv('FILTER_DEBUG', '')).strip() in {'1', 'true', 'TRUE', 'yes', 'YES'}


def _debug_log(*args: Any) -> None:
    if _debug_enabled():
        print('[FILTER_DEBUG]', *args)


_SKILL_LEXICON = {
    'python', 'java', 'javascript', 'typescript', 'react', 'node', 'nodejs',
    'aws', 'azure', 'gcp', 'sql', 'mysql', 'postgres', 'postgresql', 'mongodb',
    'spark', 'pyspark', 'hadoop', 'airflow', 'databricks',
    'tensorflow', 'pytorch', 'scikit-learn', 'sklearn',
    'flask', 'fastapi', 'django',
    'docker', 'kubernetes',
    'machine learning', 'deep learning',
}


def _looks_like_skill_token(token: str) -> bool:
    t = _norm_text(token)
    if not t:
        return False
    if t in _SKILL_LEXICON:
        return True
    # very small heuristic: common short tech tokens
    if re.fullmatch(r"[a-z]{2,10}\d?", t) and t in {'ml', 'ai'}:
        return True
    return False


def _norm_text(s: str) -> str:
    s = str(s or '').strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def normalize_synonyms(term: str) -> List[str]:
    t = _norm_text(term)
    if not t:
        return []

    if t in {'ml'}:
        return ['machine learning']

    if t in {'ai/ml', 'ai-ml', 'aiml', 'ai ml'}:
        return ['ai', 'machine learning']

    if t in {'ai'}:
        return ['ai']

    return [t]


def _infer_skill_proficiency(c: Candidate, skill: str) -> Optional[str]:
    skill_norm = _norm_text(skill)
    if not skill_norm:
        return None

    projects = getattr(c, 'projects', None) or []
    if not isinstance(projects, list):
        projects = []

    def _iter_tools(p: Any) -> List[str]:
        if not isinstance(p, dict):
            return []
        arr = (
            p.get('technical_tools')
            or p.get('technologies_used')
            or p.get('skills')
            or p.get('tools')
            or []
        )
        if isinstance(arr, list):
            return [str(x) for x in arr if x]
        if isinstance(arr, str):
            return [x.strip() for x in arr.split(',') if x.strip()]
        return []

    used_in = 0
    for p in projects:
        tools = _iter_tools(p)
        if any(_norm_text(t) == skill_norm for t in tools):
            used_in += 1

    if used_in >= 4:
        return 'ADVANCED'
    if used_in >= 2:
        return 'INTERMEDIATE'
    if used_in >= 1:
        return 'BASIC'
    return None


def _proficiency_meets(actual: Optional[str], required: str) -> bool:
    if not required:
        return True
    order = {'BASIC': 1, 'INTERMEDIATE': 2, 'ADVANCED': 3}
    a = order.get((actual or '').upper(), 0)
    r = order.get(required.upper(), 0)
    if r == 0:
        return True
    return a >= r


def _match_scalar_contains(val: Any, term: str) -> bool:
    return _norm_text(term) in _norm_text(val or '')


def _match_scalar_equals(val: Any, term: str) -> bool:
    return _norm_text(val or '') == _norm_text(term)


def run_structured_candidate_filter(payload: Dict[str, Any], fetch_limit: int = 500, max_results: int = 50) -> Dict[str, Any]:
    req = StructuredFilterRequest.model_validate(payload)
    if not req.filters:
        return {
            'message': 'No filters provided.',
            'structured': {
                'type': 'candidate_table',
                'headers': ["ID", "Name", "Role", "Bucket", "Experience", "Top Skills", "Email"],
                'rows': [],
                'applied_filters': [],
                'warnings': ['No filters provided.'],
                'scanned': 0,
                'matched': 0,
            },
        }

    warnings: List[str] = []
    applied: List[str] = []

    q = Candidate.query

    min_years = None
    max_years = None

    for f in req.filters:
        if f.field == 'work_experience_years':
            if f.operator == '>=':
                min_years = max(min_years or float('-inf'), float(f.value))
                applied.append(f"work_experience_years >= {f.value}")
            elif f.operator == '<=':
                max_years = min(max_years or float('inf'), float(f.value))
                applied.append(f"work_experience_years <= {f.value}")
            elif f.operator == 'between':
                if f.value2 is None:
                    raise ValueError('between requires value2')
                lo = float(f.value)
                hi = float(f.value2)
                min_years = max(min_years or float('-inf'), min(lo, hi))
                max_years = min(max_years or float('inf'), max(lo, hi))
                applied.append(f"work_experience_years between {min(lo, hi)} and {max(lo, hi)}")
            else:
                raise ValueError('Unsupported operator for work_experience_years')

        elif f.field == 'bucket':
            if f.operator not in {'equals', 'contains'}:
                raise ValueError('Unsupported operator for bucket')
            if f.operator == 'equals':
                q = q.filter(Candidate.role_bucket == str(f.value))
                applied.append(f"bucket equals '{f.value}'")
            else:
                q = q.filter(Candidate.role_bucket.ilike(f"%{str(f.value)}%"))
                applied.append(f"bucket contains '{f.value}'")

        elif f.field == 'role':
            if f.operator not in {'equals', 'contains'}:
                raise ValueError('Unsupported operator for role')
            if f.operator == 'equals':
                q = q.filter(Candidate.primary_role == str(f.value))
                applied.append(f"role equals '{f.value}'")
            else:
                q = q.filter(Candidate.primary_role.ilike(f"%{str(f.value)}%"))
                applied.append(f"role contains '{f.value}'")

        elif f.field == 'bench':
            if f.operator not in {'equals'}:
                raise ValueError('Unsupported operator for bench')
            v = f.value
            if isinstance(v, str):
                v_norm = _norm_text(v)
                v_bool = v_norm in {'true', 'yes', 'y', '1'}
            else:
                v_bool = bool(v)
            q = q.filter(Candidate.on_bench == v_bool)
            applied.append(f"bench equals {str(v_bool).lower()}")

        elif f.field in {'skill', 'certification', 'project'}:
            if f.operator not in {'contains', 'equals'}:
                raise ValueError(f"Unsupported operator for {f.field}")
            applied.append(f"{f.field} {f.operator} '{f.value}'" + (f" (proficiency: {f.proficiency})" if f.field == 'skill' and f.proficiency else ''))
        else:
            raise ValueError(f"Unsupported field: {f.field}")

    if min_years is not None and min_years != float('-inf'):
        q = q.filter(Candidate.total_experience_years >= float(min_years))
    if max_years is not None and max_years != float('inf'):
        q = q.filter(Candidate.total_experience_years <= float(max_years))

    candidates = q.order_by(Candidate.created_at.desc()).limit(fetch_limit).all()
    scanned = len(candidates)

    def _matches_one(c: Candidate, flt: StructuredFilter) -> bool:
        if flt.field == 'skill':
            # Match against both declared skills and project tech/tools.
            skill_terms = list(dict.fromkeys(_candidate_skills(c) + _candidate_project_tech(c)))
            if flt.operator == 'contains':
                ok = _match_term(skill_terms, str(flt.value))
            else:
                skill_norm = _norm_text(str(flt.value))
                ok = any(_norm_text(s) == skill_norm for s in skill_terms)
            if not ok:
                return False
            if flt.proficiency:
                prof = _infer_skill_proficiency(c, str(flt.value))
                return _proficiency_meets(prof, flt.proficiency)
            return True

        if flt.field == 'certification':
            return _match_term(_candidate_certs(c), str(flt.value))

        if flt.field == 'project':
            return _match_term(_candidate_projects(c), str(flt.value))

        if flt.field == 'bucket':
            return _match_scalar_equals(getattr(c, 'role_bucket', None), str(flt.value)) if flt.operator == 'equals' else _match_scalar_contains(getattr(c, 'role_bucket', None), str(flt.value))

        if flt.field == 'role':
            return _match_scalar_equals(getattr(c, 'primary_role', None), str(flt.value)) if flt.operator == 'equals' else _match_scalar_contains(getattr(c, 'primary_role', None), str(flt.value))

        if flt.field == 'bench':
            v = flt.value
            if isinstance(v, str):
                v_bool = _norm_text(v) in {'true', 'yes', 'y', '1'}
            else:
                v_bool = bool(v)
            return bool(getattr(c, 'on_bench', False)) == bool(v_bool)

        if flt.field == 'work_experience_years':
            v = _try_parse_float(getattr(c, 'total_experience_years', None) or 0)
            if flt.operator == '>=':
                return v is not None and v >= float(flt.value)
            if flt.operator == '<=':
                return v is not None and v <= float(flt.value)
            if flt.operator == 'between':
                if flt.value2 is None:
                    return False
                lo = float(flt.value)
                hi = float(flt.value2)
                return v is not None and min(lo, hi) <= v <= max(lo, hi)
            return False

        return False

    matched: List[Candidate] = []
    for c in candidates:
        checks = [bool(_matches_one(c, f)) for f in req.filters]
        if req.op == 'AND':
            ok = all(checks)
        else:
            ok = any(checks)
        if ok:
            matched.append(c)
            if len(matched) >= max_results:
                break

    # If nothing matched, provide safe diagnostics: how many candidates match each filter individually.
    if not matched and candidates:
        try:
            counts = []
            for f in req.filters:
                n = 0
                for c in candidates:
                    if _matches_one(c, f):
                        n += 1
                counts.append({'filter': f"{f.field} {f.operator} {f.value}", 'matched_candidates': n})
            warnings.append('No candidates matched all constraints. Per-filter matches: ' + json.dumps(counts))
        except Exception:
            pass

    rows: List[Dict[str, Any]] = []
    for c in matched[:max_results]:
        skills = _candidate_skills(c)
        top_skills = ", ".join([s for s in skills[:5]])
        rows.append(
            {
                'cells': [
                    str(c.id),
                    str(getattr(c, 'full_name', '') or ''),
                    str(getattr(c, 'primary_role', '') or ''),
                    str(getattr(c, 'role_bucket', '') or ''),
                    str(getattr(c, 'total_experience_years', '') or ''),
                    top_skills,
                    str(getattr(c, 'email', '') or ''),
                ]
            }
        )

    msg = f"Found {len(rows)} matching candidate(s)." if rows else "No candidates matched those filters."
    if _debug_enabled():
        _debug_log('structured_filter_request', req.model_dump())
        _debug_log('scanned', scanned, 'matched', len(rows))

    return {
        'message': msg,
        'structured': {
            'type': 'candidate_table',
            'headers': ["ID", "Name", "Role", "Bucket", "Experience", "Top Skills", "Email"],
            'rows': rows,
            'applied_filters': applied,
            'warnings': warnings,
            'scanned': scanned,
            'matched': len(rows),
        },
    }


def _try_parse_float(s: str) -> Optional[float]:
    try:
        return float(s)
    except Exception:
        return None


def _extract_project_terms(text: str) -> List[str]:
    q = _norm_text(text)
    patterns = [
        r"\bprojects?\s+(?:in|on|with|using)\s+([a-z0-9\-/\s,]+)$",
        r"\bproject\s+(?:in|on|with|using)\s+([a-z0-9\-/\s,]+)$",
        r"\bworked\s+on\s+([a-z0-9\-/\s,]+)\s+projects?\b",
    ]
    for pat in patterns:
        m = re.search(pat, q, flags=re.I)
        if m:
            chunk = (m.group(1) or '').strip()
            if not chunk:
                continue
            raw_terms = [t.strip() for t in re.split(r"[,/]|\band\b|\bor\b", chunk, flags=re.I) if t.strip()]
            out: List[str] = []
            for t0 in raw_terms:
                out.extend(normalize_synonyms(t0))
            return [t0 for t0 in out if t0]
    return []


def _extract_work_terms(text: str) -> List[str]:
    q = _norm_text(text)
    patterns = [
        r"\bworked\s+at\s+([a-z0-9\-&\.,\s]{2,80})\b",
        r"\bexperience\s+at\s+([a-z0-9\-&\.,\s]{2,80})\b",
        r"\bcompany\s+([a-z0-9\-&\.,\s]{2,80})\b",
        r"\b(?:role|title)\s+([a-z0-9\-&\.,\s]{2,80})\b",
    ]
    out: List[str] = []
    for pat in patterns:
        for m in re.finditer(pat, q, flags=re.I):
            term = (m.group(1) or '').strip()
            if term:
                out.append(term)
    return [t0 for t0 in out if t0]


def _extract_experience_range(text: str) -> Tuple[Optional[float], Optional[float]]:
    q = _norm_text(text)
    min_years = None
    max_years = None

    m = re.search(r"\b(?:at\s+least|min(?:imum)?|>=|more\s+than|over)\s*(\d+(?:\.\d+)?)\s*(?:years|yrs)\b", q)
    if m:
        min_years = _try_parse_float(m.group(1))

    m = re.search(r"\b(?:at\s+most|max(?:imum)?|<=|less\s+than|under)\s*(\d+(?:\.\d+)?)\s*(?:years|yrs)\b", q)
    if m:
        max_years = _try_parse_float(m.group(1))

    m = re.search(r"\bbetween\s*(\d+(?:\.\d+)?)\s*(?:and|to)\s*(\d+(?:\.\d+)?)\s*(?:years|yrs)\b", q)
    if m:
        a = _try_parse_float(m.group(1))
        b = _try_parse_float(m.group(2))
        if a is not None and b is not None:
            min_years = min(a, b)
            max_years = max(a, b)

    return min_years, max_years


def _split_top_level(text: str, sep: str) -> List[str]:
    parts = [p.strip() for p in re.split(sep, text, flags=re.I) if p.strip()]
    return parts


def _extract_bucket(text: str) -> Optional[str]:
    m = re.search(r"\b(?:band\s*)?(?:level\s*)?c\s*([1-9])\b", text, flags=re.I)
    if not m:
        return None
    return f"c{m.group(1)}"


def _extract_cert_terms(text: str) -> List[str]:
    q = _norm_text(text)

    m = re.search(r"\bcertified\s+(?:in|on)\s+([a-z0-9\-/\s]+?)\b", q)
    if m:
        term = (m.group(1) or '').strip()
        if term:
            return [t for t in normalize_synonyms(term) if t]

    m = re.search(r"\b(?:with|has|have)\s+([a-z0-9\-/\s]+?)\s+(?:certification|certifications|certificate|certified)\b", q)
    if m:
        term = m.group(1).strip()
        return [t for t in normalize_synonyms(term) if t]

    m = re.search(r"\b([a-z0-9\-/\s]+?)\s+(?:certification|certifications|certificate|certified)\b", q)
    if m:
        term = m.group(1).strip()
        # Avoid matching just the keyword
        if term and term not in {'with', 'has', 'have'}:
            return [t for t in normalize_synonyms(term) if t]

    return []


def _extract_skill_terms(text: str) -> List[str]:
    q = _norm_text(text)

    patterns = [
        r"\b(?:candidates?|people)\s+with\s+([a-z0-9\-/\s,]+)$",
        r"\b(?:candidates?|people)\s+who\s+(?:have|has)\s+([a-z0-9\-/\s,]+)$",
        r"\b(?:have|has)\s+([a-z0-9\-/\s,]+)$",
        r"\b(?:has|have|with)\s+skills?\s+(?:in|on)?\s*([a-z0-9\-/\s,]+)$",
        r"\bknows\s+([a-z0-9\-/\s,]+)$",
        r"\bskills?\s+(?:in|on)?\s*([a-z0-9\-/\s,]+)$",
    ]

    for pat in patterns:
        m = re.search(pat, q, flags=re.I)
        if m:
            chunk = (m.group(1) or '').strip()
            if not chunk:
                continue
            raw_terms = [t.strip() for t in re.split(r"[,/]|\band\b|\bor\b", chunk, flags=re.I) if t.strip()]
            out: List[str] = []
            for t in raw_terms:
                # Avoid incorrectly treating experience phrases as skills.
                t_norm = _norm_text(t)
                if re.search(r"\b(?:yrs?|years?)\b", t_norm) and re.search(r"\b\d+(?:\.\d+)?\b", t_norm):
                    continue
                if 'experience' in t_norm and re.search(r"\b\d+(?:\.\d+)?\b", t_norm):
                    continue
                # Prefer lexicon-driven skills for generic "have X" patterns.
                expanded = normalize_synonyms(t)
                for x in expanded:
                    if _looks_like_skill_token(x):
                        out.append(x)
                    elif pat.startswith(r"\b(?:have|has)") or 'who' in pat:
                        # For generic "have X" captures, only accept lexicon skills.
                        continue
                    else:
                        out.append(x)
            return [t for t in out if t]

    return []


def _looks_like_filter_query(text: str) -> bool:
    q = _norm_text(text)
    if not q:
        return False

    if re.search(r"\b(?:c\s*[1-9]|band\s*c\s*[1-9]|level\s*c\s*[1-9])\b", q):
        return True

    if any(k in q for k in ['certification', 'certifications', 'certificate', 'certified']):
        return True

    if any(k in q for k in ['has skills', 'skills in', 'knows']):
        return True

    if re.search(r"\b(?:candidates?|people)\s+with\b", q):
        return True

    if any(k in q for k in ['project', 'projects', 'worked at', 'experience at', 'years', 'yrs']):
        if 'candidate' in q or 'candidates' in q or 'who' in q or 'list' in q or 'find' in q:
            return True

    if any(k in q for k in ['who all', 'who are', 'show me', 'list', 'find']):
        if 'candidates' in q or 'candidate' in q:
            return True

    return False


def _rule_based_parse(user_text: str) -> Tuple[Optional[FilterSpec], str]:
    text = user_text.strip()
    if not _looks_like_filter_query(text):
        return None, 'not_filter'

    groups_raw = _split_top_level(text, r"\bor\b")
    any_of: List[AllOfGroup] = []

    # For queries like: "candidates with aws or gcp", the OR split yields ["candidates with aws", "gcp"].
    # If a group is a bare token, treat it as a skill group.
    overall_skill_mode = bool(re.search(r"\b(?:candidates?|people)\s+with\b", _norm_text(text)))

    for g in groups_raw:
        g_norm = _norm_text(g)
        if overall_skill_mode and not _looks_like_filter_query(g) and re.fullmatch(r"[a-z0-9\-]{2,30}", g_norm):
            g = f"skills in {g_norm}"

        parts = _split_top_level(g, r"\band\b")
        conds: List[Condition] = []

        bucket = _extract_bucket(g)
        if bucket:
            conds.append(Condition(field='role_bucket', value=bucket))

        min_years, max_years = _extract_experience_range(g)
        if min_years is not None:
            conds.append(Condition(field='experience_min_years', value=str(min_years)))
        if max_years is not None:
            conds.append(Condition(field='experience_max_years', value=str(max_years)))

        cert_terms: List[str] = []
        skill_terms: List[str] = []
        project_terms: List[str] = []
        work_terms: List[str] = []

        for p in parts:
            cert_terms.extend(_extract_cert_terms(p))
            skill_terms.extend(_extract_skill_terms(p))
            project_terms.extend(_extract_project_terms(p))
            work_terms.extend(_extract_work_terms(p))

            p_min, p_max = _extract_experience_range(p)
            if p_min is not None and min_years is None:
                min_years = p_min
                conds.append(Condition(field='experience_min_years', value=str(min_years)))
            if p_max is not None and max_years is None:
                max_years = p_max
                conds.append(Condition(field='experience_max_years', value=str(max_years)))

            b2 = _extract_bucket(p)
            if b2 and not bucket:
                bucket = b2
                conds.append(Condition(field='role_bucket', value=bucket))

            if not cert_terms and re.search(r"\bml\b", p, flags=re.I) and re.search(
                r"\b(certification|certifications|certificate|certified)\b", p, flags=re.I
            ):
                cert_terms.extend(['machine learning'])

        # If the user writes: "candidates with python and aws", splitting by AND yields
        # parts like ["candidates with python", "aws"]. Treat bare tokens as skills.
        if skill_terms:
            for p in parts:
                p_norm = _norm_text(p)
                if not p_norm:
                    continue
                if p_norm in {'and', 'or', 'with', 'has', 'have', 'skills', 'skill', 'candidates', 'candidate', 'people'}:
                    continue
                # If this part already contributed via explicit patterns, skip.
                if _extract_skill_terms(p) or _extract_cert_terms(p) or _extract_project_terms(p) or _extract_work_terms(p):
                    continue
                # Only accept simple short tokens/phrases.
                if re.fullmatch(r"[a-z0-9\-/\s]{2,40}", p_norm):
                    for t in normalize_synonyms(p_norm):
                        if t and t not in skill_terms:
                            skill_terms.append(t)

        # Special-case: "python and machine learning certifications".
        # If we found certifications but did not find skills, try to infer skills from the non-cert side.
        if cert_terms and not skill_terms:
            g_norm = _norm_text(g)
            if 'certification' in g_norm or 'certifications' in g_norm or 'certified' in g_norm:
                # Remove obvious certification phrases so remaining tokens can be interpreted as skills.
                scrub = re.sub(r"\b(certification|certifications|certificate|certified)\b", " ", g_norm)
                for tok in [t.strip() for t in re.split(r"[,/]|\band\b", scrub, flags=re.I) if t.strip()]:
                    if tok in cert_terms:
                        continue
                    for x in normalize_synonyms(tok):
                        if x and _looks_like_skill_token(x) and x not in skill_terms:
                            skill_terms.append(x)

        for t in cert_terms:
            conds.append(Condition(field='certification', value=t))
        for t in skill_terms:
            conds.append(Condition(field='skill', value=t))
        for t in project_terms:
            conds.append(Condition(field='project', value=t))
        for t in work_terms:
            conds.append(Condition(field='work_experience', value=t))

        if not conds:
            return None, 'ambiguous'

        any_of.append(AllOfGroup(all_of=conds))

    if not any_of:
        return None, 'ambiguous'

    return FilterSpec(any_of=any_of), 'ok'


def _groq_fallback_parse(user_text: str) -> FilterSpec:
    client = Groq(api_key=os.getenv('GROQ_API_KEY'))

    schema = {
        "type": "object",
        "properties": {
            "any_of": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "all_of": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "field": {"type": "string", "enum": [
                                        "role_bucket",
                                        "skill",
                                        "certification",
                                        "project",
                                        "work_experience",
                                        "experience_min_years",
                                        "experience_max_years"
                                    ]},
                                    "value": {"type": "string"},
                                },
                                "required": ["field", "value"],
                                "additionalProperties": False,
                            },
                        }
                    },
                    "required": ["all_of"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["any_of"],
        "additionalProperties": False,
    }

    system_prompt = (
        "You convert a user request into a JSON filter spec for filtering candidates. "
        "Return ONLY valid JSON. Do not include any explanation. "
        "Use the schema exactly. Use 'any_of' as OR groups, and each group's 'all_of' as AND conditions. "
        "Normalize synonyms: 'ml' -> 'machine learning', 'ai/ml' -> ['ai','machine learning'] (pick the best single value if needed)."
    )

    user_prompt = (
        f"User text:\n{user_text}\n\n"
        f"JSON schema:\n{json.dumps(schema, indent=2)}\n"
    )

    chat = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
        max_tokens=400,
    )

    raw = chat.choices[0].message.content
    try:
        obj = json.loads(raw)
    except Exception as e:
        raise ValueError(f"LLM did not return valid JSON: {e}")

    spec = FilterSpec.model_validate(obj)

    normalized_any_of: List[AllOfGroup] = []
    for grp in spec.any_of:
        norm_conds: List[Condition] = []
        for c in grp.all_of:
            if c.field in {'skill', 'certification'}:
                terms = normalize_synonyms(c.value)
                if terms:
                    for t in terms:
                        norm_conds.append(Condition(field=c.field, value=t))
                else:
                    norm_conds.append(c)
            else:
                norm_conds.append(c)
        normalized_any_of.append(AllOfGroup(all_of=norm_conds))

    return FilterSpec(any_of=normalized_any_of)


_debug_logged = False


def parse_candidate_filters(user_text: str) -> Optional[FilterSpec]:
    global _debug_logged

    if not _debug_logged:
        _debug_logged = True
        examples = [
            "who all are the candidates who are c4 and have ml certifications",
            "list candidates with band c3 and skills in python and aws",
            "who are c4 or c5 with databricks certifications",
            "find candidates who knows ai/ml and has certifications",
            "c4 and certified in azure",
        ]
        for ex in examples:
            spec0, reason0 = _rule_based_parse(ex)
            if spec0 is not None:
                print("[FILTER_DEBUG]", ex, "->", spec0.model_dump())
            else:
                print("[FILTER_DEBUG]", ex, "->", reason0)

    spec, reason = _rule_based_parse(user_text)
    if spec is not None:
        return spec

    if reason == 'not_filter':
        return None

    try:
        return _groq_fallback_parse(user_text)
    except (ValidationError, ValueError) as e:
        print('[FILTER_DEBUG] groq_fallback_failed:', str(e))
        return None


def _candidate_skills(c: Candidate) -> List[str]:
    skills: List[str] = []
    parsed = getattr(c, 'parsed', None) or {}

    if isinstance(parsed, str):
        try:
            parsed = json.loads(parsed)
        except Exception:
            parsed = {}

    if isinstance(getattr(c, 'skills', None), list):
        skills = [str(s) for s in (c.skills or []) if s]

    if not skills and isinstance(parsed, dict):
        maybe = parsed.get('technical_skills') or parsed.get('skills') or parsed.get('primary_skills')
        if isinstance(maybe, list):
            skills = [str(s) for s in maybe if s]

    return [_norm_text(s) for s in skills if _norm_text(s)]


def _candidate_certs(c: Candidate) -> List[str]:
    certs: List[str] = []
    parsed = getattr(c, 'parsed', None) or {}

    if isinstance(parsed, str):
        try:
            parsed = json.loads(parsed)
        except Exception:
            parsed = {}

    if isinstance(getattr(c, 'certifications', None), list):
        raw = c.certifications or []
        for item in raw:
            if isinstance(item, dict):
                name = item.get('name')
                if name:
                    certs.append(str(name))
            else:
                certs.append(str(item))

    if not certs and isinstance(parsed, dict):
        raw2 = parsed.get('certifications')
        if isinstance(raw2, list):
            for item in raw2:
                if isinstance(item, dict):
                    name = item.get('name') or item.get('title')
                    if name:
                        certs.append(str(name))
                else:
                    certs.append(str(item))

    return [_norm_text(s) for s in certs if _norm_text(s)]


def _candidate_projects(c: Candidate) -> List[str]:
    projects: List[str] = []
    parsed = getattr(c, 'parsed', None) or {}

    if isinstance(parsed, str):
        try:
            parsed = json.loads(parsed)
        except Exception:
            parsed = {}

    raw = getattr(c, 'projects', None)
    if isinstance(raw, list):
        for p in raw:
            if isinstance(p, dict):
                for k in ['name', 'organization', 'role', 'description', 'contribution', 'impact']:
                    v = p.get(k)
                    if v:
                        projects.append(str(v))
                tech = p.get('technical_tools') or p.get('technologies_used')
                if isinstance(tech, list):
                    projects.extend([str(t) for t in tech if t])
            else:
                projects.append(str(p))

    if not projects and isinstance(parsed, dict):
        raw2 = parsed.get('projects')
        if isinstance(raw2, list):
            for p in raw2:
                if isinstance(p, dict):
                    for k in ['name', 'organization', 'role', 'description', 'contribution', 'impact']:
                        v = p.get(k)
                        if v:
                            projects.append(str(v))
                    tech = p.get('technical_tools') or p.get('technologies_used')
                    if isinstance(tech, list):
                        projects.extend([str(t) for t in tech if t])
                else:
                    projects.append(str(p))

    return [_norm_text(s) for s in projects if _norm_text(s)]


def _candidate_project_tech(c: Candidate) -> List[str]:
    techs: List[str] = []
    parsed = getattr(c, 'parsed', None) or {}

    if isinstance(parsed, str):
        try:
            parsed = json.loads(parsed)
        except Exception:
            parsed = {}

    def _add_from_project(p: Any) -> None:
        if not isinstance(p, dict):
            return
        arr = (
            p.get('technical_tools')
            or p.get('technologies_used')
            or p.get('tools')
            or p.get('skills')
            or []
        )
        if isinstance(arr, list):
            for t in arr:
                if t:
                    techs.append(str(t))
        elif isinstance(arr, str):
            techs.extend([x.strip() for x in arr.split(',') if x.strip()])

    raw = getattr(c, 'projects', None)
    if isinstance(raw, list):
        for p in raw:
            _add_from_project(p)

    if isinstance(parsed, dict):
        raw2 = parsed.get('projects')
        if isinstance(raw2, list):
            for p in raw2:
                _add_from_project(p)

    return [_norm_text(t) for t in techs if _norm_text(t)]


def _candidate_work_experiences(c: Candidate) -> List[str]:
    work: List[str] = []
    parsed = getattr(c, 'parsed', None) or {}

    if isinstance(parsed, str):
        try:
            parsed = json.loads(parsed)
        except Exception:
            parsed = {}

    raw = getattr(c, 'work_experiences', None)
    if isinstance(raw, list):
        for w in raw:
            if isinstance(w, dict):
                for k in ['company_name', 'job_title', 'location', 'start_date', 'end_date']:
                    v = w.get(k)
                    if v:
                        work.append(str(v))
                tech = w.get('technologies_used')
                if isinstance(tech, list):
                    work.extend([str(t) for t in tech if t])
                resp = w.get('responsibilities')
                if isinstance(resp, list):
                    work.extend([str(r) for r in resp if r])
            else:
                work.append(str(w))

    if not work and isinstance(parsed, dict):
        raw2 = parsed.get('work_experiences')
        if isinstance(raw2, list):
            for w in raw2:
                if isinstance(w, dict):
                    for k in ['company_name', 'job_title', 'location', 'start_date', 'end_date']:
                        v = w.get(k)
                        if v:
                            work.append(str(v))
                    tech = w.get('technologies_used')
                    if isinstance(tech, list):
                        work.extend([str(t) for t in tech if t])
                    resp = w.get('responsibilities')
                    if isinstance(resp, list):
                        work.extend([str(r) for r in resp if r])
                else:
                    work.append(str(w))

    return [_norm_text(s) for s in work if _norm_text(s)]


def _match_term(values: Sequence[str], term: str) -> bool:
    t = _norm_text(term)
    if not t:
        return False
    for v in values:
        if t in v:
            return True
    return False


def _candidate_matches_group(c: Candidate, group: AllOfGroup) -> bool:
    for cond in group.all_of:
        if cond.field == 'role_bucket':
            if _norm_text(getattr(c, 'role_bucket', '') or '') != _norm_text(cond.value):
                return False
        elif cond.field == 'experience_min_years':
            v = _try_parse_float(getattr(c, 'total_experience_years', None) or 0)
            target = _try_parse_float(cond.value)
            if target is not None and (v is None or v < target):
                return False
        elif cond.field == 'experience_max_years':
            v = _try_parse_float(getattr(c, 'total_experience_years', None) or 0)
            target = _try_parse_float(cond.value)
            if target is not None and (v is None or v > target):
                return False
        elif cond.field == 'skill':
            if not _match_term(_candidate_skills(c), cond.value):
                return False
        elif cond.field == 'certification':
            if not _match_term(_candidate_certs(c), cond.value):
                return False
        elif cond.field == 'project':
            if not _match_term(_candidate_projects(c), cond.value):
                return False
        elif cond.field == 'work_experience':
            if not _match_term(_candidate_work_experiences(c), cond.value):
                return False
        else:
            return False
    return True


def run_candidate_filter_query(spec: FilterSpec, fetch_limit: int = 500, max_results: int = 50) -> Dict[str, Any]:
    if not spec.any_of:
        return {
            'message': 'I could not determine any filters from your request.',
            'rows': [],
            'spec': spec.model_dump(),
            'matched': 0,
            'applied_filters': [],
            'warnings': [],
        }

    _debug_log('parsed_spec', spec.model_dump())

    results: Dict[int, Candidate] = {}
    warnings: List[str] = []
    applied_filters: List[str] = []
    scanned_total = 0

    for group in spec.any_of:
        q = Candidate.query
        bucket_values = [c.value for c in group.all_of if c.field == 'role_bucket']

        # If the dataset doesn't contain C-level buckets (c1..c9), don't let it zero the result.
        # Instead: ignore with a warning and keep applying other constraints.
        if bucket_values:
            bucket_values_norm = [_norm_text(v) for v in bucket_values]
            only_c_levels = all(re.fullmatch(r"c[1-9]", v or "") for v in bucket_values_norm)
            if only_c_levels:
                try:
                    existing = (
                        Candidate.query.with_entities(Candidate.role_bucket)
                        .distinct()
                        .limit(50)
                        .all()
                    )
                    existing_norm = {_norm_text(r[0]) for r in existing if r and r[0]}
                except Exception:
                    existing_norm = set()

                if existing_norm and not (set(bucket_values_norm) & existing_norm):
                    warnings.append(
                        "Requested band/level buckets (e.g., c4) but this database does not store those values in role_bucket; ignoring bucket constraint."
                    )
                else:
                    q = q.filter(Candidate.role_bucket.in_(bucket_values))
                    applied_filters.append(f"role_bucket IN {bucket_values}")
            else:
                q = q.filter(Candidate.role_bucket.in_(bucket_values))
                applied_filters.append(f"role_bucket IN {bucket_values}")

        min_vals = [c.value for c in group.all_of if c.field == 'experience_min_years']
        max_vals = [c.value for c in group.all_of if c.field == 'experience_max_years']

        # Record non-SQL filters too (debug visibility)
        for cond in group.all_of:
            if cond.field == 'skill':
                applied_filters.append(f"skill contains '{cond.value}'")
            elif cond.field == 'certification':
                applied_filters.append(f"certification contains '{cond.value}'")
            elif cond.field == 'project':
                applied_filters.append(f"project contains '{cond.value}'")
            elif cond.field == 'work_experience':
                applied_filters.append(f"work_experience contains '{cond.value}'")

        if min_vals:
            mins = [m for m in (_try_parse_float(v) for v in min_vals) if m is not None]
            if mins:
                q = q.filter(Candidate.total_experience_years >= max(mins))
                applied_filters.append(f"total_experience_years >= {max(mins)}")

        if max_vals:
            maxs = [m for m in (_try_parse_float(v) for v in max_vals) if m is not None]
            if maxs:
                q = q.filter(Candidate.total_experience_years <= min(maxs))
                applied_filters.append(f"total_experience_years <= {min(maxs)}")

        candidates = (
            q.order_by(Candidate.created_at.desc())
            .limit(fetch_limit)
            .all()
        )

        scanned_total += len(candidates)

        for c in candidates:
            if _candidate_matches_group(c, group):
                results[int(c.id)] = c
                if len(results) >= max_results:
                    break
        if len(results) >= max_results:
            break

    matched = list(results.values())
    matched.sort(key=lambda c: c.created_at or 0, reverse=True)

    rows: List[Dict[str, Any]] = []
    for c in matched[:max_results]:
        skills = _candidate_skills(c)
        top_skills = ", ".join([s for s in skills[:5]])
        rows.append(
            {
                'cells': [
                    str(c.id),
                    str(getattr(c, 'full_name', '') or ''),
                    str(getattr(c, 'primary_role', '') or ''),
                    str(getattr(c, 'role_bucket', '') or ''),
                    str(getattr(c, 'total_experience_years', '') or ''),
                    top_skills,
                    str(getattr(c, 'email', '') or ''),
                ]
            }
        )

    explanation_parts: List[str] = []
    for i, grp in enumerate(spec.any_of, 1):
        parts = []
        for cond in grp.all_of:
            if cond.field == 'role_bucket':
                parts.append(f"bucket={cond.value}")
            elif cond.field == 'skill':
                parts.append(f"skill contains '{cond.value}'")
            elif cond.field == 'certification':
                parts.append(f"certification contains '{cond.value}'")
            elif cond.field == 'project':
                parts.append(f"project contains '{cond.value}'")
            elif cond.field == 'work_experience':
                parts.append(f"work experience contains '{cond.value}'")
            elif cond.field == 'experience_min_years':
                parts.append(f"experience >= {cond.value} yrs")
            elif cond.field == 'experience_max_years':
                parts.append(f"experience <= {cond.value} yrs")
        if parts:
            explanation_parts.append(f"Group {i}: " + " AND ".join(parts))

    if not rows:
        _debug_log('scanned', scanned_total, 'matched', 0)
        return {
            'message': (
                "No candidates matched those filters. "
                "Try relaxing one constraint (e.g., remove certification/skill) or using OR.\n\n"
                + "\n".join(explanation_parts)
            ),
            'rows': [],
            'spec': spec.model_dump(),
            'matched': 0,
            'scanned': scanned_total,
            'applied_filters': applied_filters,
            'warnings': warnings,
        }

    _debug_log('scanned', scanned_total, 'matched', len(rows))
    return {
        'message': f"Found {len(rows)} matching candidate(s).\n\n" + "\n".join(explanation_parts),
        'rows': rows,
        'spec': spec.model_dump(),
        'matched': len(rows),
        'scanned': scanned_total,
        'applied_filters': applied_filters,
        'warnings': warnings,
    }
