from flask import Flask, jsonify
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

@app.route('/')
def health():
    return jsonify({"status": "Resume API running!", "timestamp": os.environ.get('PORT', 5000)})

@app.route('/api/test')
def test():
    return jsonify({"message": "Backend connected successfully!"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(basedir, "resume_screening.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key')

# Initialize shared extensions
db.init_app(app)
migrate.init_app(app, db)
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

# Register auth blueprint
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)

# Add unauthorized handler to prevent redirects for API routes
@login_manager.unauthorized_handler
def unauthorized():
    # Check if the request is for an API endpoint
    if request.path.startswith('/api/'):
        return jsonify({"error": "Unauthorized"}), 401
    # For non-API routes, return JSON too (avoid redirect loops in SPA setups)
    return jsonify({"error": "Unauthorized"}), 401

# Create tables and seed admin user
with app.app_context():
    db.create_all()

    # Lightweight schema upgrade for SQLite (avoids requiring manual migrations)
    try:
        existing_cols = {
            row[1]
            for row in db.session.execute(sql_text('PRAGMA table_info(users)')).fetchall()
        }
        alter_stmts = []
        if 'name' not in existing_cols:
            alter_stmts.append("ALTER TABLE users ADD COLUMN name VARCHAR(120)")
        if 'email' not in existing_cols:
            alter_stmts.append("ALTER TABLE users ADD COLUMN email VARCHAR(255)")
        if 'force_password_change' not in existing_cols:
            alter_stmts.append(
                "ALTER TABLE users ADD COLUMN force_password_change BOOLEAN NOT NULL DEFAULT 0"
            )
        if 'last_login' not in existing_cols:
            alter_stmts.append("ALTER TABLE users ADD COLUMN last_login DATETIME")

        for stmt in alter_stmts:
            db.session.execute(sql_text(stmt))
        if alter_stmts:
            db.session.commit()
    except Exception:
        # If this fails, app can still run; migrations can be applied later.
        db.session.rollback()
    
    # Create default admin user if not exists
    from auth_models import User
    admin = User.query.filter_by(username='happyadmin').first()
    if not admin:
        admin = User(username='happyadmin', email='happyadmin@happiestminds.com', name='Happy Admin', role='admin', force_password_change=False)
        admin.set_password('Smiles@123')
        db.session.add(admin)
        db.session.commit()
        print("✅ Created admin user: happyadmin / Smiles@123")
    else:
        # Ensure existing admin has required fields
        updated = False
        if not getattr(admin, 'email', None):
            admin.email = 'happyadmin@happiestminds.com'
            updated = True
        if not getattr(admin, 'name', None):
            admin.name = 'Happy Admin'
            updated = True
        if getattr(admin, 'force_password_change', None) is None:
            admin.force_password_change = False
            updated = True
        if updated:
            db.session.commit()
        print("ℹ️ Admin user already exists")

@app.route("/dashboard")
def dashboard_stats():
    try:
        total_resumes = Candidate.query.count()
    except Exception:
        total_resumes = 0
    try:
        total_jds = JD.query.count()
    except Exception:
        total_jds = 0
    return jsonify({"total_resumes": total_resumes, "total_jds": total_jds, "pending": 0})

@app.route("/api/employees")
def list_employees():
    return jsonify([])

# RAG + chat orchestrator
pipeline = RAGResumePipeline()
orchestrator = ChatOrchestrator()

CURRENT_JD: Dict[str, Any] = {"text": ""}

def extract_dates_from_project_description(project: dict) -> dict:
    """
    Extract start_date, end_date, and duration from project name/description.
    If no dates found, project remains archived (start_date=None, end_date=None).
    """
    # If we already have dates, skip
    if project.get("start_date") and project.get("end_date"):
        return project
    
    # Build search text - prioritize name, then description
    search_texts = []
    if project.get("name"):
        search_texts.append(("name", project["name"]))
    if project.get("description"):
        search_texts.append(("description", project["description"]))
    
    if not search_texts:
        return project
    
    # Try to extract dates from each text source
    for source, text in search_texts:
        
        # Pattern 1: Parentheses format "(Month Year – Month Year)"
        # Matches: "(June 2024 – December 2024)", "(May 2024 - June 2024)"
        paren_pattern = r'\(([A-Z][a-z]{2,8}\s+\d{4})\s*[–\-—]\s*([A-Z][a-z]{2,8}\s+\d{4}|Present|Current|Ongoing)\)'
        match = re.search(paren_pattern, text, re.IGNORECASE)
        
        if match:
            project["start_date"] = match.group(1).strip()
            end = match.group(2).strip()
            if end.lower() in ["present", "current", "ongoing"]:
                project["end_date"] = "Present"
            else:
                project["end_date"] = end
            print(f"   ✅ Extracted from {source} (parentheses): {project['start_date']} → {project['end_date']}")
            break
        
        # Pattern 2: "Month Year – Month Year" (no parentheses)
        # Matches: "June 2024 – December 2024", "May 2024 - June 2024"
        date_range_pattern = r'([A-Z][a-z]{2,8}\s+\d{4})\s*[–\-—]\s*([A-Z][a-z]{2,8}\s+\d{4}|Present|Current|Ongoing)'
        match = re.search(date_range_pattern, text, re.IGNORECASE)
        
        if match:
            project["start_date"] = match.group(1).strip()
            end = match.group(2).strip()
            if end.lower() in ["present", "current", "ongoing"]:
                project["end_date"] = "Present"
            else:
                project["end_date"] = end
            print(f"   ✅ Extracted from {source}: {project['start_date']} → {project['end_date']}")
            break
        
        # Pattern 3: "YYYY-MM to YYYY-MM"
        iso_range_pattern = r'(\d{4}-\d{2})\s*(?:to|-|–)\s*(\d{4}-\d{2}|Present|Current|Ongoing)'
        match = re.search(iso_range_pattern, text, re.IGNORECASE)
        
        if match:
            project["start_date"] = match.group(1).strip()
            project["end_date"] = match.group(2).strip()
            print(f"   ✅ Extracted ISO dates from {source}: {project['start_date']} → {project['end_date']}")
            break
    
    # If no dates found, leave as None (will be archived)
    if not project.get("start_date") and not project.get("end_date"):
        print(f"   ℹ️  No dates found - will be archived")
        return project
    
    # Calculate duration if we have both dates
    if project.get("start_date") and project.get("end_date") and not project.get("duration_months"):
        try:
            start = project["start_date"]
            end = project["end_date"]
            
            if end.lower() in ["present", "current", "ongoing"]:
                end = datetime.now().strftime("%B %Y")
            
            # Parse dates (handle multiple formats)
            for fmt in ["%B %Y", "%b %Y", "%Y-%m"]:
                try:
                    start_dt = datetime.strptime(start, fmt)
                    end_dt = datetime.strptime(end, fmt)
                    
                    # Calculate inclusive months
                    months = (end_dt.year - start_dt.year) * 12 + (end_dt.month - start_dt.month) + 1
                    project["duration_months"] = max(1, months)
                    print(f"   ✅ Calculated duration: {project['duration_months']} months")
                    break
                except:
                    continue
        except Exception as e:
            print(f"   ⚠️ Could not calculate duration: {e}")
    
    return project

def calculate_project_duration(project: dict) -> dict:
    """
    Calculate duration_months from start_date and end_date if both exist.
    Works with formats: "June 2024", "Jun 2024", "2024-06"
    """
    if not project.get("start_date") or not project.get("end_date"):
        return project
    
    # If duration already calculated, skip
    if project.get("duration_months"):
        return project
    
    try:
        start = project["start_date"]
        end = project["end_date"]
        
        # Handle "Present" as current date
        if end.lower() in ["present", "current", "ongoing", "in progress"]:
            end = datetime.now().strftime("%B %Y")
        
        # Try multiple date formats
        parsed_start = None
        parsed_end = None
        
        for fmt in ["%B %Y", "%b %Y", "%Y-%m"]:
            try:
                parsed_start = datetime.strptime(start, fmt)
                parsed_end = datetime.strptime(end, fmt)
                break
            except:
                continue
        
        if parsed_start and parsed_end:
            # Calculate inclusive months (June 2024 to December 2024 = 7 months)
            months = (parsed_end.year - parsed_start.year) * 12 + (parsed_end.month - parsed_start.month) + 1
            project["duration_months"] = max(1, months)
            print(f"   ✅ Calculated duration: {project['duration_months']} months ({start} to {end})")
        else:
            print(f"   ⚠️ Could not parse dates for duration calculation")
            
    except Exception as e:
        print(f"   ⚠️ Duration calculation error: {e}")
    
    return project

def find_matching_project(new_project: dict) -> 'ProjectDB | None':
    """
    Find if a project already exists in ProjectDB based on name and organization.
    Returns the matching ProjectDB object or None.
    """
    from models import ProjectDB
    
    project_name = (new_project.get("name") or "").strip()
    organization = (new_project.get("organization") or "").strip()  # ✅ FIX: Handle None
    
    if not project_name:
        return None
    
    # Try exact match first
    query = ProjectDB.query.filter(ProjectDB.name.ilike(f"%{project_name}%"))
    
    if organization:  # ✅ Only filter by org if it exists
        query = query.filter(ProjectDB.organization.ilike(f"%{organization}%"))
    
    candidates = query.all()
    
    if not candidates:
        return None
    
    # If multiple matches, find best one by similarity
    best_match = None
    best_score = 0.0
    
    for candidate_proj in candidates:
        # Calculate similarity score (0-100)
        name_score = fuzz.ratio(project_name.lower(), candidate_proj.name.lower())
        
        if organization and candidate_proj.organization:
            org_score = fuzz.ratio(organization.lower(), candidate_proj.organization.lower())
            total_score = (name_score * 0.7) + (org_score * 0.3)
        else:
            total_score = name_score
        
        if total_score > best_score and total_score >= 75:  # 75% threshold
            best_score = total_score
            best_match = candidate_proj
    
    return best_match

def update_project_summary(project: 'ProjectDB'):
    """
    Auto-generate a comprehensive project summary from all contributors.
    Creates a formatted summary with team contributions.
    """
    if not project.contributions:
        project.summary = f"**{project.name}**\n\nNo team contributions yet."
        return
    
    # Build summary sections
    sections = []
    
    # 1. Project Overview (from first contributor's description)
    first_desc = None
    for contrib in project.contributions:
        if contrib.description:
            first_desc = contrib.description
            break
    
    if first_desc:
        sections.append(f"**Overview:** {first_desc}")
    
    # 2. Technologies (merged from all contributors)
    if project.all_technologies:
        tech_str = ", ".join(sorted(project.all_technologies))
        sections.append(f"**Technologies:** {tech_str}")
    
    # 3. Team Contributions (list each person's role and responsibilities)
    team_section = ["**Team Contributions:**"]
    for contrib in project.contributions:
        if contrib.candidate:
            name = contrib.candidate.full_name or "Unknown"
            role = contrib.role or "Team Member"
            
            # Format responsibilities
            if contrib.responsibilities:
                resp_bullets = "; ".join(contrib.responsibilities[:3])  # Top 3
                team_section.append(f"- *{name} ({role}):* {resp_bullets}")
            else:
                team_section.append(f"- *{name} ({role})*")
    
    sections.append("\n".join(team_section))
    
    # 4. Impact Metrics (if any)
    impacts = []
    for contrib in project.contributions:
        if contrib.impact:
            impacts.append(contrib.impact)
    
    if impacts:
        impact_str = " | ".join(impacts)
        sections.append(f"**Impact:** {impact_str}")
    
    # 5. Team Size
    sections.append(f"**Team Size:** {project.total_contributors} contributor(s)")
    
    # Combine all sections
    project.summary = "\n\n".join(sections)

def process_and_save_projects(candidate: "Candidate"):
    """
    Process candidate's projects and save to ProjectDB with deduplication.

    FIXES:
    - Prevent duplicate CandidateProject rows on re-upload by "upserting" the
      association (candidate_id, project_id) instead of always inserting.
    - Keep project.total_contributors accurate by counting distinct links.
    - Commit once at the end for speed and to reduce partial-save issues.
    """
    from models import ProjectDB, CandidateProject
    from sqlalchemy import func

    parsed = candidate.parsed or {}
    candidate_projects = parsed.get("projects", [])

    if not candidate_projects:
        return

    print(f"\n📂 Processing {len(candidate_projects)} projects for {candidate.full_name}")
    print("=" * 60)

    saved_count = 0
    updated_links = 0
    created_links = 0

    llm_merge_checks_used = 0
    LLM_MERGE_CHECK_LIMIT = 8
    SIMILARITY_THRESHOLD = 0.86

    try:
        for idx, proj in enumerate(candidate_projects, 1):
            if not proj or not proj.get("name"):
                continue

            print(f"\n[{idx}/{len(candidate_projects)}] Processing: '{proj.get('name')}'")

            # ✅ Show dates from LLM
            if proj.get("start_date") or proj.get("end_date"):
                print(f"   📅 LLM extracted: {proj.get('start_date')} → {proj.get('end_date')}")

            # ✅ Step 1: Extract dates from description if missing
            proj = extract_dates_from_project_description(proj)

            # ✅ Step 2: Calculate duration from dates
            proj = calculate_project_duration(proj)

            # ✅ Show final summary
            if proj.get("start_date") or proj.get("end_date"):
                duration_str = f" ({proj.get('duration_months')} months)" if proj.get("duration_months") else ""
                print(f"   ✅ Final: {proj.get('start_date')} → {proj.get('end_date')}{duration_str}")
            else:
                print(f"   ℹ️  No dates - will be archived")

            # Check if project already exists (by name + organization)
            existing_project = find_matching_project(proj)

            if existing_project:
                print(f"🔍 Found matching project: '{existing_project.name}' (score: 100.00%)")
                print(f"✅ Updating existing project: '{existing_project.name}'")
                project_db = existing_project

                # Merge technologies
                existing_techs = set(project_db.all_technologies or [])
                new_techs = set(proj.get("technical_tools") or proj.get("technologies_used") or [])
                project_db.all_technologies = list(existing_techs | new_techs)

                # Update dates if new ones are more specific
                if proj.get("start_date") and not project_db.start_date:
                    project_db.start_date = proj.get("start_date")
                if proj.get("end_date") and not project_db.end_date:
                    project_db.end_date = proj.get("end_date")
                if proj.get("duration_months") and not project_db.duration_months:
                    project_db.duration_months = proj.get("duration_months")

                db.session.add(project_db)

            else:
                # LLM-assisted dedupe (to prevent near-duplicate projects from being created)
                project_db = None

                if llm_merge_checks_used < LLM_MERGE_CHECK_LIMIT:
                    try:
                        candidates = ProjectDB.query.filter(ProjectDB.merged_into_id.is_(None)).limit(1000).all()
                    except Exception:
                        candidates = ProjectDB.query.limit(1000).all()

                    best = None
                    best_score = 0.0
                    incoming = {
                        "name": proj.get("name"),
                        "organization": proj.get("organization"),
                        "description": proj.get("description") or proj.get("summary"),
                        "technical_tools": proj.get("technical_tools") or proj.get("technologies_used") or [],
                    }

                    for cand_proj in candidates:
                        cand_dict = {
                            "name": cand_proj.name,
                            "organization": cand_proj.organization,
                            "description": cand_proj.summary,
                            "technical_tools": cand_proj.all_technologies or [],
                        }
                        score = calculate_project_similarity(incoming, cand_dict)
                        if score > best_score:
                            best_score = score
                            best = cand_proj

                    if best and best_score >= SIMILARITY_THRESHOLD:
                        prompt = f"""
You are deduplicating projects during resume ingestion.
Decide if the INCOMING project should be merged into the EXISTING canonical project.

Return ONLY JSON:
- same_project: boolean
- confidence: number (0-1)
- reason: string

INCOMING project:
name: {incoming.get('name')}
organization: {incoming.get('organization')}
description: {incoming.get('description')}
technologies: {incoming.get('technical_tools')}

EXISTING project (id={best.id}):
name: {best.name}
organization: {best.organization}
summary: {best.summary}
technologies: {best.all_technologies or []}
"""
                        try:
                            llm_out = _groq_json(prompt)
                            llm_merge_checks_used += 1
                        except Exception as e:
                            llm_out = {"same_project": False, "confidence": 0, "reason": f"LLM error: {e}"}

                        if llm_out.get("same_project") is True:
                            print(f"🤝 LLM dedupe: using existing project '{best.name}' (ID {best.id})")
                            print(f"   Similarity: {best_score:.2f}")
                            print(f"   Reason: {llm_out.get('reason')}")
                            project_db = best

                if not project_db:
                    print(f"🆕 Creating new project: '{proj.get('name')}'")
                    project_db = ProjectDB(
                        name=proj.get("name"),
                        organization=proj.get("organization"),
                        start_date=proj.get("start_date"),
                        end_date=proj.get("end_date"),
                        duration_months=proj.get("duration_months"),
                        is_academic=proj.get("is_academic", False),
                        all_technologies=proj.get("technical_tools") or proj.get("technologies_used") or [],
                        team_size_estimate=proj.get("team_size"),
                        total_contributors=0,  # will set after link upsert
                        impact_metrics=proj.get("impact_metrics") or [],
                    )
                    db.session.add(project_db)
                    db.session.flush()  # ensure project_db.id exists

            # ✅ UPSERT CandidateProject link (prevents duplicates on re-upload)
            existing_link = CandidateProject.query.filter_by(
                candidate_id=candidate.id,
                project_id=project_db.id,
            ).first()

            if existing_link:
                # Update fields (so re-upload can enrich info)
                existing_link.role = proj.get("role") or existing_link.role
                existing_link.description = proj.get("description") or existing_link.description
                existing_link.responsibilities = proj.get("responsibilities") or existing_link.responsibilities or []
                existing_link.technical_tools = (
                    proj.get("technical_tools") or proj.get("technologies_used") or existing_link.technical_tools or []
                )
                existing_link.contribution = proj.get("contribution") or existing_link.contribution
                existing_link.impact = proj.get("impact") or existing_link.impact
                existing_link.candidate_start_date = proj.get("start_date") or existing_link.candidate_start_date
                existing_link.candidate_end_date = proj.get("end_date") or existing_link.candidate_end_date
                existing_link.candidate_duration_months = proj.get("duration_months") or existing_link.candidate_duration_months

                db.session.add(existing_link)
                updated_links += 1
                print(f"   🔁 Link exists — updated contributor fields for candidate {candidate.id}")

            else:
                candidate_proj = CandidateProject(
                    candidate_id=candidate.id,
                    project_id=project_db.id,
                    role=proj.get("role"),
                    description=proj.get("description"),
                    responsibilities=proj.get("responsibilities") or [],
                    technical_tools=proj.get("technical_tools") or proj.get("technologies_used") or [],
                    contribution=proj.get("contribution"),
                    impact=proj.get("impact"),
                    candidate_start_date=proj.get("start_date"),
                    candidate_end_date=proj.get("end_date"),
                    candidate_duration_months=proj.get("duration_months"),
                )
                db.session.add(candidate_proj)
                created_links += 1
                print(f"   ➕ Created new contributor link for candidate {candidate.id}")

            # Update project summary (if this reads from DB, it will see pending changes after flush)
            update_project_summary(project_db)

            # Update contributor count from DB (distinct candidates)
            project_db.total_contributors = (
                db.session.query(func.count(func.distinct(CandidateProject.candidate_id)))
                .filter(CandidateProject.project_id == project_db.id)
                .scalar()
            ) or 0
            db.session.add(project_db)

            saved_count += 1
            print(f"   📊 Summary updated with {project_db.total_contributors} contributor(s)")
            print(f"✅ Successfully processed project '{proj.get('name')}' (ID: {project_db.id})")

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        print(f"❌ Error processing projects for {candidate.full_name}: {e}")
        import traceback
        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print(f"✅ Completed: {saved_count}/{len(candidate_projects)} projects processed")
    print(f"   Links created: {created_links}, links updated: {updated_links}")
    print("=" * 60)

def _normalize_project_key(name: str | None) -> str | None:
    """Normalize project name for matching (helper function)"""
    if not name:
        return None
    return " ".join(name.strip().lower().split())

def simple_intent_check(message: str) -> dict:
    """Minimal intent classifier - no external deps"""
    raw = message.strip().upper()
    text = message.lower()
    
    # 🔎 Direct SID → JD lookup, e.g. "#sidcode 500000"
    sidcode_match = re.search(r'#sidcode\s*[:=]?\s*([a-z0-9_-]+)', text)
    if sidcode_match:
        sid = sidcode_match.group(1).strip()
        return {
            "type": "sid_lookup",
            "sid": sid,
            "via_command": True
        }

    if raw.startswith("AIRANK"):
        sid_match = re.search(r'(?:sid|jd)[:=]?\s*([A-Z0-9]+)', text)
        sid = sid_match.group(1) if sid_match else None
        return {"type": "ai_rank", "sid": sid, "role": message[6:].strip(), "via_command": True}
    
    if raw.startswith("TEAM") or any(kw in text for kw in ['assign', 'add to team', 'remove from team']):
        return {"type": "team_management", "raw": message, "via_command": True}
    
    if raw.startswith("EDIT"):
        return {"type": "edit_candidate", "instruction": message[4:].strip(), "via_command": True}
    
    if raw.startswith("CANDIDATERANK"):
        # Extract candidate ID from message
        candidate_match = re.search(r'candidate[:=]?\s*(\d+)', text, re.IGNORECASE)
        candidate_id = candidate_match.group(1) if candidate_match else None
        bucket_match = re.search(r'bucket[:=]?\s*(\w+)', text, re.IGNORECASE)
        bucket = bucket_match.group(1) if bucket_match else "all"
        
        return {"type": "candidate_rank", "candidate_id": candidate_id, "bucket": bucket, "via_command": True}
    
    return {"type": "generic"}

def get_history(session_id):
    """Get chat history for intent classifier"""
    return []  # Empty for now - add your history logic later

def handle_smart_rank(intent, session_id):
    """Smart ranking using the advanced screening algorithm"""
    from services.smart_screening import smart_screen_candidate
    
    sid = intent.get("sid")
    bucket = intent.get("bucket", "all")
    bench_status = intent.get("bench_status", "all")
    
    print(f"🎯 SMART RANK: sid={sid}, bucket={bucket}, bench={bench_status}")
    
    if not sid:
        return jsonify({
            "session_id": session_id or str(uuid.uuid4()),
            "message": "❌ Job SID required for ranking",
            "structured": {"type": "error"}
        })
    
    try:
        # Get JD
        jd = JD.query.filter_by(sid=sid).first()
        if not jd:
            return jsonify({
                "session_id": session_id or str(uuid.uuid4()),
                "message": f"❌ JD #{sid} not found",
                "structured": {"type": "error"}
            })
        
        jd_parsed = getattr(jd, "parsed", {}) or {}
        if isinstance(jd_parsed, str):
            try:
                jd_parsed = json.loads(jd_parsed)
            except Exception:
                jd_parsed = {}
        if not isinstance(jd_parsed, dict):
            jd_parsed = {}

        required_skills = jd_parsed.get("required_skills") or []
        bonus_skills = jd_parsed.get("bonus_skills") or []

        # Fallback: parse free-text skills column
        if not required_skills:
            skills_text = (getattr(jd, "skills", None) or "").strip()
            if skills_text:
                required_skills = [s.strip() for s in re.split(r"[,;\n]+", skills_text) if s.strip()]

        # Build JD dict for screening
        jd_dict = {
            "required_skills": required_skills,
            "bonus_skills": bonus_skills,
            "competency": getattr(jd, 'competency', '') or "",
            "designation": getattr(jd, 'designation', '') or "",
            "job_description": getattr(jd, 'job_description', '') or "",
        }
        
        # Query candidates with filters
        query = Candidate.query
        if bucket != "all":
            query = query.filter(Candidate.role_bucket == bucket)
        if bench_status == "on":
            query = query.filter(Candidate.on_bench == True)
        elif bench_status == "off":
            query = query.filter(Candidate.on_bench == False)
        
        candidates = query.limit(50).all()
        
        if not candidates:
            return jsonify({
                "session_id": session_id or str(uuid.uuid4()),
                "message": f"No candidates match filters for JD #{sid}",
                "structured": {"type": "error"}
            })
        
        # Score candidates using smart screening
        rankings = []
        for cand in candidates:
            try:
                cand_parsed = getattr(cand, "parsed", {}) or {}
                if isinstance(cand_parsed, str):
                    try:
                        cand_parsed = json.loads(cand_parsed)
                    except Exception:
                        cand_parsed = {}
                if not isinstance(cand_parsed, dict):
                    cand_parsed = {}

                skills = (
                    getattr(cand, "skills", None)
                    or cand_parsed.get("skills")
                    or cand_parsed.get("technical_skills")
                    or []
                )
                if isinstance(skills, str):
                    skills = [s.strip() for s in re.split(r"[,;\n]+", skills) if s.strip()]

                roles = (
                    getattr(cand, "work_experiences", None)
                    or cand_parsed.get("roles")
                    or cand_parsed.get("work_experiences")
                    or []
                )

                cand_dict = {
                    "id": cand.id,
                    "full_name": getattr(cand, 'full_name', f"Candidate {cand.id}"),
                    "skills": skills or [],
                    "roles": roles or [],
                    "total_experience_years": getattr(cand, 'total_experience_years', 0) or 0,
                }
                
                score_result = smart_screen_candidate(cand_dict, jd_dict)
                rankings.append({
                    "rank": 0,  # Will be set after sorting
                    "candidate_id": cand.id,
                    "candidate_name": score_result["candidate_name"],
                    "score": score_result["final_score"],
                    "reasoning": f"Tech: {score_result['tech_score']}%, Exp: {score_result['experience_score']}%, Matrix: {score_result['matrix_score']}%"
                })
            except Exception as e:
                print(f"⚠️ Error scoring candidate {cand.id}: {e}")
                continue
        
        # Sort and rank
        rankings.sort(key=lambda x: x["score"], reverse=True)
        for i, rank in enumerate(rankings[:15], 1):
            rank["rank"] = i
        
        jd_title = jd.designation or jd.competency or "JD"

        rows = []
        for r in rankings[:10]:
            rows.append({
                "rank": r.get("rank"),
                "name": r.get("candidate_name") or "Unknown",
                "score": r.get("score"),
                "experience": "",
                "skills": "",
                "reason": r.get("reasoning") or "",
            })

        message = f"Top candidates for JD {jd.sid} ({jd_title})"
        return jsonify({
            "session_id": session_id,
            "message": message,
            "structured": {
                "type": "ranking",
                "role": f"{jd.sid} - {jd_title}",
                "rows": rows,
                "total_candidates": len(candidates),
            }
        })
        
    except Exception as e:
        print(f"🚨 Smart ranking error: {e}")
        return jsonify({
            "session_id": session_id,
            "message": f"Ranking failed: {str(e)}",
            "structured": {"type": "error"}
        })


def handle_candidate_rank(intent, session_id):
    """Rank all JDs against a single candidate (reverse ranking)"""
    from services.smart_screening import smart_screen_candidate
    
    candidate_id = intent.get("candidate_id")
    bucket = intent.get("bucket", "all")
    
    print(f"🎯 CANDIDATE RANK: candidate_id={candidate_id}, bucket={bucket}")
    
    if not candidate_id:
        return jsonify({
            "session_id": session_id or str(uuid.uuid4()),
            "message": "❌ Candidate ID required for ranking",
            "structured": {"type": "error"}
        })
    
    try:
        # Get candidate
        candidate = Candidate.query.filter_by(id=candidate_id).first()
        if not candidate:
            return jsonify({
                "session_id": session_id or str(uuid.uuid4()),
                "message": f"❌ Candidate #{candidate_id} not found",
                "structured": {"type": "error"}
            })
        
        cand_parsed = getattr(candidate, "parsed", {}) or {}
        if isinstance(cand_parsed, str):
            try:
                cand_parsed = json.loads(cand_parsed)
            except Exception:
                cand_parsed = {}
        if not isinstance(cand_parsed, dict):
            cand_parsed = {}

        cand_skills = (
            getattr(candidate, "skills", None)
            or cand_parsed.get("skills")
            or cand_parsed.get("technical_skills")
            or []
        )
        if isinstance(cand_skills, str):
            cand_skills = [s.strip() for s in re.split(r"[,;\n]+", cand_skills) if s.strip()]

        cand_roles = (
            getattr(candidate, "work_experiences", None)
            or cand_parsed.get("roles")
            or cand_parsed.get("work_experiences")
            or []
        )

        # Build candidate dict for screening
        candidate_dict = {
            "id": candidate.id,
            "full_name": getattr(candidate, 'full_name', f"Candidate {candidate.id}"),
            "skills": cand_skills or [],
            "roles": cand_roles or [],
            "total_experience_years": getattr(candidate, 'total_experience_years', 0) or 0,
        }
        
        # Query JDs with filters
        query = JD.query
        if bucket != "all":
            # Filter JDs by competency/bucket if needed
            if bucket == "data_scientist":
                query = query.filter(JD.competency.ilike('%data scientist%'))
            elif bucket == "data_practice":
                query = query.filter(JD.competency.ilike('%data engineer%') | JD.competency.ilike('%data practice%'))
        
        jds = query.limit(50).all()
        
        if not jds:
            return jsonify({
                "session_id": session_id or str(uuid.uuid4()),
                "message": f"No JDs match filters for candidate #{candidate_id}",
                "structured": {"type": "error"}
            })
        
        # Score JDs using smart screening (reversed)
        rankings = []
        for jd in jds:
            try:
                jd_parsed = getattr(jd, "parsed", {}) or {}
                if isinstance(jd_parsed, str):
                    try:
                        jd_parsed = json.loads(jd_parsed)
                    except Exception:
                        jd_parsed = {}
                if not isinstance(jd_parsed, dict):
                    jd_parsed = {}

                required_skills = jd_parsed.get("required_skills") or []
                bonus_skills = jd_parsed.get("bonus_skills") or []

                if not required_skills:
                    skills_text = (getattr(jd, "skills", None) or "").strip()
                    if skills_text:
                        required_skills = [s.strip() for s in re.split(r"[,;\n]+", skills_text) if s.strip()]

                jd_dict = {
                    "required_skills": required_skills,
                    "bonus_skills": bonus_skills,
                    "competency": getattr(jd, 'competency', '') or "",
                    "designation": getattr(jd, 'designation', '') or "",
                    "job_description": getattr(jd, 'job_description', '') or "",
                }
                
                score_result = smart_screen_candidate(candidate_dict, jd_dict)
                rankings.append({
                    "rank": 0,  # Will be set after sorting
                    "jd_id": jd.id,
                    "jd_sid": getattr(jd, 'sid', f"JD{jd.id}"),
                    "jd_title": score_result.get("jd_title", jd_dict["designation"]),
                    "score": score_result["final_score"],
                    "reasoning": f"Tech: {score_result['tech_score']}%, Exp: {score_result['experience_score']}%, Matrix: {score_result['matrix_score']}%"
                })
            except Exception as e:
                print(f"⚠️ Error scoring JD {jd.id}: {e}")
                continue
        
        # Sort and rank
        rankings.sort(key=lambda x: x["score"], reverse=True)
        for i, rank in enumerate(rankings[:15], 1):
            rank["rank"] = i
        
        # Map to the same shape the frontend RankingTable expects.
        # We reuse structured.type='ranking' so MessageBubble renders RankingTable.
        rows = []
        for r in rankings[:10]:
            title = r.get("jd_title") or "JD"
            sid_label = f"#{r.get('jd_sid')}" if r.get("jd_sid") is not None else ""
            name = f"{sid_label} {title}".strip()
            rows.append({
                "rank": r.get("rank"),
                "name": name,
                "score": r.get("score"),
                "experience": "",
                "skills": "",
                "reason": r.get("reasoning") or "",
            })

        message = f"Top JD matches for {candidate_dict['full_name']}"
        return jsonify({
            "session_id": session_id,
            "message": message,
            "structured": {
                "type": "ranking",
                "role": f"JD fit for {candidate_dict['full_name']}",
                "rows": rows,
                "total_candidates": len(jds),
            }
        })
        
    except Exception as e:
        print(f"🚨 Candidate ranking error: {e}")
        return jsonify({
            "session_id": session_id,
            "message": f"Ranking failed: {str(e)}",
            "structured": {"type": "error"}
        })


def handle_sid_lookup(intent, session_id):
    """
    Handle "#sidcode 500000" style messages and return full JD data for that SID.
    """
    sid = (intent.get("sid") or "").strip()
    print(f"🔎 SID LOOKUP: sid={sid}")

    if not sid:
        return jsonify({
            "session_id": session_id or str(uuid.uuid4()),
            "message": "❌ Please provide a SID after #sidcode, e.g. `#sidcode 500000`.",
            "structured": {"type": "error", "data": {"reason": "missing_sid"}}
        })

    jd = JD.query.filter_by(sid=sid).first()
    if not jd:
        return jsonify({
            "session_id": session_id or str(uuid.uuid4()),
            "message": f"❌ No JD found for SID `{sid}`.",
            "structured": {"type": "jd_not_found", "data": {"sid": sid}}
        })

    # Mirror the /api/jds shape, but for a single JD
    jd_data = {
        "sid": jd.sid,
        "title": jd.designation or "Unnamed JD",
        "comments": jd.comments or "",
        "sub_bu": jd.sub_bu or "",
        "account": jd.account or "",
        "project": jd.project or "",
        "sub_practice_name": jd.sub_practice_name or "",

        "competency": jd.competency or "",
        "designation": jd.designation or "",
        "description": jd.job_description or "",
        "skills": (jd.parsed.get("required_skills", []) if jd.parsed else [])
                  + (jd.parsed.get("bonus_skills", []) if jd.parsed else []),

        "billability": jd.billability or "",
        "billing_type": jd.billing_type or "",
        "probability": float(jd.probability) if jd.probability else 0.0,
        "billed_pct": jd.billed_pct or "",
        "project_type": jd.project_type or "",
        "governance_category": jd.governance_category or "",

        "customer_interview": jd.customer_interview or "",
        "position_type": jd.position_type or "",
        "location_type": jd.location_type or "",
        "base_location_country": jd.base_location_country or "",
        "base_location_city": jd.base_location_city or "",
        "facility": jd.facility or "",
        "fulfilment_type": jd.fulfilment_type or "",

        "approval_status": jd.approval_status or "",
        "sid_status": jd.sid_status or "",
        "identified_empid": jd.identified_empid or "",
        "identified_empname": jd.identified_empname or "",
        "original_billable_date": jd.original_billable_date or "",
        "updated_billable_date": jd.updated_billable_date or "",
        "billing_end_date": jd.billing_end_date or "",
        "requirement_expiry_date": jd.requirement_expiry_date or "",
        "resource_required_date": jd.resource_required_date or "",
        "requirement_initiated_date": jd.requirement_initiated_date or "",
        "month": jd.month or "",
        "request_initiated_by": getattr(jd, "request_initiated_by", "") or "",
        "dm": jd.dm or "",
        "bdm": jd.bdm or "",

        "remarks": jd.remarks or "",
        "reason_for_cancel": jd.reason_for_cancel or "",
        "reason_for_lost": jd.reason_for_lost or "",
        "replacement_employee": jd.replacement_employee or "",
        "urgent": jd.urgent.lower() in ["yes", "true", "1"] if jd.urgent else False,
        "ctc_rate": jd.ctc_rate or "",
        "customer_reference_id": jd.customer_reference_id or "",
        "billing_loss_status": jd.billing_loss_status or "",
        "aging": float(jd.aging) if jd.aging else 0.0,
        "action_items": jd.action_items or "",

        "parsed": jd.parsed or {},
        "created_at": jd.created_at.isoformat() if jd.created_at else None,
        "skill_count": len((jd.parsed or {}).get("required_skills", [])),
        "is_urgent": jd.urgent.lower() in ["yes", "true", "1"] if jd.urgent else False,
        "days_aging": float(jd.aging) if jd.aging else 0,
    }

    # Human-readable HTML summary for the chat UI (table layout)
    skills_str = ", ".join(jd_data["skills"]) if jd_data["skills"] else "—"
    html = f"""
    <div style="padding:20px;border-radius:12px;background:#0f172a;color:#e5e7eb;font-family:system-ui;max-width:780px;">
      <h3 style="margin-top:0;margin-bottom:16px;font-size:18px;">📄 JD for SID #{jd_data['sid']}</h3>
      <table style="width:100%;border-collapse:collapse;font-size:13px;">
        <tbody>
          <tr>
            <th style="text-align:left;padding:8px;border-bottom:1px solid #1f2937;width:22%;color:#9ca3af;">Title</th>
            <td style="padding:8px;border-bottom:1px solid #1f2937;">{jd_data['title']}</td>
          </tr>
          <tr>
            <th style="text-align:left;padding:8px;border-bottom:1px solid #1f2937;color:#9ca3af;">Account / Project</th>
            <td style="padding:8px;border-bottom:1px solid #1f2937;">{jd_data['account']} / {jd_data['project']}</td>
          </tr>
          <tr>
            <th style="text-align:left;padding:8px;border-bottom:1px solid #1f2937;color:#9ca3af;">Competency</th>
            <td style="padding:8px;border-bottom:1px solid #1f2937;">{jd_data['competency']}</td>
          </tr>
          <tr>
            <th style="text-align:left;padding:8px;border-bottom:1px solid #1f2937;color:#9ca3af;">Location</th>
            <td style="padding:8px;border-bottom:1px solid #1f2937;">{jd_data['base_location_city']} {jd_data['base_location_country']} ({jd_data['location_type']})</td>
          </tr>
          <tr>
            <th style="text-align:left;padding:8px;border-bottom:1px solid #1f2937;color:#9ca3af;">Billability / CTC</th>
            <td style="padding:8px;border-bottom:1px solid #1f2937;">{jd_data['billability']} | {jd_data['ctc_rate']}</td>
          </tr>
          <tr>
            <th style="text-align:left;padding:8px;border-bottom:1px solid #1f2937;color:#9ca3af;">Skills</th>
            <td style="padding:8px;border-bottom:1px solid #1f2937;white-space:pre-wrap;">{skills_str}</td>
          </tr>
          <tr>
            <th style="text-align:left;vertical-align:top;padding:8px;color:#9ca3af;">Description</th>
            <td style="padding:8px;">
              <div style="font-size:13px;white-space:pre-wrap;max-height:260px;overflow-y:auto;border-radius:8px;background:#020617;padding:12px;border:1px solid #1f2937;">
                {jd_data['description']}
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    """

    return jsonify({
        "session_id": session_id or str(uuid.uuid4()),
        "message": html,
        "structured": {
            "type": "jd_detail",
            "data": jd_data
        }
    })

def format_rankings_message(data):
    """Clean ranking results formatter"""
    try:
        jd_title = str(data.get("jd", {}).get("title", "JD"))
        total_cands = data.get("total_candidates", 0)
        rankings = data.get("rankings", [])
        
        html = '<div style="padding:20px;background:#f9fafb;border-radius:12px;">'
        html += f'<h3 style="margin:0 0 15px 0;color:#1e40af;">🤖 Smart Ranked Candidates</h3>'
        html += f'<p><strong>JD:</strong> {jd_title} | <strong>{total_cands} candidates</strong></p>'
        html += '<table style="width:100%;border-collapse:collapse;font-size:14px;margin-top:15px;">'
        html += '<tr style="background:#e2e8f0;"><th>Rank</th><th>Name</th><th>Score</th><th>Details</th></tr>'
        
        for rank in rankings[:10]:
            score = float(rank.get("score", 0))
            color = "#10b981" if score >= 80 else "#f59e0b" if score >= 60 else "#ef4444"
            
            html += f'<tr style="border-bottom:1px solid #e5e7eb;">'
            html += f'<td style="padding:8px;text-align:center;font-weight:bold;">{rank["rank"]}</td>'
            html += f'<td style="padding:8px;">{rank["candidate_name"]}</td>'
            html += f'<td style="padding:8px;text-align:center;font-weight:bold;color:{color};">{score:.1f}</td>'
            html += f'<td style="padding:8px;font-size:12px;">{rank["reasoning"]}</td>'
            html += '</tr>'
        
        html += '</table>'
        html += '</div>'
        return html
        
    except Exception as e:
        print(f"Format error: {e}")
        return f'<div style="padding:20px;color:red;">Error formatting results: {str(e)}</div>'

def format_candidate_rankings_message(data):
    """Format candidate-centric ranking results"""
    try:
        candidate_name = str(data.get("candidate", {}).get("name", "Candidate"))
        total_jds = data.get("total_jds", 0)
        rankings = data.get("rankings", [])
        
        html = '<div style="padding:20px;background:#f0f9ff;border-radius:12px;">'
        html += f'<h3 style="margin:0 0 15px 0;color:#1e40af;">🎯 Best JD Matches for {candidate_name}</h3>'
        html += f'<p><strong>Candidate:</strong> {candidate_name} | <strong>{total_jds} JDs evaluated</strong></p>'
        html += '<table style="width:100%;border-collapse:collapse;font-size:14px;margin-top:15px;">'
        html += '<tr style="background:#e2e8f0;"><th>Rank</th><th>JD SID</th><th>Title</th><th>Score</th><th>Details</th></tr>'
        
        for rank in rankings[:10]:
            score = float(rank.get("score", 0))
            color = "#10b981" if score >= 80 else "#f59e0b" if score >= 60 else "#ef4444"
            
            html += f'<tr style="border-bottom:1px solid #e5e7eb;">'
            html += f'<td style="padding:8px;text-align:center;font-weight:bold;">{rank["rank"]}</td>'
            html += f'<td style="padding:8px;font-weight:bold;">#{rank["jd_sid"]}</td>'
            html += f'<td style="padding:8px;">{rank["jd_title"]}</td>'
            html += f'<td style="padding:8px;text-align:center;font-weight:bold;color:{color};">{score:.1f}</td>'
            html += f'<td style="padding:8px;font-size:12px;">{rank["reasoning"]}</td>'
            html += '</tr>'
        
        html += '</table>'
        html += '</div>'
        return html
        
    except Exception as e:
        print(f"Candidate rank format error: {e}")
        return f'<div style="padding:20px;color:red;">Error formatting results: {str(e)}</div>'

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json() or {}
    user_message = (data.get("message") or "").strip()
    session_id = data.get("session_id")

    if not user_message:
        return jsonify({"error": "Message required"}), 400

    try:
        print(f"📥 CHAT ENDPOINT RECEIVED: message='{user_message}', session={session_id}")

        # 🆕 INTENT CLASSIFICATION + EARLY EXIT (SELF-CONTAINED!)
        intent = simple_intent_check(user_message)
        print(f"🎯 INTENT: {intent}")
        
        # 🚀 BYPASS ORCHESTRATOR FOR HARD COMMANDS
        if intent.get("via_command"):
            if intent["type"] == "ai_rank":
                # Use smart screening instead of mock ranking
                return handle_smart_rank(intent, session_id)

            if intent["type"] == "candidate_rank":
                print("🎯 BYPASSING ORCHESTRATOR → CANDIDATE RANK")
                return handle_candidate_rank(intent, session_id)

            if intent["type"] == "sid_lookup":
                print("📄 BYPASSING ORCHESTRATOR → SID LOOKUP")
                return handle_sid_lookup(intent, session_id)
            
            if intent["type"] == "team_management":
                print("👥 TEAM COMMAND DETECTED")
                return jsonify({
                    "session_id": session_id or str(uuid.uuid4()),
                    "message": "👥 Team management coming soon! Use: TEAM assign John to ProjectX",
                    "structured": {"type": "team", "data": intent}
                })

            # NOTE: EDIT commands must go through the orchestrator so that
            # ChatOrchestrator._handle_edit can generate + apply the patch and commit to DB.
            # Do not early-return a stub response here.

        # NORMAL ORCHESTRATOR FLOW (UNCHANGED)
        orchestrator = ChatOrchestrator()
        response = orchestrator.handle_message(user_message, session_uuid=session_id)

        print(f"🎭 ORCHESTRATOR RETURNED: {type(response)}")
        print(f"🎭 RESPONSE KEYS: {list(response.keys()) if isinstance(response, dict) else 'NOT A DICT'}")

        # ✅ PASS THROUGH: already structured
        if isinstance(response, dict) and "structured" in response:
            print("✅ Response already has 'structured' key - passing through")
            structured = response.get("structured")
            print("✅ structured.type:", structured.get("type") if structured else "MISSING")
            structured = response.get("structured")
            rows = structured.get("rows", []) if structured else []
            print(f"✅ Fixed rows: {len(rows)}")
            print("✅ rows[0]:", rows[:1])
            return jsonify(response)

        # ✅ TRANSFORM: dict but not already structured
        if isinstance(response, dict):
            print("🔄 Transforming response to structured format")
            print(f"   - type: {response.get('type')}")
            print(f"   - data keys: {list((response.get('data') or {}).keys())}")

            structured_response = {
                "session_id": response.get("session_id") or session_id,
                "message": response.get("message", "I couldn't process that query."),
                "structured": {
                    "type": response.get("type", "text"),
                    "data": response.get("data") or {},
                },
            }
            return jsonify(structured_response)

        print("⚠️ Response format unexpected, returning as-is")
        return jsonify(response)

    except Exception as e:
        print(f"❌ Chat endpoint error: {str(e)}")
        import traceback
        traceback.print_exc()

        return jsonify({
            "session_id": session_id or str(uuid.uuid4()),
            "message": "Sorry, I encountered an error. Please try again!",
            "structured": {"type": "error", "data": {"error": str(e)}},
        }), 500

@app.route('/health')
def health():
    return {"status": "healthy", "chat_ready": True}

def find_existing_candidate(new_candidate: Candidate) -> Candidate | None:
    """
    Find if candidate already exists in database.
    Checks by: 1) Email (primary), 2) Name (secondary)
    SQLite-compatible version using Python-side filtering
    """
    parsed = new_candidate.parsed or {}
    email = (parsed.get("email") or new_candidate.email or "").strip().lower()
    name = (parsed.get("candidate_name") or new_candidate.full_name or "").strip().lower()
    
    if not email and not name:
        return None
    
    # Get all candidates except the new one
    all_candidates = Candidate.query.filter(Candidate.id != new_candidate.id).all()
    
    for candidate in all_candidates:
        candidate_parsed = candidate.parsed or {}
        
        # Strategy 1: Match by email (most reliable)
        if email:
            candidate_email = (
                candidate_parsed.get("email") or 
                candidate.email or 
                ""
            ).strip().lower()
            
            if candidate_email and candidate_email == email:
                print(f"   ✅ Found by email: {email}")
                return candidate
        
        # Strategy 2: Match by exact name (fallback)
        if name:
            candidate_name = (
                candidate_parsed.get("candidate_name") or 
                candidate.full_name or 
                ""
            ).strip().lower()
            
            if candidate_name and candidate_name == name:
                print(f"   ✅ Found by name: {name}")
                return candidate
    
    return None

def merge_candidates(existing: Candidate, new: Candidate) -> Candidate:
    """
    Merge new candidate data into existing candidate.
    Strategy: Keep existing as base, add/update with new information.
    """
    existing_parsed = existing.parsed or {}
    new_parsed = new.parsed or {}
    
    print(f"\n📝 Merging candidate ")
    print(f"   Existing: {len(existing_parsed.get('projects', []))} projects, {existing.total_experience_years} years exp")
    print(f"   New:      {len(new_parsed.get('projects', []))} projects, {new.total_experience_years} years exp")
    
    # 1. Update contact info if new has more details
    if new_parsed.get("email") and not existing_parsed.get("email"):
        existing_parsed["email"] = new_parsed["email"]
        existing.email = new_parsed["email"]
        print(f"   ✅ Updated email")
    
    if new_parsed.get("phone") and not existing_parsed.get("phone"):
        existing_parsed["phone"] = new_parsed["phone"]
        existing.phone = new_parsed["phone"]
        print(f"   ✅ Updated phone")
    
    if new_parsed.get("linkedin") and not existing_parsed.get("linkedin"):
        existing_parsed["linkedin"] = new_parsed["linkedin"]
        print(f"   ✅ Updated LinkedIn")
    
    # 2. Update experience summary if new is longer/better
    new_summary = new_parsed.get("experience_summary") or new_parsed.get("professional_summary")
    existing_summary = existing_parsed.get("experience_summary") or existing_parsed.get("professional_summary")
    
    if new_summary and (not existing_summary or len(new_summary) > len(existing_summary)):
        existing_parsed["experience_summary"] = new_summary
        print(f"   ✅ Updated experience summary")
    
    # 3. Merge skills (union of both)
    existing_skills = set(existing_parsed.get("technical_skills") or existing_parsed.get("skills") or [])
    new_skills = set(new_parsed.get("technical_skills") or new_parsed.get("skills") or [])
    merged_skills = list(existing_skills | new_skills)
    
    if len(merged_skills) > len(existing_skills):
        existing_parsed["technical_skills"] = merged_skills
        print(f"   ✅ Merged skills: {len(existing_skills)} → {len(merged_skills)}")
    
    # 4. Merge primary skills
    existing_primary = set(existing_parsed.get("primary_skills") or [])
    new_primary = set(new_parsed.get("primary_skills") or [])
    merged_primary = list(existing_primary | new_primary)
    
    if len(merged_primary) > len(existing_primary):
        existing_parsed["primary_skills"] = merged_primary
        print(f"   ✅ Merged primary skills: {len(existing_primary)} → {len(merged_primary)}")
    
    # 5. Merge projects (add new ones that don't exist)
    existing_projects = existing_parsed.get("projects") or []
    new_projects = new_parsed.get("projects") or []
    
    # Create lookup of existing project names
    existing_project_names = {
        (proj.get("name") or "").lower().strip() 
        for proj in existing_projects if proj
    }
    
    added_projects = 0
    for new_proj in new_projects:
        if not new_proj:
            continue
        
        new_proj_name = (new_proj.get("name") or "").lower().strip()
        
        # If project doesn't exist, add it
        if new_proj_name not in existing_project_names:
            existing_projects.append(new_proj)
            added_projects += 1
            print(f"   ✅ Added new project: '{new_proj.get('name')}'")
        else:
            # Project exists - check if new version has more details
            for idx, existing_proj in enumerate(existing_projects):
                if (existing_proj.get("name") or "").lower().strip() == new_proj_name:
                    # Update if new has more responsibilities or tools
                    existing_resp_count = len(existing_proj.get("responsibilities") or [])
                    new_resp_count = len(new_proj.get("responsibilities") or [])
                    
                    if new_resp_count > existing_resp_count:
                        existing_projects[idx] = new_proj
                        print(f"   ✅ Updated project '{new_proj.get('name')}' with more details")
                    break
    
    existing_parsed["projects"] = existing_projects
    
    if added_projects > 0:
        print(f"   ✅ Added {added_projects} new project(s)")
    
    # 6. Merge work experiences
    existing_jobs = existing_parsed.get("work_experiences") or []
    new_jobs = new_parsed.get("work_experiences") or []
    
    existing_job_keys = {
        (job.get("company_name") or "", job.get("job_title") or "")
        for job in existing_jobs if job
    }
    
    added_jobs = 0
    for new_job in new_jobs:
        if not new_job:
            continue
        
        job_key = (new_job.get("company_name") or "", new_job.get("job_title") or "")
        if job_key not in existing_job_keys and job_key != ("", ""):
            existing_jobs.append(new_job)
            added_jobs += 1
    
    if added_jobs > 0:
        existing_parsed["work_experiences"] = existing_jobs
        print(f"   ✅ Added {added_jobs} new job(s)")
    
    # 7. Merge certifications
    existing_certs = existing_parsed.get("certifications") or []
    new_certs = new_parsed.get("certifications") or []
    
    existing_cert_names = {
        (cert.get("name") or "").lower() 
        for cert in existing_certs if cert
    }
    
    added_certs = 0
    for new_cert in new_certs:
        if not new_cert:
            continue
        
        cert_name = (new_cert.get("name") or "").lower()
        if cert_name and cert_name not in existing_cert_names:
            existing_certs.append(new_cert)
            added_certs += 1
    
    if added_certs > 0:
        existing_parsed["certifications"] = existing_certs
        print(f"   ✅ Added {added_certs} new certification(s)")
    
    # 8. Update experience years if new is higher
    if new.total_experience_years and new.total_experience_years > (existing.total_experience_years or 0):
        existing.total_experience_years = new.total_experience_years
        existing_parsed["total_experience_years"] = new.total_experience_years
        print(f"   ✅ Updated experience: {existing.total_experience_years} years")
    
    # 9. Update primary role if new is more specific
    if new.primary_role and not existing.primary_role:
        existing.primary_role = new.primary_role
        existing_parsed["primary_role"] = new.primary_role
        print(f"   ✅ Updated role: {new.primary_role}")
    
    # Save merged data
    existing.parsed = existing_parsed
    flag_modified(existing, "parsed")
    db.session.add(existing)
    db.session.commit()
    
    print(f"   💾 Merge complete!")
    print(f"   Final: {len(existing_parsed.get('projects', []))} projects, {existing.total_experience_years} years exp\n")
    
    return existing

@app.route("/api/upload-resumes", methods=["POST"])
def upload_resumes():
    """Upload resumes with candidate deduplication and automatic merging"""
    files = request.files.getlist("resumes")
    if not files:
        return jsonify({"error": "No files"}), 400
    
    results = []
    
    for file in files:
        try:
            fresh_pipeline = RAGResumePipeline()
            candidate_id = str(uuid.uuid4())
            
            result = fresh_pipeline.process_resume(
                file_obj=file,
                candidate_id=candidate_id
            )
            
            if result["success"]:
                # Get the newly parsed candidate
                new_candidate = db.session.get(Candidate, result["candidate_id"])
                
                if new_candidate:
                    # ✅ CHECK FOR DUPLICATE CANDIDATE
                    existing_candidate = find_existing_candidate(new_candidate)
                    
                    if existing_candidate:
                        print(f"\n🔍 DUPLICATE DETECTED: Found existing candidate '{existing_candidate.full_name}' (ID: {existing_candidate.id})")
                        print(f"   Merging with new data from upload...")
                        
                        # Merge the candidates
                        merged_candidate = merge_candidates(existing_candidate, new_candidate)
                        
                        # Delete the temporary new candidate
                        db.session.delete(new_candidate)
                        db.session.commit()
                        
                        # Use the existing candidate for project processing
                        candidate = merged_candidate
                        
                        results.append({
                            "success": True,
                            "candidate_id": candidate.id,
                            "full_name": candidate.full_name,
                            "status": "merged",
                            "message": f"Updated existing candidate with new information",
                            "projects_count": len(candidate.parsed.get("projects", [])),
                            "experience_years": candidate.total_experience_years
                        })
                    else:
                        candidate = new_candidate
                        results.append({
                            "success": True,
                            "candidate_id": candidate.id,
                            "full_name": candidate.full_name,
                            "status": "new",
                            "projects_count": len(result["parsed_data"].get("projects", [])),
                            "experience_years": result["parsed_data"].get("total_experience_years", 0)
                        })
                    
                    # Process projects (works for both new and merged)
                    try:
                        if candidate.parsed and candidate.parsed.get("projects"):
                            print(f"📂 Processing projects for {candidate.full_name}")
                            process_and_save_projects(candidate)
                        
                        # Run old deduplication for backward compatibility
                        deduplicate_candidate_projects(candidate)
                        print(f"✅ Deduplication complete for {candidate.full_name}")
                        
                    except Exception as dedup_error:
                        print(f"⚠️ Project processing failed (non-critical): {dedup_error}")
                        import traceback
                        traceback.print_exc()
            else:
                results.append({"success": False, "error": result["error"]})
                
        except Exception as e:
            print(f"Failed {file.filename}: {e}")
            import traceback
            traceback.print_exc()
            results.append({"success": False, "filename": file.filename, "error": str(e)})
    
    return jsonify({
        "successful": sum(1 for r in results if r.get("success")),
        "failed": len(results) - sum(1 for r in results if r.get("success")),
        "results": results
    }), 200

def deduplicate_candidate_projects(candidate: Candidate):
    """
    Match this candidate's projects with existing projects in database.
    Merge team members if project already exists.
    """
    parsed = candidate.parsed or {}
    new_projects = parsed.get("projects", [])

    if not new_projects:
        return

    # Get all existing candidates and their projects
    all_candidates = Candidate.query.filter(Candidate.id != candidate.id).all()
    existing_projects = []

    for other_cand in all_candidates:
        other_parsed = other_cand.parsed or {}
        other_projects = other_parsed.get("projects", [])

        for proj in other_projects:
            if proj.get("name"):
                existing_projects.append({
                    "project": proj,
                    "candidate": other_cand
                })

    # Match each new project
    updated = False

    for new_proj in new_projects:
        # Try to find matching project
        best_match = None
        best_score = 0.0

        for existing in existing_projects:
            score = calculate_project_similarity(new_proj, existing["project"])

            if score > best_score and score >= 0.70:  # 70% threshold
                best_score = score
                best_match = existing

        if best_match:
            # âœ… Found matching project!
            matched_proj = best_match["project"]
            matched_cand = best_match["candidate"]

            print(f"âœ… MATCH: '{new_proj.get('name')}' matches '{matched_proj.get('name')}' ({best_score:.1%})")

            # Add current candidate to the matched project's team
            matched_proj.setdefault("team_members", [])

            if candidate.id not in [m.get("id") for m in matched_proj["team_members"]]:
                matched_proj["team_members"].append({
                    "id": candidate.id,
                    "name": candidate.full_name or "Unknown",
                    "role": new_proj.get("role") or candidate.primary_role,
                    "years": float(candidate.total_experience_years or 0.0),
                })

                # Save the updated matched candidate
                flag_modified(matched_cand, "parsed")
                db.session.add(matched_cand)
                print(f"   Added {candidate.full_name} to team in {matched_cand.full_name}'s record")

            # Also add matched candidate to THIS project's team
            new_proj.setdefault("team_members", [])

            if matched_cand.id not in [m.get("id") for m in new_proj["team_members"]]:
                new_proj["team_members"].append({
                    "id": matched_cand.id,
                    "name": matched_cand.full_name or "Unknown",
                    "role": matched_proj.get("role") or matched_cand.primary_role,
                    "years": float(matched_cand.total_experience_years or 0.0),
                })
                updated = True
                print(f"   Added {matched_cand.full_name} to team in {candidate.full_name}'s record")

            # Merge technologies
            existing_techs = set(matched_proj.get("technologies_used", []))
            new_techs = set(new_proj.get("technologies_used", []))
            merged_techs = list(existing_techs | new_techs)

            if merged_techs:
                new_proj["technologies_used"] = merged_techs
                matched_proj["technologies_used"] = merged_techs
                updated = True

            # Use better description if available
            if new_proj.get("description") and len(new_proj["description"]) > len(matched_proj.get("description", "")):
                matched_proj["description"] = new_proj["description"]
                flag_modified(matched_cand, "parsed")
                db.session.add(matched_cand)

        else:
            # âœ… New unique project
            print(f"ðŸ†• NEW PROJECT: '{new_proj.get('name')}'")

            # Initialize team_members with just this candidate
            new_proj.setdefault("team_members", [])
            if candidate.id not in [m.get("id") for m in new_proj["team_members"]]:
                new_proj["team_members"].append({
                    "id": candidate.id,
                    "name": candidate.full_name or "Unknown",
                    "role": new_proj.get("role") or candidate.primary_role,
                    "years": float(candidate.total_experience_years or 0.0),
                })
                updated = True

    if updated:
        candidate.parsed = parsed
        flag_modified(candidate, "parsed")
        db.session.add(candidate)
        db.session.commit()
        print(f"ðŸ’¾ Saved deduplication for {candidate.full_name}")

@app.route("/api/jd", methods=["POST"])
def save_jd():
    data = request.get_json() or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "JD text required"}), 400
    CURRENT_JD["text"] = text
    return jsonify({"success": True})

