from app import app, db
from models import ProjectDB, CandidateProject
import re

def normalize_name(name):
    if not name:
        return ""
    s = name.strip().lower()
    s = re.sub(r'[^\w\s]', ' ', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()

def cleanup_duplicate_projects():
    with app.app_context():
        print("🧹 Cleaning up duplicate projects...")
        
        all_projects = ProjectDB.query.all()
        normalized_map = {}
        
        # Group by normalized name
        for proj in all_projects:
            norm = normalize_name(proj.name)
            if norm not in normalized_map:
                normalized_map[norm] = []
            normalized_map[norm].append(proj)
        
        deleted_count = 0
        
        for norm_name, projects in normalized_map.items():
            if len(projects) <= 1:
                continue
            
            print(f"\n🔍 Found {len(projects)} duplicates of '{projects[0].name}'")
            
            # Keep the one with most contributors
            projects.sort(key=lambda p: p.total_contributors or 0, reverse=True)
            keep = projects[0]
            duplicates = projects[1:]
            
            print(f"   ✅ Keeping: ID {keep.id} ({keep.total_contributors} members)")
            
            # Move all contributors from duplicates to the keeper
            for dup in duplicates:
                contributions = CandidateProject.query.filter_by(project_id=dup.id).all()
                
                for contrib in contributions:
                    # Check if candidate already linked to keeper
                    existing = CandidateProject.query.filter_by(
                        candidate_id=contrib.candidate_id,
                        project_id=keep.id
                    ).first()
                    
                    if not existing:
                        contrib.project_id = keep.id
                        db.session.add(contrib)
                        print(f"   🔗 Moved {contrib.candidate.full_name} from ID {dup.id} to ID {keep.id}")
                
                # Delete the duplicate project
                db.session.delete(dup)
                deleted_count += 1
                print(f"   🗑️  Deleted duplicate ID {dup.id}")
        
            # Update contributor count
            keep.total_contributors = CandidateProject.query.filter_by(project_id=keep.id).count()
            db.session.add(keep)
        
        db.session.commit()
        
        print(f"\n✅ Cleanup complete! Deleted {deleted_count} duplicate projects")
        
        # Show final state
        remaining = ProjectDB.query.all()
        print(f"📊 Final count: {len(remaining)} unique projects")

if __name__ == "__main__":
    cleanup_duplicate_projects()
