"""
Project matching and summary generation utility.
Matches candidates to existing projects and auto-updates summaries.
"""

from models import db, ProjectDB, CandidateProject, Candidate
from sqlalchemy import func
from fuzzywuzzy import fuzz
from typing import Optional, Dict, List, Tuple
import re


def normalize_project_name(name: str) -> str:
    """Normalize project name for matching"""
    if not name:
        return ""
    # Remove special chars, lowercase, strip whitespace
    normalized = re.sub(r'[^\w\s-]', '', name.lower().strip())
    # Remove common prefixes
    stop_words = ['project', 'the', 'a', 'an']
    words = normalized.split()
    words = [w for w in words if w not in stop_words]
    return ' '.join(words)


def calculate_project_similarity(proj1: Dict, proj2: Dict) -> float:
    """
    Calculate similarity score between two projects (0.0 to 1.0).
    Based on project name, organization, description, and technologies.
    """
    if not proj1 or not proj2:
        return 0.0

    scores = []

    # 1. Name similarity (60% weight)
    name1 = normalize_project_name(proj1.get("name") or "")
    name2 = normalize_project_name(proj2.get("name") or "")

    if name1 and name2:
        # Exact match = 100%
        if name1 == name2:
            return 1.0
        # Use token_sort_ratio to handle word order differences
        name_sim = fuzz.token_sort_ratio(name1, name2) / 100.0
        scores.append(('name', name_sim, 0.6))

    # 2. Organization similarity (15% weight)
    org1 = (proj1.get("organization") or "").lower().strip()
    org2 = (proj2.get("organization") or "").lower().strip()
    if org1 and org2:
        org_sim = fuzz.ratio(org1, org2) / 100.0
        scores.append(('org', org_sim, 0.15))

    # 3. Description similarity (10% weight)
    desc1 = (proj1.get("description") or "").lower().strip()
    desc2 = (proj2.get("description") or "").lower().strip()
    if desc1 and desc2:
        desc_sim = fuzz.partial_ratio(desc1, desc2) / 100.0
        scores.append(('desc', desc_sim, 0.10))

    # 4. Technology overlap (15% weight)
    tech1 = set(proj1.get("technologies_used") or proj1.get("technical_tools") or [])
    tech2 = set(proj2.get("technologies_used") or proj2.get("technical_tools") or [])
    if tech1 and tech2:
        # Jaccard similarity
        intersection = len(tech1 & tech2)
        union = len(tech1 | tech2)
        tech_sim = intersection / union if union > 0 else 0.0
        scores.append(('tech', tech_sim, 0.15))

    # Calculate weighted average
    if not scores:
        return 0.0

    total_weight = sum(weight for _, _, weight in scores)
    weighted_sum = sum(score * weight for _, score, weight in scores)

    return weighted_sum / total_weight if total_weight > 0 else 0.0


def find_matching_project(
    project_name: str,
    organization: Optional[str] = None,
    start_date: Optional[str] = None,
    threshold: float = 0.75
) -> Optional[ProjectDB]:
    """
    Find existing project in DB that matches the given project.
    
    Matching criteria (in order of priority):
    1. Exact name + organization match
    2. High similarity name (>75%) + organization match
    3. Exact name + overlapping dates
    4. High similarity name (>75%) alone
    
    Returns:
        ProjectDB object if match found, None otherwise
    """
    if not project_name:
        return None
    
    normalized_name = normalize_project_name(project_name)
    
    # Get all projects (limit to reasonable number for performance)
    all_projects = ProjectDB.query.limit(1000).all()
    
    best_match = None
    best_score = 0.0
    
    for proj in all_projects:
        score = 0.0
        proj_normalized = normalize_project_name(proj.name)
        
        # Exact match check first
        if normalized_name == proj_normalized:
            return proj
        
        # Name similarity (60% weight)
        name_similarity = fuzz.token_sort_ratio(normalized_name, proj_normalized) / 100.0
        score += name_similarity * 0.6
        
        # Organization match (if both provided) (30% weight)
        if organization and proj.organization:
            org_similarity = fuzz.ratio(
                organization.lower().strip(),
                proj.organization.lower().strip()
            ) / 100.0
            score += org_similarity * 0.3
        
        # Date overlap check (if provided) (10% bonus)
        if start_date and proj.start_date:
            # Simple year extraction for basic matching
            year_pattern = r'\d{4}'
            candidate_years = set(re.findall(year_pattern, start_date))
            project_years = set(re.findall(year_pattern, proj.start_date))
            if candidate_years and project_years and candidate_years & project_years:
                score += 0.1
        
        if score > best_score and score >= threshold:
            best_score = score
            best_match = proj
    
    if best_match:
        print(f"🔍 Found matching project: '{best_match.name}' (score: {best_score:.2%})")
    
    return best_match


