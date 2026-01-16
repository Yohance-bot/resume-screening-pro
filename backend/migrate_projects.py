from app import app, db
from models import Candidate, ProjectDB, CandidateProject
import re

def normalize_project_key(name):
    if not name:
        return ""
    s = name.strip().lower()
    s = re.sub(r'[^\w\s]', ' ', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()

def migrate_projects():
    with app.app_context():
        print("🚀 Starting project migration...")
        
        all_candidates = Candidate.query.all()
        project_map = {}
        migrated_count = 0
        
        print("\n📋 Step 1: Finding all unique projects...")
        for candidate in all_candidates:
            parsed = candidate.parsed or {}
            projects = parsed.get("projects") or []
            
            for p in projects:
                if not isinstance(p, dict):
                    continue
                
                project_name = p.get("name") or p.get("project_name")
                if not project_name:
                    continue
                
                normalized = normalize_project_key(project_name)
                
                if normalized in project_map:
                    continue
                
                project_db = ProjectDB(
                    name=project_name,
                    organization=p.get("organization") or p.get("company"),
                    start_date=p.get("start_date") or p.get("startdate"),
                    end_date=p.get("end_date") or p.get("enddate"),
                    duration_months=p.get("duration_months"),
                    is_academic=p.get("is_academic", False),
                    summary=p.get("description") or p.get("summary"),
                    all_technologies=p.get("technologies_used") or p.get("tech_stack") or p.get("technologies") or [],
                )
                
                db.session.add(project_db)
                db.session.flush()
                
                project_map[normalized] = project_db
                print(f"  ✅ Created project: {project_name} (ID: {project_db.id})")
        
        db.session.commit()
        print(f"\n✅ Created {len(project_map)} unique projects")
        
        print("\n📋 Step 2: Linking candidates to projects...")
        for candidate in all_candidates:
            parsed = candidate.parsed or {}
            projects = parsed.get("projects") or []
            
            for p in projects:
                if not isinstance(p, dict):
                    continue
                
                project_name = p.get("name") or p.get("project_name")
                if not project_name:
                    continue
                
                normalized = normalize_project_key(project_name)
                project_db = project_map.get(normalized)
                
                if not project_db:
                    continue
                
                existing = CandidateProject.query.filter_by(
                    candidate_id=candidate.id,
                    project_id=project_db.id
                ).first()
                
                if existing:
                    continue
                
                candidate_project = CandidateProject(
                    candidate_id=candidate.id,
                    project_id=project_db.id,
                    role=p.get("role") or candidate.primary_role,
                    description=p.get("description"),
                    responsibilities=p.get("responsibilities") or [],
                    technical_tools=p.get("technologies_used") or p.get("tech_stack") or p.get("technologies") or [],
                    contribution=p.get("contribution"),
                    impact=p.get("impact"),
                    candidate_start_date=p.get("start_date") or p.get("startdate"),
                    candidate_end_date=p.get("end_date") or p.get("enddate"),
                    candidate_duration_months=p.get("duration_months"),
                )
                
                db.session.add(candidate_project)
                migrated_count += 1
                print(f"  ✅ Linked {candidate.full_name} → {project_name}")
        
        print("\n📋 Step 3: Updating team counts...")
        for project_db in project_map.values():
            count = CandidateProject.query.filter_by(project_id=project_db.id).count()
            project_db.total_contributors = count
            print(f"  ✅ {project_db.name}: {count} members")
        
        db.session.commit()
        
        print(f"\n🎉 Migration complete!")
        print(f"   Projects created: {len(project_map)}")
        print(f"   Candidate-Project links: {migrated_count}")

if __name__ == "__main__":
    migrate_projects()