@app.route("/api/candidates", methods=["GET"])
def list_candidates():
    rows = Candidate.query.order_by(Candidate.created_at.desc()).limit(200).all()

    def to_dict(c):
        parsed = c.parsed or {}
        sections = parsed.get("sections") or {}

        primary_role = c.primary_role
        roles = (
            parsed.get("roles")
            or parsed.get("work_experiences")
            or parsed.get("experience")
            or sections.get("experience")
            or []
        )
        if roles:
            primary_role = roles[0].get("job_title") or roles[0].get("title") or primary_role

        return {
            "id": c.id,
            "full_name": c.full_name,
            "email": c.email,
            "phone": c.phone,
            "total_experience_years": c.total_experience_years,
            "primary_role": primary_role,
            "primary_domain": c.primary_domain,
            "parsed": parsed,
            "role_bucket": c.role_bucket, 
            "on_bench": c.on_bench,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }

    return jsonify({"candidates": [to_dict(c) for c in rows]}), 200


def _dedupe_sorted_strings(values):
    seen = set()
    out = []
    for v in values or []:
        s = str(v or '').strip()
        if not s:
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    out.sort(key=lambda x: x.lower())
    return out


@app.route("/api/filter-options/projects", methods=["GET"])
def filter_options_projects():
    try:
        from models import ProjectDB
        rows = db.session.query(ProjectDB.name).filter(ProjectDB.name.isnot(None)).distinct().all()
        names = [r[0] for r in rows if r and r[0]]
        return jsonify(_dedupe_sorted_strings(names)), 200
    except Exception:
        # Fallback: extract from Candidate.projects JSON
        rows = Candidate.query.with_entities(Candidate.projects).all()
        names = []
        for (projects,) in rows:
            if not projects or not isinstance(projects, list):
                continue
            for p in projects:
                if isinstance(p, dict):
                    names.append(p.get('name') or '')
                elif isinstance(p, str):
                    names.append(p)
        return jsonify(_dedupe_sorted_strings(names)), 200