def merge_technologies(existing: List[str], new: List[str]) -> List[str]:
    """Merge technology lists, removing duplicates (case-insensitive)"""
    if not existing:
        existing = []
    if not new:
        return existing
    
    # Create lowercase map for deduplication
    tech_map = {tech.lower(): tech for tech in existing if tech}
    for tech in new:
        if tech:  # Skip None/empty
            tech_lower = tech.lower()
            if tech_lower not in tech_map:
                tech_map[tech_lower] = tech
    
    return sorted(tech_map.values())


def generate_project_summary(project: ProjectDB) -> str:
    """
    Generate comprehensive project summary from all candidate contributions.
    
    Format:
    - Project description (synthesized from all candidates)
    - Key technologies used
    - Team roles and responsibilities
    - Impact metrics
    """
    if not project.contributions:
        return "No detailed information available yet."
    
    # Collect all descriptions
    descriptions = [c.description for c in project.contributions if c.description]
    
    # Collect all roles and responsibilities
    roles_responsibilities = []
    for contrib in project.contributions:
        if contrib.role and contrib.responsibilities:
            roles_responsibilities.append({
                "role": contrib.role,
                "responsibilities": contrib.responsibilities[:3],  # Top 3 per person
                "name": contrib.candidate.full_name if contrib.candidate else "Unknown"
            })
    
    # Collect impact metrics
    impacts = [c.impact for c in project.contributions if c.impact]
    
    # Build summary
    summary_parts = []
    
    # 1. Description (take the most detailed one)
    if descriptions:
        longest_desc = max(descriptions, key=len)
        summary_parts.append(f"**Overview:** {longest_desc}")
    
    # 2. Technologies
    if project.all_technologies:
        tech_str = ", ".join(project.all_technologies[:15])  # Limit to 15 techs
        summary_parts.append(f"\n**Technologies:** {tech_str}")
    
    # 3. Team contributions
    if roles_responsibilities:
        summary_parts.append("\n**Team Contributions:**")
        for item in roles_responsibilities[:5]:  # Max 5 roles
            role = item["role"]
            name = item["name"]
            resp_str = "; ".join(item["responsibilities"])
            summary_parts.append(f"- *{name} ({role}):* {resp_str}")
    
    # 4. Impact
    if impacts:
        summary_parts.append(f"\n**Impact:** {' | '.join(impacts[:3])}")
    
    # 5. Team size
    if project.total_contributors:
        summary_parts.append(f"\n**Team Size:** {project.total_contributors} contributor(s)")
    
    return "\n".join(summary_parts)