@app.route("/api/filter-options/skills", methods=["GET"])
def filter_options_skills():
    rows = Candidate.query.with_entities(Candidate.skills, Candidate.parsed).all()
    skills = []
    for cand_skills, parsed in rows:
        if isinstance(cand_skills, list):
            skills.extend([s for s in cand_skills if s])
        if isinstance(parsed, dict):
            ts = parsed.get('technical_skills') or parsed.get('skills') or []
            if isinstance(ts, list):
                skills.extend([s for s in ts if s])
            elif isinstance(ts, str):
                skills.extend([x.strip() for x in ts.split(',') if x.strip()])

            # Also include skills from project tech stacks
            projs = parsed.get('projects') or []
            if isinstance(projs, list):
                for p in projs:
                    if not isinstance(p, dict):
                        continue
                    arr = (
                        p.get('technical_tools')
                        or p.get('technologies_used')
                        or p.get('tools')
                        or p.get('skills')
                        or []
                    )
                    if isinstance(arr, list):
                        skills.extend([x for x in arr if x])
                    elif isinstance(arr, str):
                        skills.extend([x.strip() for x in arr.split(',') if x.strip()])
    return jsonify(_dedupe_sorted_strings(skills)), 200


@app.route("/api/filter-options/certifications", methods=["GET"])
def filter_options_certifications():
    rows = Candidate.query.with_entities(Candidate.certifications, Candidate.parsed).all()
    certs = []
    for cand_certs, parsed in rows:
        if isinstance(cand_certs, list):
            for c in cand_certs:
                if not c:
                    continue
                if isinstance(c, dict):
                    certs.append(c.get('name') or c.get('title') or '')
                else:
                    certs.append(c)
        if isinstance(parsed, dict):
            pc = parsed.get('certifications') or []
            if isinstance(pc, list):
                for c in pc:
                    if not c:
                        continue
                    if isinstance(c, dict):
                        certs.append(c.get('name') or c.get('title') or '')
                    else:
                        certs.append(c)
            elif isinstance(pc, str):
                certs.extend([x.strip() for x in pc.split(',') if x.strip()])
    return jsonify(_dedupe_sorted_strings(certs)), 200


@app.route("/api/filter-options/buckets", methods=["GET"])
def filter_options_buckets():
    rows = Candidate.query.with_entities(Candidate.role_bucket).filter(Candidate.role_bucket.isnot(None)).distinct().all()
    buckets = [r[0] for r in rows if r and r[0]]
    return jsonify(_dedupe_sorted_strings(buckets)), 200


@app.route("/api/filter-options/roles", methods=["GET"])
def filter_options_roles():
    rows = Candidate.query.with_entities(Candidate.primary_role).filter(Candidate.primary_role.isnot(None)).distinct().all()
    roles = [r[0] for r in rows if r and r[0]]
    return jsonify(_dedupe_sorted_strings(roles)), 200


@app.route("/api/candidates/filter", methods=["POST"])
def candidates_filter_structured():
    data = request.get_json() or {}
    try:
        from services.candidate_filters import run_structured_candidate_filter
        out = run_structured_candidate_filter(data)
        return jsonify(out), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 400


@app.route("/api/candidates/<int:cand_id>", methods=["DELETE", "OPTIONS"])
@cross_origin()
def delete_candidate(cand_id):
    if request.method == "OPTIONS":
        return "", 200

    try:
        from models import CandidateProject, ProjectDB

        cand = db.session.get(Candidate, cand_id)
        if not cand:
            return jsonify({"ok": False, "error": "Candidate not found"}), 404

        # Track affected projects before deletion so we can recompute contributor counts.
        # IMPORTANT: do NOT load CandidateProject ORM objects into the session here, otherwise
        # SQLAlchemy may try to set candidate_id=NULL during parent delete (NOT NULL constraint).
        affected_project_ids = []
        try:
            from sqlalchemy import select

            affected_project_ids = list(
                db.session.execute(
                    select(CandidateProject.project_id).where(CandidateProject.candidate_id == cand_id)
                ).scalars()
            )
        except Exception:
            affected_project_ids = []

        # Best-effort: delete from vector DB
        try:
            pipeline.vector_db.delete_candidate(cand_id)
        except Exception as ve:
            print(f"Warning: failed to delete candidate {cand_id} from vector DB: {ve}")

        # Best-effort: delete stored resume file if present
        try:
            pdf_path = getattr(cand, "pdf_path", None)
            if pdf_path:
                import os
                if os.path.exists(pdf_path):
                    os.remove(pdf_path)
        except Exception as fe:
            print(f"Warning: failed to delete resume file for candidate {cand_id}: {fe}")

        # IMPORTANT: Explicitly delete CandidateProject links via a Core DELETE and flush.
        # This avoids SQLAlchemy issuing UPDATE candidate_project SET candidate_id=NULL.
        try:
            from sqlalchemy import delete

            db.session.execute(delete(CandidateProject).where(CandidateProject.candidate_id == cand_id))
            db.session.flush()
        except Exception as ce:
            print(f"Warning: failed to delete candidate_project links for candidate {cand_id}: {ce}")

        # Delete candidate
        db.session.delete(cand)
        db.session.commit()

        # Recompute contributor counts for affected projects
        try:
            for pid in set(affected_project_ids):
                proj = db.session.get(ProjectDB, pid)
                if not proj:
                    continue
                proj.total_contributors = CandidateProject.query.filter_by(project_id=pid).count()
            db.session.commit()
        except Exception as pe:
            db.session.rollback()
            print(f"Warning: failed to update project contributor counts after deleting candidate {cand_id}: {pe}")

        return jsonify({"ok": True, "deleted_candidate_id": cand_id}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/projects-db", methods=["GET"])
def debug_projects_db():
    """Debug endpoint to see what's in the database tables."""
    projects = ProjectDB.query.all()
    
    result = []
    for project in projects:
        contributions = CandidateProject.query.filter_by(project_id=project.id).all()
        
        members = []
        for contrib in contributions:
            members.append({
                "candidate_id": contrib.candidate_id,
                "candidate_name": contrib.candidate.full_name,
                "role": contrib.role,
            })
        
        result.append({
            "project_id": project.id,
            "project_name": project.name,
            "total_contributors": project.total_contributors,
            "members_in_db": members,
            "member_count": len(members),
        })
    
    return jsonify(result), 200

@app.route("/api/projects", methods=["GET"])
def list_projects():
    """Fetch all projects from database with their team members."""

    from models import ProjectDB, CandidateProject, ProjectMergeHistory
    
    def slugify(name: str) -> str:
        import re
        s = name.strip().lower()
        s = re.sub(r"[^\w\s-]", "", s)
        s = re.sub(r"\s+", "-", s)
        return s[:80]

    def is_ongoing_project(project: ProjectDB) -> bool:
        """Determine if project is ongoing based on end_date."""
        if not project.end_date:
            # Has start date but no end date → ongoing
            if project.start_date:
                return True
            # No dates at all → archived
            return False
        
        end_date = project.end_date.lower()
        
        # Explicit ongoing indicators
        if any(word in end_date for word in ["present", "current", "now", "ongoing"]):
            return True
        
        # Has explicit end date → archived
        return False

    # Fetch all projects from database (exclude merged children)
    all_projects = ProjectDB.query.filter(ProjectDB.merged_into_id.is_(None)).all()

    active_histories = ProjectMergeHistory.query.filter(ProjectMergeHistory.reversed_at.is_(None)).all()
    merge_history_by_child = {h.source_project_id: h.id for h in active_histories}
    
    ongoing = []
    archived = []

    for project in all_projects:
        # Get all team members for this project
        contributions = CandidateProject.query.filter_by(project_id=project.id).all()
        
        members = []
        for contrib in contributions:
            candidate = contrib.candidate
            members.append({
                "id": candidate.id,
                "name": candidate.full_name or "Unknown",
                "role": contrib.role or candidate.primary_role,
                "years": float(candidate.total_experience_years or 0.0),
                "contribution": contrib.contribution,
                "technical_tools": contrib.technical_tools or [],
            })
        
        # Sort members by experience
        members = sorted(
            members,
            key=lambda m: (m["years"], (m["role"] or "").lower()),
            reverse=True,
        )

        project_data = {
            "id": slugify(project.name),
            "db_id": project.id,  # Real database ID
            "name": project.name,
            "organization": project.organization,
            "start_date": project.start_date,
            "end_date": project.end_date,
            "duration_months": project.duration_months,
            "summary": project.summary,
            "technologies": sorted(project.all_technologies or []),
            "members": members,
            "team_size": len(members),
            "is_academic": project.is_academic,
            "merged_children": [
                {
                    "db_id": child.id,
                    "name": child.name,
                    "merge_history_id": merge_history_by_child.get(child.id),
                }
                for child in ProjectDB.query.filter(ProjectDB.merged_into_id == project.id).all()
            ],
        }

        # Categorize as ongoing or archived
        if is_ongoing_project(project):
            ongoing.append(project_data)
        else:
            archived.append(project_data)

    # Sort by name
    ongoing.sort(key=lambda p: p["name"].lower())
    archived.sort(key=lambda p: p["name"].lower())

    return jsonify({
        "projects": ongoing,
        "archived_projects": archived,
        "total_projects": len(ongoing) + len(archived),
    }), 200


def _cp_snapshot(cp):
    return {
        "id": cp.id,
        "candidate_id": cp.candidate_id,
        "project_id": cp.project_id,
        "role": cp.role,
        "description": cp.description,
        "responsibilities": cp.responsibilities or [],
        "technical_tools": cp.technical_tools or [],
        "contribution": cp.contribution,
        "impact": cp.impact,
        "candidate_start_date": cp.candidate_start_date,
        "candidate_end_date": cp.candidate_end_date,
        "candidate_duration_months": cp.candidate_duration_months,
    }


def _project_snapshot(p):
    return {
        "name": p.name,
        "organization": p.organization,
        "start_date": p.start_date,
        "end_date": p.end_date,
        "duration_months": p.duration_months,
        "is_academic": p.is_academic,
        "summary": p.summary,
        "all_technologies": p.all_technologies or [],
        "team_size_estimate": p.team_size_estimate,
        "impact_metrics": p.impact_metrics or [],
        "total_contributors": p.total_contributors,
    }


def _merge_lists(a, b):
    a = list(a or [])
    b = list(b or [])
    seen = set()
    out = []
    for v in a + b:
        if v is None:
            continue
        key = str(v).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(v)
    return out


def _groq_json(prompt: str) -> Dict[str, Any]:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY missing")
    client = Groq(api_key=GROQ_API_KEY)
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    content = (resp.choices[0].message.content or "").strip()
    return json.loads(content) if content else {}


def _recompute_project_contributors(project_id: int):
    from models import CandidateProject, ProjectDB
    from sqlalchemy import func

    proj = db.session.get(ProjectDB, int(project_id))
    if not proj:
        return
    proj.total_contributors = (
        db.session.query(func.count(func.distinct(CandidateProject.candidate_id)))
        .filter(CandidateProject.project_id == proj.id)
        .scalar()
    ) or 0
    db.session.add(proj)


@app.route("/api/projects/merge/suggest", methods=["POST"])
def suggest_project_merges():
    from models import ProjectDB

    data = request.get_json() or {}
    threshold = float(data.get("threshold") or 0.82)
    limit = int(data.get("limit") or 10)

    projects = ProjectDB.query.filter(ProjectDB.merged_into_id.is_(None)).limit(500).all()
    items = [
        {
            "id": p.id,
            "name": p.name,
            "organization": p.organization,
            "summary": p.summary,
            "technologies": p.all_technologies or [],
        }
        for p in projects
    ]

    scored = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            s = calculate_project_similarity(items[i], items[j])
            if s >= threshold:
                scored.append((s, items[i], items[j]))

    scored.sort(key=lambda x: x[0], reverse=True)

    suggestions = []
    for score, a, b in scored[: max(limit * 2, 20)]:
        prompt = f"""
You are helping deduplicate projects in an internal candidate database.
Decide if Project A and Project B represent the SAME real-world project.

Return ONLY JSON with keys:
- same_project: boolean
- confidence: number (0-1)
- reason: string
- recommended_target_id: integer (choose canonical project id)
- recommended_source_id: integer (id to merge into target)

Project A (id={a['id']}):
name: {a.get('name')}
organization: {a.get('organization')}
summary: {a.get('summary')}
technologies: {a.get('technologies')}

Project B (id={b['id']}):
name: {b.get('name')}
organization: {b.get('organization')}
summary: {b.get('summary')}
technologies: {b.get('technologies')}
"""
        try:
            out = _groq_json(prompt)
        except Exception as e:
            return jsonify({"error": f"LLM error: {e}"}), 500

        if out.get("same_project") is True:
            suggestions.append({
                "score": float(score),
                "confidence": float(out.get("confidence") or 0),
                "reason": out.get("reason") or "",
                "recommended_target_id": out.get("recommended_target_id"),
                "recommended_source_id": out.get("recommended_source_id"),
            })

        if len(suggestions) >= limit:
            break

    return jsonify({"suggestions": suggestions}), 200


@app.route("/api/projects/merge", methods=["POST"])
def merge_projects():
    from models import ProjectDB, CandidateProject, ProjectMergeHistory

    data = request.get_json() or {}
    source_id = data.get("source_project_id")
    target_id = data.get("target_project_id")

    if source_id is None or target_id is None:
        return jsonify({"error": "source_project_id and target_project_id required"}), 400

    source_id = int(source_id)
    target_id = int(target_id)
    if source_id == target_id:
        return jsonify({"error": "source_project_id and target_project_id must be different"}), 400

    source = db.session.get(ProjectDB, source_id)
    target = db.session.get(ProjectDB, target_id)
    if not source or not target:
        return jsonify({"error": "Project not found"}), 404
    if source.merged_into_id is not None:
        return jsonify({"error": "Source project is already merged"}), 400

    prompt = f"""
You are merging two projects in an internal candidate database.
You MUST ensure they represent the SAME real-world project.
Return ONLY JSON with keys:
- should_merge: boolean
- confidence: number (0-1)
- reason: string

Project SOURCE (id={source.id}):
name: {source.name}
organization: {source.organization}
summary: {source.summary}
technologies: {source.all_technologies or []}

Project TARGET (id={target.id}):
name: {target.name}
organization: {target.organization}
summary: {target.summary}
technologies: {target.all_technologies or []}
"""

    try:
        out = _groq_json(prompt)
    except Exception as e:
        return jsonify({"error": f"LLM error: {e}"}), 500

    if out.get("should_merge") is not True:
        return jsonify({"error": "LLM refused merge", "details": out}), 400

    source_before = _project_snapshot(source)
    target_before = _project_snapshot(target)
    moved = []

    source_links = CandidateProject.query.filter_by(project_id=source.id).all()
    for link in source_links:
        existing = CandidateProject.query.filter_by(
            candidate_id=link.candidate_id,
            project_id=target.id,
        ).first()

        if existing:
            target_link_before = _cp_snapshot(existing)
            source_link_snapshot = _cp_snapshot(link)

            if not existing.role and link.role:
                existing.role = link.role
            if not existing.description and link.description:
                existing.description = link.description
            existing.responsibilities = _merge_lists(existing.responsibilities, link.responsibilities)
            existing.technical_tools = _merge_lists(existing.technical_tools, link.technical_tools)
            if not existing.contribution and link.contribution:
                existing.contribution = link.contribution
            if not existing.impact and link.impact:
                existing.impact = link.impact
            if not existing.candidate_start_date and link.candidate_start_date:
                existing.candidate_start_date = link.candidate_start_date
            if not existing.candidate_end_date and link.candidate_end_date:
                existing.candidate_end_date = link.candidate_end_date
            if not existing.candidate_duration_months and link.candidate_duration_months:
                existing.candidate_duration_months = link.candidate_duration_months

            moved.append({
                "action": "merged_into_existing",
                "source_link_snapshot": source_link_snapshot,
                "target_link_id": existing.id,
                "target_link_before": target_link_before,
            })
            db.session.delete(link)
        else:
            before = _cp_snapshot(link)
            link.project_id = target.id
            moved.append({
                "action": "repoint",
                "link_id": link.id,
                "before": before,
            })

    target.all_technologies = _merge_lists(target.all_technologies, source.all_technologies)
    if (not target.summary) and source.summary:
        target.summary = source.summary

    source.merged_into_id = target.id
    source.merged_at = datetime.utcnow()

    hist = ProjectMergeHistory(
        source_project_id=source.id,
        target_project_id=target.id,
        source_project_before=source_before,
        target_project_before=target_before,
        moved_links=moved,
        llm_reason=out.get("reason") or "",
    )
    db.session.add(hist)

    _recompute_project_contributors(source.id)
    _recompute_project_contributors(target.id)
    db.session.commit()

    return jsonify({
        "success": True,
        "merge_history_id": hist.id,
        "llm": out,
    }), 200


@app.route("/api/projects/unmerge", methods=["POST"])
def unmerge_projects():
    from models import ProjectDB, CandidateProject, ProjectMergeHistory

    data = request.get_json() or {}
    merge_history_id = data.get("merge_history_id")
    if merge_history_id is None:
        return jsonify({"error": "merge_history_id required"}), 400

    hist = db.session.get(ProjectMergeHistory, int(merge_history_id))
    if not hist:
        return jsonify({"error": "Merge history not found"}), 404
    if hist.reversed_at is not None:
        return jsonify({"error": "Merge history already reversed"}), 400

    source = db.session.get(ProjectDB, int(hist.source_project_id))
    target = db.session.get(ProjectDB, int(hist.target_project_id))
    if not source or not target:
        return jsonify({"error": "Project not found"}), 404

    # Restore project fields
    src_before = hist.source_project_before or {}
    tgt_before = hist.target_project_before or {}

    for k, v in src_before.items():
        if hasattr(source, k):
            setattr(source, k, v)
    for k, v in tgt_before.items():
        if hasattr(target, k):
            setattr(target, k, v)

    source.merged_into_id = None
    source.merged_at = None

    moved_links = hist.moved_links or []
    for entry in moved_links:
        action = entry.get("action")
        if action == "repoint":
            link_id = entry.get("link_id")
            cp = db.session.get(CandidateProject, int(link_id)) if link_id else None
            if cp:
                cp.project_id = source.id
        elif action == "merged_into_existing":
            target_link_id = entry.get("target_link_id")
            target_before = entry.get("target_link_before") or {}
            src_snap = entry.get("source_link_snapshot") or {}

            # Restore target link fields
            existing = db.session.get(CandidateProject, int(target_link_id)) if target_link_id else None
            if existing:
                for k, v in target_before.items():
                    if k in {"id", "candidate_id", "project_id"}:
                        continue
                    if hasattr(existing, k):
                        setattr(existing, k, v)

            # Recreate source link
            cand_id = src_snap.get("candidate_id")
            if cand_id is not None:
                dup = CandidateProject.query.filter_by(candidate_id=int(cand_id), project_id=source.id).first()
                if not dup:
                    recreated = CandidateProject(
                        candidate_id=int(cand_id),
                        project_id=source.id,
                        role=src_snap.get("role"),
                        description=src_snap.get("description"),
                        responsibilities=src_snap.get("responsibilities") or [],
                        technical_tools=src_snap.get("technical_tools") or [],
                        contribution=src_snap.get("contribution"),
                        impact=src_snap.get("impact"),
                        candidate_start_date=src_snap.get("candidate_start_date"),
                        candidate_end_date=src_snap.get("candidate_end_date"),
                        candidate_duration_months=src_snap.get("candidate_duration_months"),
                    )
                    db.session.add(recreated)

    hist.reversed_at = datetime.utcnow()
    db.session.add(hist)

    _recompute_project_contributors(source.id)
    _recompute_project_contributors(target.id)
    db.session.commit()

    return jsonify({"success": True}), 200

@app.route("/api/reset-candidates", methods=["POST"])
def reset_candidates():
    try:
        num_rows = db.session.query(Candidate).delete()
        db.session.commit()
        print(f"Deleted {num_rows} candidates from SQL")

        try:
            pipeline.vector_db.clear_all()
            print("Cleared vector DB collection")
        except Exception as ve:
            print(f"Warning: failed to clear vector DB: {ve}")

        return jsonify({"ok": True, "deleted": num_rows}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/normalize-resumes", methods=["POST"])
def normalize_resumes():
    fresh_pipeline = RAGResumePipeline()
    rows = Candidate.query.all()
    results = {"updated": 0, "errors": 0}

    for c in rows:
        try:
            normalized = fresh_pipeline.dolphin_normalize_resume(c.raw_text or "")
            parsed = fresh_pipeline.dolphin_parse_resume(normalized)
            if parsed != c.parsed:
                c.parsed = parsed
                results["updated"] += 1
        except:
            results["errors"] += 1

    db.session.commit()
    return jsonify({"message": f"âœ… Updated {results['updated']}/{len(rows)} resumes"}), 200

@app.route("/api/candidate-buckets", methods=["GET"])
def candidate_buckets():
    rows = Candidate.query.order_by(Candidate.created_at.desc()).all()
    data = []
    for c in rows:
        parsed = c.parsed or {}
        bucket = classify_candidate_bucket(parsed, c.primary_role)
        data.append({
            "id": c.id,
            "name": c.full_name,
            "primary_role": c.primary_role,
            "bucket": bucket,
        })
    return jsonify({"candidates": data})

@app.route("/api/classify-all-candidates", methods=["POST"])
def classify_all_candidates():
    rows = Candidate.query.all()
    updated = 0

    for c in rows:
        parsed = c.parsed or {}
        bucket = classify_candidate_bucket(parsed, c.primary_role)

        if c.role_bucket != bucket:
            c.role_bucket = bucket
            updated += 1

    db.session.commit()

    return jsonify({
        "message": f"âœ… Classified {len(rows)} candidates, updated {updated}",
        "breakdown": {
            "data_scientist": Candidate.query.filter_by(role_bucket="data_scientist").count(),
            "data_practice": Candidate.query.filter_by(role_bucket="data_practice").count(),
        }
    })

@app.route("/api/candidates/<int:cand_id>/bench", methods=["PATCH", "OPTIONS"])
@cross_origin()
def update_bench(cand_id):
    if request.method == "OPTIONS":
        return "", 200

    data = request.get_json() or {}
    on_bench = bool(data.get("on_bench", True))

    cand = Candidate.query.get(cand_id)
    if not cand:
        return jsonify({"error": "Candidate not found"}), 404

    cand.on_bench = on_bench
    db.session.add(cand)
    db.session.commit()
    return jsonify({"id": cand.id, "on_bench": cand.on_bench}), 200

@app.route('/api/chat-upload', methods=['POST'])
def chat_upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    try:
        file_type = 'pdf' if file.filename.lower().endswith('.pdf') else 'docx'

        if file_type == 'pdf':
            text = extract_pdf_text(file)
        else:
            text = extract_docx_text(file)

        jd_keywords = ['requirements', 'responsibilities', 'qualifications', 'experience required', 'must have']
        resume_keywords = ['experience', 'projects', 'education', 'linkedin', 'email', 'mobile']

        jd_score = sum(1 for kw in jd_keywords if kw.lower() in text.lower())
        resume_score = sum(1 for kw in resume_keywords if kw.lower() in text.lower())

        if jd_score > resume_score:
            jd_res = requests.post('http://localhost:5050/api/jd', 
                                 json={'text': text}, 
                                 headers={'Content-Type': 'application/json'})
            if jd_res.ok:
                return jsonify({
                    'message': 'âœ… Saved Job Description. Now say "RANK these candidates"',
                    'structured': {'type': 'jd_saved'}
                })
            else:
                return jsonify({'error': 'Failed to save JD'}), 500
        else:
            resume_res = requests.post('http://localhost:5050/api/upload-resumes', 
                                     files={'resumes': (file.filename, file.stream, file.content_type)})
            if resume_res.ok:
                data = resume_res.json()
                return jsonify({
                    'message': f'âœ… Added resume to database. Parsed successfully!',
                    'structured': {'type': 'resume_added'}
                })
            else:
                return jsonify({'error': 'Failed to save resume'}), 500

    except Exception as e:
        return jsonify({'error': f'Processing failed: {str(e)}'}), 500

@app.route("/api/jds")
def list_jds():
    """Full JD dashboard data - all 47 fields + parsed skills"""
    jds = JD.query.order_by(JD.created_at.desc()).limit(100).all()
    return jsonify([{
        # Core identifiers
        "sid": j.sid,
        "title": j.designation or "Unnamed JD",
        "comments": j.comments or "",
        "sub_bu": j.sub_bu or "",
        "account": j.account or "",
        "project": j.project or "",
        "sub_practice_name": j.sub_practice_name or "",
        
        # Job details
        "competency": j.competency or "",
        "designation": j.designation or "",
        "description": j.job_description or "",
        "skills": (j.parsed.get("required_skills", []) if j.parsed else []) + 
                 (j.parsed.get("bonus_skills", []) if j.parsed else []),
        
        # Billing/Status
        "billability": j.billability or "",
        "billing_type": j.billing_type or "",
        "probability": float(j.probability) if j.probability else 0.0,
        "billed_pct": j.billed_pct or "",
        "project_type": j.project_type or "",
        "governance_category": j.governance_category or "",
        
        # Position/Location
        "customer_interview": j.customer_interview or "",
        "position_type": j.position_type or "",
        "location_type": j.location_type or "",
        "base_location_country": j.base_location_country or "",
        "base_location_city": j.base_location_city or "",
        "facility": j.facility or "",
        "fulfilment_type": j.fulfilment_type or "",
        
        # Status/Dates
        "approval_status": j.approval_status or "",
        "sid_status": j.sid_status or "",
        "identified_empid": j.identified_empid or "",
        "identified_empname": j.identified_empname or "",
        "original_billable_date": j.original_billable_date or "",
        "updated_billable_date": j.updated_billable_date or "",
        "billing_end_date": j.billing_end_date or "",
        "requirement_expiry_date": j.requirement_expiry_date or "",
        "resource_required_date": j.resource_required_date or "",
        "requirement_initiated_date": j.requirement_initiated_date or "",
        "month": j.month or "",
        "request_initiated_by": j.request_initiated_by or "",
        "dm": j.dm or "",
        "bdm": j.bdm or "",
        
        # Misc
        "remarks": j.remarks or "",
        "reason_for_cancel": j.reason_for_cancel or "",
        "reason_for_lost": j.reason_for_lost or "",
        "replacement_employee": j.replacement_employee or "",
        "urgent": j.urgent.lower() in ["yes", "true", "1"] if j.urgent else False,
        "ctc_rate": j.ctc_rate or "",
        "customer_reference_id": j.customer_reference_id or "",
        "billing_loss_status": j.billing_loss_status or "",
        "aging": float(j.aging) if j.aging else 0.0,
        "action_items": j.action_items or "",
        
        # Computed/Metadata
        "parsed": j.parsed or {},
        "created_at": j.created_at.isoformat() if j.created_at else None,
        "skill_count": len((j.parsed or {}).get("required_skills", [])),
        "is_urgent": j.urgent.lower() in ["yes", "true", "1"] if j.urgent else False,
        "days_aging": float(j.aging) if j.aging else 0
        
    } for j in jds])


@app.route("/api/jds", methods=["POST"])
def create_jd_row():
    from sqlalchemy.orm.attributes import flag_modified

    data = request.get_json() or {}
    sid = (data.get("sid") or "").strip()
    if not sid:
        return jsonify({"error": "sid required"}), 400
    if JD.query.filter_by(sid=sid).first():
        return jsonify({"error": f"JD '{sid}' already exists"}), 409

    jd = JD(sid=sid)

    # Map friendly fields used by UI
    if "title" in data and "designation" not in data:
        data["designation"] = data.get("title")
    if "description" in data and "job_description" not in data:
        data["job_description"] = data.get("description")

    # skills: accept string "a, b" or list
    parsed = data.get("parsed")
    if not isinstance(parsed, dict):
        parsed = {}
    skills_in = data.get("skills")
    if isinstance(skills_in, str):
        skills_list = [s.strip() for s in skills_in.split(",") if s.strip()]
    elif isinstance(skills_in, list):
        skills_list = [str(s).strip() for s in skills_in if str(s).strip()]
    else:
        skills_list = []
    if skills_list:
        parsed["required_skills"] = [s.lower() for s in skills_list]
        jd.skills = ", ".join(skills_list)
    jd.parsed = parsed
    flag_modified(jd, "parsed")

    # numeric conversions
    for k in ["probability", "aging"]:
        if k in data:
            try:
                setattr(jd, k, float(data.get(k)) if data.get(k) not in (None, "") else 0.0)
            except Exception:
                setattr(jd, k, 0.0)

    # urgent: accept boolean
    if "urgent" in data and isinstance(data.get("urgent"), bool):
        jd.urgent = "Yes" if data.get("urgent") else "No"

    # generic assign for other model attrs
    skip = {"sid", "skills", "parsed", "title", "description", "job_description", "designation", "probability", "aging", "urgent", "created_at", "id"}
    for key, val in data.items():
        if key in skip:
            continue
        if hasattr(jd, key):
            setattr(jd, key, val)
    if "designation" in data:
        jd.designation = (data.get("designation") or "")
    if "job_description" in data:
        jd.job_description = (data.get("job_description") or "")

    db.session.add(jd)
    db.session.commit()

    return list_jds()


@app.route("/api/jds/<string:sid>", methods=["PATCH"])
def update_jd_row(sid: str):
    from sqlalchemy.orm.attributes import flag_modified

    jd = JD.query.filter_by(sid=sid).first()
    if not jd:
        return jsonify({"error": f"JD '{sid}' not found"}), 404

    data = request.get_json() or {}

    # Allow SID change
    if "sid" in data:
        new_sid = (data.get("sid") or "").strip()
        if new_sid and new_sid != jd.sid:
            if JD.query.filter_by(sid=new_sid).first():
                return jsonify({"error": f"JD '{new_sid}' already exists"}), 409
            jd.sid = new_sid

    # Friendly aliases
    if "title" in data and "designation" not in data:
        data["designation"] = data.get("title")
    if "description" in data and "job_description" not in data:
        data["job_description"] = data.get("description")

    if "designation" in data:
        jd.designation = (data.get("designation") or "")
    if "job_description" in data:
        jd.job_description = (data.get("job_description") or "")

    if "probability" in data:
        try:
            jd.probability = float(data.get("probability") if data.get("probability") not in (None, "") else 0.0)
        except Exception:
            jd.probability = 0.0

    if "aging" in data:
        try:
            jd.aging = float(data.get("aging") if data.get("aging") not in (None, "") else 0.0)
        except Exception:
            jd.aging = 0.0

    if "urgent" in data:
        if isinstance(data.get("urgent"), bool):
            jd.urgent = "Yes" if data.get("urgent") else "No"
        else:
            jd.urgent = str(data.get("urgent"))

    if "skills" in data:
        parsed = jd.parsed or {}
        skills_in = data.get("skills")
        if isinstance(skills_in, str):
            skills_list = [s.strip() for s in skills_in.split(",") if s.strip()]
        elif isinstance(skills_in, list):
            skills_list = [str(s).strip() for s in skills_in if str(s).strip()]
        else:
            skills_list = []
        parsed["required_skills"] = [s.lower() for s in skills_list]
        jd.skills = ", ".join(skills_list)
        jd.parsed = parsed
        flag_modified(jd, "parsed")

    skip = {"id", "created_at", "sid", "skills", "parsed", "title", "description", "designation", "job_description", "probability", "aging", "urgent"}
    for key, val in data.items():
        if key in skip:
            continue
        if hasattr(jd, key):
            setattr(jd, key, val)

    db.session.add(jd)
    db.session.commit()

    return list_jds()

@app.route("/api/debug/chroma", methods=["GET"])
def debug_chroma():
    info = {}
    try:
        info["count"] = pipeline.vector_db.collection.count()
        peek = pipeline.vector_db.collection.get(limit=5, include=["metadatas", "documents"])
        info["ids"] = peek.get("ids", [])
        info["metas"] = peek.get("metadatas", [])
    except Exception as e:
        info["error"] = str(e)
    return jsonify(info), 200

@app.route("/api/projects/manage", methods=["POST"])
def manage_project_team():
    """Add or remove a candidate from a project using proper database relationships."""
    from models import CandidateProject, ProjectDB

    data = request.get_json() or {}
    action = (data.get("action") or "").lower()
    project_name = data.get("project_id")  # This is actually the project name
    candidate_id = data.get("candidate_id")

    print(f"🔧 MANAGE: {action} candidate {candidate_id} to/from '{project_name}'")

    if action not in {"add", "remove"}:
        return jsonify({"error": "action must be 'add' or 'remove'"}), 400
    if not project_name or candidate_id is None:
        return jsonify({"error": "project_id and candidate_id required"}), 400

    # Get the candidate
    candidate = db.session.get(Candidate, candidate_id)
    if not candidate:
        return jsonify({"error": "Candidate not found"}), 404

    # Normalize project name for matching
    normalized_name = _normalize_project_key(project_name)
    print(f"🔧 Normalized key: '{normalized_name}'")

    # Find or create the project in ProjectDB
    project = ProjectDB.query.filter(
        db.func.lower(ProjectDB.name) == normalized_name.lower()
    ).first()

    if not project:
        # Extract project details from any candidate who has it in their parsed JSON
        project_data = _find_project_in_parsed_data(normalized_name)
        
        if not project_data:
            return jsonify({"error": "Project not found"}), 404
        
        # Create new project in database
        project = ProjectDB(
            name=project_data.get("name") or project_data.get("project_name") or project_name,
            organization=project_data.get("organization"),
            start_date=project_data.get("start_date"),
            end_date=project_data.get("end_date"),
            duration_months=project_data.get("duration_months"),
            summary=project_data.get("description") or project_data.get("summary"),
            all_technologies=project_data.get("technologies") or project_data.get("technical_tools") or [],
        )
        db.session.add(project)
        db.session.flush()
        print(f"🆕 Created new project: {project.name} (ID: {project.id})")

    if action == "add":
        # Check if candidate is already linked to this project
        existing_link = CandidateProject.query.filter_by(
            candidate_id=candidate_id,
            project_id=project.id
        ).first()

        if existing_link:
            print(f"⚠️ Candidate {candidate_id} already in project {project.id}")
            return jsonify({
                "success": True,
                "message": "Candidate already in project",
                "project_id": project.id
            }), 200

        # Find project details from candidate's parsed data
        project_details = _find_candidate_project_details(candidate, normalized_name)

        # Create new link
        candidate_project = CandidateProject(
            candidate_id=candidate_id,
            project_id=project.id,
            role=project_details.get("role") or candidate.primary_role,
            description=project_details.get("description"),
            responsibilities=project_details.get("responsibilities") or [],
            technical_tools=project_details.get("technologies") or project_details.get("technical_tools") or [],
            contribution=project_details.get("contribution"),
            impact=project_details.get("impact"),
            candidate_start_date=project_details.get("start_date"),
            candidate_end_date=project_details.get("end_date"),
            candidate_duration_months=project_details.get("duration_months"),
        )
        db.session.add(candidate_project)
        
        # Update team count
        project.total_contributors = CandidateProject.query.filter_by(project_id=project.id).count() + 1
        
        db.session.commit()
        print(f"✅ Added {candidate.full_name} to project '{project.name}'")
        print(f"   Total team members: {project.total_contributors}")

        return jsonify({
            "success": True,
            "action": "add",
            "project_id": project.id,
            "project_name": project.name,
            "candidate_id": candidate_id,
            "team_size": project.total_contributors
        }), 200

    elif action == "remove":
        # Find and remove the link
        link = CandidateProject.query.filter_by(
            candidate_id=candidate_id,
            project_id=project.id
        ).first()

        if not link:
            return jsonify({"error": "Candidate not in this project"}), 404

        db.session.delete(link)
        
        # Update team count
        project.total_contributors = max(0, CandidateProject.query.filter_by(project_id=project.id).count() - 1)
        
        db.session.commit()
        print(f"✅ Removed {candidate.full_name} from project '{project.name}'")
        print(f"   Remaining team members: {project.total_contributors}")

        return jsonify({
            "success": True,
            "action": "remove",
            "project_id": project.id,
            "candidate_id": candidate_id,
            "team_size": project.total_contributors
        }), 200

def _find_project_in_parsed_data(normalized_name):
    """Find project details from any candidate's parsed JSON data."""
    all_candidates = Candidate.query.all()
    
    for cand in all_candidates:
        parsed = cand.parsed or {}
        projects = parsed.get("projects") or []
        
        for p in projects:
            pname = p.get("name") or p.get("project_name")
            if _normalize_project_key(pname) == normalized_name:
                return p
    
    return None


def _find_candidate_project_details(candidate, normalized_name):
    """Find specific project details from a candidate's parsed JSON."""
    parsed = candidate.parsed or {}
    projects = parsed.get("projects") or []
    
    for p in projects:
        pname = p.get("name") or p.get("project_name")
        if _normalize_project_key(pname) == normalized_name:
            return p
    
    return {}

def deduplicate_candidate_projects(candidate: Candidate):
    """
    Match this candidate's projects with existing projects in database.
    Merge team members if project already exists.
    """
    parsed = candidate.parsed or {}
    new_projects = parsed.get("projects", [])

    if not new_projects:
        return

    # Get all existing candidates and their projects
    all_candidates = Candidate.query.filter(Candidate.id != candidate.id).all()
    existing_projects = []

    for other_cand in all_candidates:
        other_parsed = other_cand.parsed or {}
        other_projects = other_parsed.get("projects", [])

        for proj in other_projects:
            if proj and proj.get("name"):  # ✅ Check proj is not None
                existing_projects.append({
                    "project": proj,
                    "candidate": other_cand
                })

    # Match each new project
    updated = False

    for new_proj in new_projects:
        if not new_proj or not new_proj.get("name"):  # ✅ Skip None projects
            continue

        # Try to find matching project
        best_match = None
        best_score = 0.0

        for existing in existing_projects:
            score = calculate_project_similarity(new_proj, existing["project"])

            if score > best_score and score >= 0.70:  # 70% threshold
                best_score = score
                best_match = existing

        if best_match:
            # ✅ Found matching project!
            matched_proj = best_match["project"]
            matched_cand = best_match["candidate"]

            print(f"✅ MATCH: '{new_proj.get('name')}' matches '{matched_proj.get('name')}' ({best_score:.1%})")

            # ✅ Initialize team_members if None
            if matched_proj.get("team_members") is None:
                matched_proj["team_members"] = []
            if new_proj.get("team_members") is None:
                new_proj["team_members"] = []

            # Add current candidate to the matched project's team
            if candidate.id not in [m.get("id") for m in matched_proj["team_members"]]:
                matched_proj["team_members"].append({
                    "id": candidate.id,
                    "name": candidate.full_name or "Unknown",
                    "role": new_proj.get("role") or candidate.primary_role,
                    "years": float(candidate.total_experience_years or 0.0),
                })

                # Save the updated matched candidate
                flag_modified(matched_cand, "parsed")
                db.session.add(matched_cand)
                print(f"   Added {candidate.full_name} to team in {matched_cand.full_name}'s record")

            # Also add matched candidate to THIS project's team
            if matched_cand.id not in [m.get("id") for m in new_proj["team_members"]]:
                new_proj["team_members"].append({
                    "id": matched_cand.id,
                    "name": matched_cand.full_name or "Unknown",
                    "role": matched_proj.get("role") or matched_cand.primary_role,
                    "years": float(matched_cand.total_experience_years or 0.0),
                })
                updated = True
                print(f"   Added {matched_cand.full_name} to team in {candidate.full_name}'s record")

            # Merge technologies (handle None)
            existing_techs = set(matched_proj.get("technologies_used") or matched_proj.get("technical_tools") or [])
            new_techs = set(new_proj.get("technologies_used") or new_proj.get("technical_tools") or [])
            merged_techs = list(existing_techs | new_techs)

            if merged_techs:
                new_proj["technologies_used"] = merged_techs
                matched_proj["technologies_used"] = merged_techs
                updated = True

        else:
            # ✅ New unique project
            print(f"🆕 NEW PROJECT: '{new_proj.get('name')}'")

            # Initialize team_members with just this candidate
            if new_proj.get("team_members") is None:
                new_proj["team_members"] = []
            
            if candidate.id not in [m.get("id") for m in new_proj["team_members"]]:
                new_proj["team_members"].append({
                    "id": candidate.id,
                    "name": candidate.full_name or "Unknown",
                    "role": new_proj.get("role") or candidate.primary_role,
                    "years": float(candidate.total_experience_years or 0.0),
                })
                updated = True

    if updated:
        candidate.parsed = parsed
        flag_modified(candidate, "parsed")
        db.session.add(candidate)
        db.session.commit()
        print(f"💾 Saved deduplication for {candidate.full_name}")

def calculate_project_similarity(proj1: dict, proj2: dict) -> float:
    """
    Calculate similarity score between two projects (0.0 to 1.0).
    Based on project name, organization, and description.
    """
    if not proj1 or not proj2:
        return 0.0

    # Get project names (required)
    name1 = (proj1.get("name") or "").lower().strip()
    name2 = (proj2.get("name") or "").lower().strip()

    if not name1 or not name2:
        return 0.0

    # Exact name match = 100%
    if name1 == name2:
        return 1.0

    # Calculate similarity scores
    scores = []

    # 1. Name similarity (70% weight)
    name_sim = fuzz.ratio(name1, name2) / 100.0
    scores.append(name_sim * 0.7)

    # 2. Organization similarity (15% weight)
    org1 = (proj1.get("organization") or "").lower().strip()
    org2 = (proj2.get("organization") or "").lower().strip()
    if org1 and org2:
        org_sim = fuzz.ratio(org1, org2) / 100.0
        scores.append(org_sim * 0.15)

    # 3. Description similarity (15% weight)
    desc1 = (proj1.get("description") or "").lower().strip()
    desc2 = (proj2.get("description") or "").lower().strip()
    if desc1 and desc2:
        desc_sim = fuzz.partial_ratio(desc1, desc2) / 100.0
        scores.append(desc_sim * 0.15)

    # Final score
    final_score = sum(scores)

    return final_score

@app.route("/api/projects-db", methods=["GET"])
@cross_origin()
def get_all_projects_db():
    """Get all projects from ProjectDB with contributor details and summaries"""
    from models import ProjectDB
    
    try:
        projects = ProjectDB.query.order_by(ProjectDB.created_at.desc()).all()
        
        result = []
        for proj in projects:
            proj_dict = proj.to_dict()
            
            # ✅ Add contributor details
            contributors = []
            for contrib in proj.contributions:
                if not contrib.candidate:
                    continue
                
                candidate = contrib.candidate
                contributors.append({
                    "id": contrib.id,
                    "candidate_id": candidate.id,
                    "candidate_name": candidate.full_name or "Unknown",
                    "role": contrib.role,
                    "description": contrib.description,
                    "responsibilities": contrib.responsibilities or [],
                    "technical_tools": contrib.technical_tools or [],
                    "contribution": contrib.contribution,
                    "impact": contrib.impact,
                    "candidate_start_date": contrib.candidate_start_date,
                    "candidate_end_date": contrib.candidate_end_date,
                    "candidate_duration_months": contrib.candidate_duration_months,
                })
            
            proj_dict["contributors"] = contributors
            
            # ✅ Determine status (ongoing vs archived)
            if proj.end_date and proj.end_date.lower() not in ["present", "current", "ongoing"]:
                proj_dict["status"] = "archived"
            elif proj.start_date and not proj.end_date:
                proj_dict["status"] = "archived"  # No dates = archived
            else:
                proj_dict["status"] = "ongoing"
            
            result.append(proj_dict)
        
        return jsonify({
            "success": True,
            "projects": result,
            "total": len(result)
        }), 200
        
    except Exception as e:
        print(f"Error fetching projects: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/projects-db/<int:project_id>", methods=["GET"])
def get_project_details(project_id):
    """Get detailed information about a specific project"""
    from models import ProjectDB
    
    project = ProjectDB.query.get(project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404
    
    project_dict = project.to_dict()
    
    # Add detailed contributor information
    contributors = []
    for contrib in project.contributions:
        if contrib.candidate:
            contributors.append({
                "id": contrib.candidate.id,
                "name": contrib.candidate.full_name,
                "email": contrib.candidate.email,
                "role": contrib.role,
                "description": contrib.description,
                "responsibilities": contrib.responsibilities,
                "technical_tools": contrib.technical_tools,
                "contribution": contrib.contribution,
                "impact": contrib.impact,
                "start_date": contrib.candidate_start_date,
                "end_date": contrib.candidate_end_date,
                "duration_months": contrib.candidate_duration_months,
            })
    
    project_dict["contributors"] = contributors
    
    return jsonify(project_dict), 200


@app.route("/api/candidates/<int:candidate_id>/projects-db", methods=["GET"])
def get_candidate_projects_db(candidate_id):
    """Get all projects a candidate has worked on from ProjectDB"""
    from models import CandidateProject, ProjectDB
    
    contributions = CandidateProject.query.filter_by(candidate_id=candidate_id).all()
    
    projects = []
    for contrib in contributions:
        if contrib.project:
            project_dict = contrib.project.to_dict()
            project_dict["my_role"] = contrib.role
            project_dict["my_responsibilities"] = contrib.responsibilities
            project_dict["my_tools"] = contrib.technical_tools
            project_dict["my_impact"] = contrib.impact
            projects.append(project_dict)
    
    return jsonify({"projects": projects}), 200

@app.route("/api/rebuild-chroma", methods=["POST"])
def rebuild_chroma():
    """Rebuild ChromaDB from current candidates in database"""
    try:
        # Import ChromaDB collection directly
        import chromadb
        from chromadb.config import Settings
        
        # Initialize ChromaDB client (match your existing setup)
        chroma_client = chromadb.PersistentClient(
            path="./chroma_db",
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Get or create collection
        collection = chroma_client.get_or_create_collection(
            name="resumes",
            metadata={"hnsw:space": "cosine"}
        )
        
        # 1. Clear existing collection
        try:
            # Get all IDs first
            all_ids = collection.get()['ids']
            if all_ids:
                collection.delete(ids=all_ids)
                print(f"🧹 Cleared {len(all_ids)} documents from ChromaDB")
        except Exception as e:
            print(f"⚠️ Collection was empty: {e}")
        
        # 2. Get all current candidates
        from models import Candidate
        candidates = Candidate.query.all()
        
        # 3. Re-add them to ChromaDB
        from sentence_transformers import SentenceTransformer
        embedding_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        
        count = 0
        for cand in candidates:
            if cand.raw_text:
                try:
                    # Generate embedding
                    embedding = embedding_model.encode(cand.raw_text).tolist()
                    
                    # Add to ChromaDB
                    collection.add(
                        ids=[f"resume_{cand.id}"],
                        embeddings=[embedding],
                        documents=[cand.raw_text],
                        metadatas=[{
                            "candidate_id": cand.id,
                            "name": cand.full_name or "Unknown",
                            "source": "resume"
                        }]
                    )
                    count += 1
                    print(f"✅ Added candidate {cand.id} - {cand.full_name}")
                except Exception as e:
                    print(f"❌ Failed to add {cand.id}: {e}")
        
        return jsonify({
            "success": True,
            "message": f"✅ Rebuilt ChromaDB with {count} candidates",
            "candidates_in_db": len(candidates),
            "chunks_added": count
        })
        
    except Exception as e:
        import traceback
        print(f"❌ Error rebuilding ChromaDB: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/upload-jds-csv", methods=["POST"])
def upload_jds_csv():
    print("DEBUG: Endpoint hit, pandas =", pd.__version__)
    if "jds_csv" not in request.files:
        return jsonify({"error": "jds_csv required"}), 400
    
    file = request.files["jds_csv"]
    print(f"DEBUG: File received: {file.filename}, size: {file.content_length}")
    
    try:
        df = pd.read_csv(file.stream, encoding='utf-8-sig')
        print(f"DEBUG: CSV parsed: {len(df)} rows, columns: {list(df.columns)}")
    except Exception as e:
        return jsonify({"error": f"CSV parse failed: {str(e)}"}), 422
    
    # Rename exact CSV columns to model fields
    df.columns = df.columns.str.strip()
    rename_map = {
        "Billed %": "billed_pct",
        "CTC / Rate": "ctc_rate",
        "Identified EmpID": "identified_empid",
        "Identified EmpName": "identified_empname",
        "SID Status": "sid_status",
        "Sub BU": "sub_bu",
        "Sub Practice Name": "sub_practice_name"
    }
    df.rename(columns=rename_map, inplace=True)
    
    created = 0
    skipped = 0
    
    for index, row in df.iterrows():
        sid_raw = row.get("SID")
        if pd.isna(sid_raw) or str(sid_raw).strip() == "":
            skipped += 1
            continue
        
        sid = str(sid_raw).strip()
        if JD.query.filter_by(sid=sid).first():
            print(f"DEBUG: SID {sid} exists, skip")
            skipped += 1
            continue
        
        # Skills parsing → skills field + parsed JSON
        skills_raw = str(row.get("Skills", ""))
        required_skills = [s.strip().lower() for s in skills_raw.split(",") if s.strip()]
        
        desc = str(row.get("Job Description", ""))
        bonus_match = re.search(r"Good to Have[:\s]*([^\.]+)", desc, re.I | re.DOTALL)
        bonus_skills = [s.strip().lower() for s in (bonus_match.group(1).split(",") if bonus_match else []) if s.strip()]
        
        row["parsed"] = {
            "required_skills": required_skills,
            "bonus_skills": bonus_skills,
            "description": desc
        }
        
        # Float conversion for numerics
        row["probability"] = float(row.get("Probability", 0)) if row.get("Probability") else 0.0
        row["aging"] = float(row.get("Aging", 0)) if row.get("Aging") else 0.0
        
        # Create JD with ALL fields
        jd = JD(**row.to_dict())
        db.session.add(jd)
        created += 1
        print(f"DEBUG: Created JD {sid}")
    
    db.session.commit()
    print(f"DEBUG: FINAL: created={created}, skipped={skipped}, total={len(df)}")
    
    return jsonify({
        "created": created,
        "skipped": skipped,
        "total_rows": len(df),
    })

@app.route("/api/llm-rank", methods=["POST"])
def llm_rank_jd():
    data = request.json
    sid = data.get("sid")
    bucket = data.get("bucket", "all")
    bench_status = data.get("bench_status", "all")
    
    # 🐛 DEBUG LOGS
    print(f"🤖 LLM-RANK CALLED: sid={sid}, bucket={bucket}, bench={bench_status}")
    
    # Fetch JD with ALL data
    jd = JD.query.filter_by(sid=sid).first()
    if not jd:
        return jsonify({"error": f"JD '{sid}' not found"}), 404
    
    # Extract full JD data
    jd_parsed = jd.parsed or {}
    required_skills = [s.lower().strip() for s in (jd_parsed.get("required_skills", []) or [])]
    bonus_skills = [s.lower().strip() for s in (jd_parsed.get("bonus_skills", []) or [])]
    all_jd_skills = required_skills + bonus_skills
    
    # Full JD context for LLM
    jd_full_data = {
        "sid": jd.sid,
        "designation": jd.designation or "",
        "competency": jd.competency or "",
        "job_description": jd.job_description or "",
        "required_skills": required_skills,
        "bonus_skills": bonus_skills,
        "location_type": jd.location_type or "",
        "base_location_city": jd.base_location_city or "",
        "base_location_country": jd.base_location_country or "",
        "ctc_rate": jd.ctc_rate or "",
        "billability": jd.billability or "",
        "project": jd.project or "",
        "account": jd.account or "",
    }
    
    # Fetch filtered candidates
    candidates = Candidate.query
    
    # Filter by bucket
    if bucket != "all" and bucket != "both":
        candidates = candidates.filter(Candidate.role_bucket == bucket)
        print(f"   ✅ Filtered by bucket: {bucket}")
    
    # Filter by bench status (on_bench is boolean, not bench_status string)
    if bench_status != "all" and bench_status != "both":
        if bench_status == "on":
            candidates = candidates.filter(Candidate.on_bench == True)
            print(f"   ✅ Filtered by bench: ON BENCH")
        elif bench_status == "off":
            candidates = candidates.filter(Candidate.on_bench == False)
            print(f"   ✅ Filtered by bench: ON PROJECT")
    
    candidates = candidates.all()  # Get all, not just 50
    print(f"📊 Found {len(candidates)} candidates for ranking after filters")
    
    if not candidates:
        return jsonify({"error": "No candidates found with these filters"}), 404
    
    # Prepare FULL candidate data for scoring
    candidate_full_data = []
    for c in candidates:
        parsed_c = c.parsed or {}
        
        # Extract ALL skills from multiple sources
        skills_list = []
        if parsed_c.get("technical_skills"):
            skills_list.extend(parsed_c["technical_skills"])
        if parsed_c.get("skills"):
            skills_list.extend(parsed_c["skills"])
        if c.skills:
            skills_list.extend(c.skills if isinstance(c.skills, list) else [])
        # Deduplicate and normalize
        skills_list = [s.lower().strip() for s in skills_list if s]
        skills_list = list(set(skills_list))
        
        # Extract ALL projects with full details
        projects = parsed_c.get("projects", []) or []
        if not projects and c.projects:
            projects = c.projects if isinstance(c.projects, list) else []
        
        # Extract ALL work experiences with full details
        work_experiences = parsed_c.get("work_experiences", []) or []
        if not work_experiences and c.work_experiences:
            work_experiences = c.work_experiences if isinstance(c.work_experiences, list) else []
        
        # Total experience
        total_exp = (
            parsed_c.get("total_experience_years")
            or parsed_c.get("total_exp")
            or c.total_experience_years
            or 0.0
        )
        
        # Bench status
        bench_status_val = "bench" if (getattr(c, "on_bench", False) or getattr(c, "bench_status", "").lower() == "on") else "active"
        
        candidate_full_data.append({
            "id": c.id,
            "name": c.full_name or "Unknown",
            "skills": skills_list,
            "projects": projects,
            "work_experiences": work_experiences,
            "total_experience_years": float(total_exp),
            "primary_role": c.primary_role or parsed_c.get("primary_role", ""),
            "bench_status": bench_status_val,
            "parsed": parsed_c,  # Full parsed data for reference
        })
    
    def score_candidate(cand_data: dict) -> tuple[float, str]:
        """
        Advanced scoring prioritizing:
        1. Skills match (primary, ~50%)
        2. Relevant project experience where skills were used (~30%, counts more)
        3. Work experience (~15%)
        4. Bench status and other factors (~5%)
        """
        cand_skills = cand_data["skills"]
        cand_projects = cand_data["projects"]
        cand_work_exp = cand_data["work_experiences"]
        total_exp = cand_data["total_experience_years"]
        
        # 1. SKILLS MATCH (Primary - 50 points max)
        required_matches = sum(1 for skill in required_skills if any(skill in cs for cs in cand_skills))
        bonus_matches = sum(1 for skill in bonus_skills if any(skill in cs for cs in cand_skills))
        
        # Weight required skills more than bonus
        skills_score = min(50.0, (required_matches * 8.0) + (bonus_matches * 2.0))
        skills_pct = (required_matches / len(required_skills)) * 100 if required_skills else 0
        
        # 2. RELEVANT PROJECT EXPERIENCE (30 points max - counts more!)
        project_score = 0.0
        relevant_projects = []
        
        for proj in cand_projects:
            if not proj:
                continue
            
            # Check if project uses JD skills
            proj_techs = []
            if isinstance(proj, dict):
                proj_techs.extend(proj.get("technologies_used", []) or [])
                proj_techs.extend(proj.get("technical_tools", []) or [])
                proj_desc = (proj.get("description", "") or "").lower()
                proj_name = (proj.get("name", "") or "").lower()
            else:
                continue
            
            # Normalize project techs
            proj_techs = [t.lower().strip() for t in proj_techs if t]
            
            # Count how many JD skills appear in this project
            project_skill_matches = 0
            for jd_skill in all_jd_skills:
                # Check in techs
                if any(jd_skill in pt for pt in proj_techs):
                    project_skill_matches += 1
                # Check in description
                elif jd_skill in proj_desc or jd_skill in proj_name:
                    project_skill_matches += 1
            
            if project_skill_matches > 0:
                # More matches = higher score, recent projects weighted more
                project_value = min(10.0, project_skill_matches * 2.5)
                project_score += project_value
                relevant_projects.append({
                    "name": proj.get("name", "Unknown"),
                    "matches": project_skill_matches,
                    "value": project_value
                })
        
        project_score = min(30.0, project_score)  # Cap at 30
        
        # 3. WORK EXPERIENCE (15 points max)
        work_exp_score = 0.0
        relevant_work = []
        
        for work in cand_work_exp:
            if not work or not isinstance(work, dict):
                continue
            
            work_techs = []
            work_techs.extend(work.get("technologies_used", []) or [])
            work_techs.extend(work.get("technical_tools", []) or [])
            work_techs.extend(work.get("skills", []) or [])
            work_techs = [t.lower().strip() for t in work_techs if t]
            
            work_desc = (work.get("description", "") or "").lower()
            work_title = (work.get("job_title", "") or work.get("title", "") or "").lower()
            
            # Count JD skill matches in work experience
            work_skill_matches = sum(1 for jd_skill in all_jd_skills 
                                    if any(jd_skill in wt for wt in work_techs) 
                                    or jd_skill in work_desc 
                                    or jd_skill in work_title)
            
            if work_skill_matches > 0:
                work_value = min(5.0, work_skill_matches * 1.5)
                work_exp_score += work_value
                relevant_work.append({
                    "company": work.get("company_name", "Unknown"),
                    "title": work.get("job_title", "Unknown"),
                    "matches": work_skill_matches
                })
        
        work_exp_score = min(15.0, work_exp_score)  # Cap at 15
        
        # 4. EXPERIENCE YEARS BONUS (5 points max)
        exp_bonus = min(5.0, total_exp * 0.5) if total_exp > 0 else 0.0
        
        # 5. BENCH STATUS (5 points)
        bench_bonus = 5.0 if cand_data["bench_status"] == "bench" else 2.0
        
        # TOTAL SCORE
        total_score = skills_score + project_score + work_exp_score + exp_bonus + bench_bonus
        
        # Build detailed reasoning
        reason_parts = []
        if required_matches > 0:
            reason_parts.append(f"{required_matches}/{len(required_skills)} required skills ({skills_pct:.0f}%)")
        if relevant_projects:
            reason_parts.append(f"{len(relevant_projects)} relevant projects")
        if relevant_work:
            reason_parts.append(f"{len(relevant_work)} relevant work experiences")
        if total_exp > 0:
            reason_parts.append(f"{total_exp:.1f} yrs exp")
        reason_parts.append(f"bench={cand_data['bench_status']}")
        
        reasoning = " | ".join(reason_parts) if reason_parts else "Limited match"
        
        return total_score, reasoning
    
    # Score all candidates
    scored = []
    for cand_data in candidate_full_data:
        score, reasoning = score_candidate(cand_data)
        scored.append({
            "candidate_id": cand_data["id"],
            "candidate_name": cand_data["name"],
            "score": round(score, 1),
            "reasoning": reasoning,
        })
    
    # Sort by score descending
    scored.sort(key=lambda x: x["score"], reverse=True)
    
    # Assign ranks and take top 10
    for i, r in enumerate(scored[:10], start=1):
        r["rank"] = i
    
    rankings = scored[:10]
    
    return jsonify({
        "jd": {
            "sid": jd.sid,
            "title": jd.designation,
            "competency": jd.competency,
            "skills": required_skills,
            "location": jd.location_type
        },
        "rankings": rankings,
        "total_candidates": len(candidates),
        "filters": {"bucket": bucket, "bench_status": bench_status},
        "success": True
    })

if __name__ == '__main__':
    app.run(debug=True, port=5050)