def add_candidate_to_project(
    candidate_id: int,
    project_data: Dict,
) -> Tuple[ProjectDB, CandidateProject]:
    """
    Add candidate to a project (new or existing).
    
    Steps:
    1. Try to find matching existing project
    2. If found, add candidate contribution
    3. If not found, create new project
    4. Update project summary with new contribution
    5. Merge technologies
    
    Args:
        candidate_id: Candidate ID
        project_ Dict with keys matching Project Pydantic model
    
    Returns:
        Tuple of (ProjectDB, CandidateProject)
    """
    # Extract project info
    project_name = project_data.get("name", "Unnamed Project")
    organization = project_data.get("organization")
    start_date = project_data.get("start_date")
    end_date = project_data.get("end_date")
    duration_months = project_data.get("duration_months")
    is_academic = project_data.get("is_academic", False)
    
    # Try to find existing project
    existing_project = find_matching_project(
        project_name=project_name,
        organization=organization,
        start_date=start_date,
    )
    
    if existing_project:
        # Update existing project
        project = existing_project
        print(f"✅ Updating existing project: '{project.name}'")
        
        # Merge technologies
        new_techs = project_data.get("technical_tools") or project_data.get("technologies_used") or []
        project.all_technologies = merge_technologies(project.all_technologies or [], new_techs)
        
        # Update team size
        project.total_contributors += 1
        
        # Add impact metrics
        new_impact = project_data.get("impact")
        if new_impact:
            if not project.impact_metrics:
                project.impact_metrics = []
            if new_impact not in project.impact_metrics:  # Avoid duplicates
                project.impact_metrics.append(new_impact)
        
    else:
        # Create new project
        print(f"🆕 Creating new project: '{project_name}'")
        project = ProjectDB(
            name=project_name,
            organization=organization,
            start_date=start_date,
            end_date=end_date,
            duration_months=duration_months,
            is_academic=is_academic,
            all_technologies=project_data.get("technical_tools") or project_data.get("technologies_used") or [],
            team_size_estimate=project_data.get("team_size") or 1,
            total_contributors=1,
            impact_metrics=[project_data.get("impact")] if project_data.get("impact") else [],
        )
        db.session.add(project)
        db.session.flush()  # Get project.id
    
    # Create candidate contribution record
    contribution = CandidateProject(
        candidate_id=candidate_id,
        project_id=project.id,
        role=project_data.get("role"),
        description=project_data.get("description"),
        responsibilities=project_data.get("responsibilities") or [],
        technical_tools=project_data.get("technical_tools") or project_data.get("technologies_used") or [],
        contribution=project_data.get("contribution"),
        impact=project_data.get("impact"),
        candidate_start_date=start_date,
        candidate_end_date=end_date,
        candidate_duration_months=duration_months,
    )
    db.session.add(contribution)
    db.session.flush()
    
    # Regenerate project summary
    project.summary = generate_project_summary(project)
    from datetime import datetime
    project.updated_at = datetime.utcnow()
    
    db.session.commit()
    
    print(f"   📊 Summary updated with {project.total_contributors} contributor(s)")
    
    return project, contribution


def process_candidate_projects(candidate_id: int, projects_list: List[Dict]) -> List[Tuple[ProjectDB, CandidateProject]]:
    """
    Process all projects for a candidate.
    
    Args:
        candidate_id: Candidate ID
        projects_list: List of project dicts from parsed resume
    
    Returns:
        List of (ProjectDB, CandidateProject) tuples
    """
    results = []
    
    print(f"\n{'='*60}")
    print(f"📂 Processing {len(projects_list)} project(s) for candidate {candidate_id}")
    print(f"{'='*60}")
    
    for idx, project_data in enumerate(projects_list, 1):
        if not project_data or not project_data.get("name"):
            print(f"⚠️  Skipping project {idx}: No name provided")
            continue
        
        try:
            print(f"\n[{idx}/{len(projects_list)}] Processing: '{project_data.get('name')}'")
            project, contribution = add_candidate_to_project(candidate_id, project_data)
            results.append((project, contribution))
            print(f"✅ Successfully processed project '{project.name}' (ID: {project.id})")
            
        except Exception as e:
            print(f"❌ Error processing project '{project_data.get('name')}': {e}")
            import traceback
            traceback.print_exc()
            continue
    
    print(f"\n{'='*60}")
    print(f"✅ Completed: {len(results)}/{len(projects_list)} projects saved to database")
    print(f"{'='*60}\n")
    
    return results
