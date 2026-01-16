from typing import Dict, List, Any, Optional, Tuple
from groq import Groq
import os
import json
import re
from datetime import datetime, timedelta
from functools import lru_cache
from models import Candidate, db
from sqlalchemy import cast, String, func, or_, and_
from collections.abc import Mapping

class GeneralQueryHandler:
    """
    Production-grade natural language query handler for candidate-related questions.
    
    Features:
    - Multi-intent understanding (handles compound queries)
    - Smart skill matching with aliases and fuzzy matching
    - Context-aware responses with conversation memory
    - Advanced filtering (nested conditions, ranges, exclusions)
    - Query optimization with result caching
    - Fallback strategies for low-quality data
    - Analytics and insights generation
    """
    
    # Skill aliases for better matching
    SKILL_ALIASES = {
        "python": ["py", "python3", "cpython"],
        "javascript": ["js", "node", "nodejs", "node.js"],
        "react": ["reactjs", "react.js"],
        "aws": ["amazon web services", "amazon aws"],
        "gcp": ["google cloud", "google cloud platform"],
        "azure": ["microsoft azure", "ms azure"],
        "kubernetes": ["k8s", "kube"],
        "tensorflow": ["tf"],
        "pytorch": ["torch"],
        "sql": ["mysql", "postgresql", "postgres", "mssql", "oracle"],
        "nosql": ["mongodb", "cassandra", "dynamodb", "redis"],
        "spark": ["apache spark", "pyspark"],
        "docker": ["containers", "containerization"],
        "machine learning": ["ml", "ai", "artificial intelligence"],
        "deep learning": ["dl", "neural networks"],
        "data science": ["ds"],
        "etl": ["data pipeline", "data pipelines"],
    }
    
    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self._cache = {}
        self._cache_ttl = 300
        self._session_memory = {}  # ✅ NEW: Store last filters per session
        
    def _extract_candidate_rows(self, candidates: List[Candidate]) -> List[Dict]:
        """Extract candidate data into a clean format for display."""
        
        rows = []
        for c in candidates:
            # Extract skills from parsed JSON or fallback
            skills = []
            location = "N/A"
            
            if c.parsed and isinstance(c.parsed, dict):
                skills = c.parsed.get('technical_skills', []) or c.parsed.get('skills', [])
                location = c.parsed.get('location', 'N/A')
            
            rows.append({
                "id": c.id,
                "name": c.full_name or "Unknown",
                "email": c.email or "N/A",
                "phone": c.phone or "N/A",
                "role": c.primary_role or "Not specified",
                "experience": c.total_experience_years or 0,
                "bucket": c.role_bucket or "Unknown",
                "skills": skills,
                "on_bench": getattr(c, 'on_bench', None),
                "location": location
            })
        
        return rows

    def handle_query(self, user_query: str, context: Optional[List[Dict]] = None, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Main entry point with session-based memory.
        ALWAYS returns something useful - never gives up!
        """
        
        # Check cache first
        cache_key = self._get_cache_key(user_query, context)
        cached = self._get_from_cache(cache_key)
        if cached:
            print(f"✅ Cache hit for: {user_query[:50]}...")
            return cached
        
        try:
            # Get last filters from session memory
            last_filters = self._session_memory.get(session_id, {}) if session_id else {}
            print(f"📝 LAST SESSION FILTERS: {last_filters}")
            
            # Extract intent
            intent = self._extract_intent(
                user_query, 
                context=context, 
                last_filters=last_filters
            )
            print(f"🎯 Extracted intent: {json.dumps(intent, indent=2)}")
            
            # Validate and enrich intent
            intent = self._enrich_intent(intent, user_query)
            
            # Fetch candidates with optimized query
            candidates, suggestion = self._fetch_candidates(intent)
            print(f"📊 Found {len(candidates)} candidates")
            
            # ✅ FALLBACK: If no candidates found, try broader search
            if not candidates and intent.get("filters"):
                print("🔄 No results with filters, trying broader search...")
                
                # Try without some filters
                broader_intent = intent.copy()
                broader_intent["filters"] = {}
                
                # Keep only name filter if it exists
                if "candidate_name" in intent.get("filters", {}):
                    broader_intent["filters"]["candidate_name"] = intent["filters"]["candidate_name"]
                elif "name" in intent.get("filters", {}):
                    broader_intent["filters"]["name"] = intent["filters"]["name"]
                elif "name_filter" in intent.get("filters", {}):
                    broader_intent["filters"]["name_filter"] = intent["filters"]["name_filter"]
                
                candidates, broader_suggestion = self._fetch_candidates(broader_intent)
                if broader_suggestion:
                    suggestion = broader_suggestion
                print(f"📊 Broader search found {len(candidates)} candidates")
            
            # Generate response (now with candidates and suggestion)
            response = self._generate_response(user_query, intent, candidates, context, suggestion)
            
            # Save filters to session memory for next query
            if session_id and intent.get("filters"):
                self._session_memory[session_id] = intent["filters"]
                print(f"💾 SAVED FILTERS TO SESSION: {intent['filters']}")
            
            # Cache the result
            self._set_cache(cache_key, response)
            
            return response
            
        except Exception as e:
            print(f"❌ Query handling error: {e}")
            import traceback
            traceback.print_exc()
            
            # ✅ SMART FALLBACK: Try to get ANY candidates and show them
            try:
                print("🆘 Attempting emergency fallback...")
                
                # Try to extract just the name from query
                query_lower = user_query.lower()
                
                # Common name extraction patterns
                name_keywords = ['about', 'for', 'of', 'from', 'candidate', 'person', 'named']
                potential_name = None
                
                for keyword in name_keywords:
                    if keyword in query_lower:
                        parts = query_lower.split(keyword)
                        if len(parts) > 1:
                            # Get text after keyword
                            potential_name = parts[1].strip().split()[0] if parts[1].strip() else None
                            break
                
                # If we found a potential name, search for it
                if potential_name:
                    emergency_candidates = Candidate.query.filter(
                        Candidate.full_name.ilike(f"%{potential_name}%")
                    ).limit(10).all()
                    
                    if emergency_candidates:
                        candidate_rows = self._extract_candidate_rows(emergency_candidates)
                        
                        return {
                            "type": "table",
                            "message": f"Found {len(emergency_candidates)} candidate(s) matching '{potential_name}'. Here's what I found:",
                            "data": {
                                "candidates": candidate_rows,
                                "total": len(candidate_rows),
                                "filters": {"name_filter": potential_name},
                                "insights": {}
                            }
                        }
                
                # Last resort: show recent candidates
                recent_candidates = Candidate.query.order_by(Candidate.created_at.desc()).limit(5).all()
                if recent_candidates:
                    candidate_rows = self._extract_candidate_rows(recent_candidates)
                    
                    return {
                        "type": "table",
                        "message": f"I had trouble understanding your query '{user_query}', but here are {len(recent_candidates)} recent candidates that might help:",
                        "data": {
                            "candidates": candidate_rows,
                            "total": len(candidate_rows),
                            "filters": {},
                            "insights": {}
                        }
                    }
                
            except Exception as fallback_error:
                print(f"❌ Fallback also failed: {fallback_error}")
            
            # Absolute last resort
            return {
                "type": "text",
                "message": f"I'm having trouble processing '{user_query}'. Try asking:\n\n" +
                        "• 'show me all candidates'\n" +
                        "• 'who is [candidate name]'\n" +
                        "• 'list data scientists'\n" +
                        "• 'candidates with Python skills'",
                "data": {"error": str(e)}
            }
    
    def _extract_intent(self, user_query: str, context: Optional[List[Dict]] = None, last_filters: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Advanced intent extraction with session memory.
        """
        
        last_filters = last_filters or {}
        
        # Build context string from previous queries
        context_str = ""
        if context:
            recent = context[-3:]
            context_lines = []
            for msg in recent:
                user_msg = msg.get('user', '')
                assistant_msg = msg.get('assistant', '')
                context_lines.append(f"User: {user_msg}")
                context_lines.append(f"Assistant: {assistant_msg}")
            context_str = "\n".join(context_lines)
        
        # Build prompt parts
        prompt_parts = ["You are an advanced query understanding AI for a candidate database.", ""]
        prompt_parts.append("Extract structured intent from the user's query.")
        prompt_parts.append("")
        
        if context_str:
            prompt_parts.append("CONVERSATION CONTEXT:")
            prompt_parts.append(context_str)
            prompt_parts.append("")
        
        # ✅ CRITICAL: Tell LLM about last filters
        if last_filters:
            prompt_parts.append(f"PREVIOUS QUERY FILTERS: {json.dumps(last_filters)}")
            prompt_parts.append("")
            prompt_parts.append("IMPORTANT RULES:")
            prompt_parts.append("- If user asks a follow-up question with 'his/her/their/them', INHERIT previous filters")
            prompt_parts.append("- If user asks 'what about X' or 'show me X', INHERIT previous filters")
            prompt_parts.append("- Only REPLACE filters if user explicitly mentions a NEW filter")
            prompt_parts.append("")
            prompt_parts.append("EXAMPLES:")
            prompt_parts.append(f"Previous: {json.dumps(last_filters)}")
            prompt_parts.append('User asks: "what are their skills" → KEEP filters: ' + json.dumps(last_filters))
            prompt_parts.append('User asks: "what are his projects" → KEEP filters: ' + json.dumps(last_filters))
            prompt_parts.append('User asks: "show me data engineers" → REPLACE with new filters')
            prompt_parts.append("")
        
        prompt_parts.append(f"Query: \"{user_query}\"")
        prompt_parts.append("")
        prompt_parts.append("Extract intent and return JSON with: query_type, filters, limit, sort_by, aggregation, confidence")
        prompt_parts.append("")
        prompt_parts.append("IMPORTANT: If query mentions certifications/certificates, set query_type='certification' and extract certification_name in filters.")
        prompt_parts.append("Examples:")
        prompt_parts.append('- "how many people have AWS certification" → query_type: "certification", filters: {certification_name: "AWS"}')
        prompt_parts.append('- "who has completed PMP certificate" → query_type: "certification", filters: {certification_name: "PMP"}')
        prompt_parts.append("")
        prompt_parts.append("Return ONLY valid JSON.")
        
        prompt = "\n".join(prompt_parts)
        
        try:
            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are a query intent extraction AI. Return ONLY valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=800
            )
            
            intent = json.loads(response.choices[0].message.content)
            
            # ✅ FALLBACK: If no filters extracted and it's a follow-up, force inherit
            query_lower = user_query.lower()
            follow_up_indicators = ['his', 'her', 'their', 'them', 'those', 'these', 'what about', 'how about']
            
            is_follow_up = any(indicator in query_lower for indicator in follow_up_indicators)
            has_no_new_filters = not intent.get("filters") or len(intent.get("filters", {})) == 0
            
            if is_follow_up and has_no_new_filters and last_filters:
                print(f"🔗 FORCING FILTER INHERITANCE: {last_filters}")
                intent["filters"] = last_filters.copy()
            
            return intent
            
        except Exception as e:
            print(f"❌ Intent extraction failed: {e}")
            return self._fallback_intent_extraction(user_query)
    
    def _fallback_intent_extraction(self, user_query: str) -> Dict[str, Any]:
        """
        Keyword-based fallback when LLM fails.
        """
        text = user_query.lower()
        intent = {
            "query_type": "list",
            "filters": {},
            "limit": 10,
            "sort_by": None,
            "aggregation": None,
            "confidence": 0.6
        }
        
        # Detect query type
        if any(kw in text for kw in ["how many", "count", "total"]):
            intent["query_type"] = "count"
            intent["aggregation"] = "count"
        elif any(kw in text for kw in ["avg", "average", "mean"]):
            intent["query_type"] = "stats"
            intent["aggregation"] = "average"
        
        # Detect bucket
        if "data scientist" in text:
            intent["filters"]["role_bucket"] = "data_scientist"
        elif "data practice" in text or "data engineer" in text:
            intent["filters"]["role_bucket"] = "data_practice"
        
        # Detect experience
        import re
        exp_match = re.search(r'(\d+)\+?\s*(?:years?|yrs?)', text)
        if exp_match:
            intent["filters"]["min_experience"] = int(exp_match.group(1))
        
        # Detect skills
        common_skills = ["python", "sql", "java", "aws", "spark", "react", "docker", "kubernetes"]
        skills_found = [skill for skill in common_skills if skill in text]
        if skills_found:
            intent["filters"]["skills_required"] = skills_found
        
        # Detect certifications - improved extraction
        if any(kw in text for kw in ["certification", "certificate", "certified", "has completed", "completed", "have completed"]):
            intent["query_type"] = "certification"
            # Try to extract certification name with better patterns
            import re
            cert_patterns = [
                # "who all have completed tensor flow developer certifications"
                r'(?:who\s+all|who|people|person|candidates?)\s+(?:have|has|completed|with)\s+([A-Za-z0-9\s\-&]+?)(?:\s+certification|\s+certificate|\s+certified|$)',
                # "how many people have AWS certification"
                r'(?:have|has|completed|with)\s+([A-Za-z0-9\s\-&]+?)(?:\s+certification|\s+certificate|\s+certified|$)',
                # "AWS certification"
                r'([A-Za-z0-9\s\-&]+?)\s+(?:certification|certificate|certified)',
                # "certification in AWS"
                r'(?:certification|certificate|certified|completed)\s+(?:in|for|on)?\s+([A-Za-z0-9\s\-&]+?)(?:\s+by|\s+from|$)',
                # "who has PMP"
                r'(?:who|people|person|candidates?)\s+(?:has|have|with)\s+([A-Za-z0-9\s\-&]+?)(?:\s+certification|\s+certificate|$)',
            ]
            for pattern in cert_patterns:
                match = re.search(pattern, user_query, re.IGNORECASE)
                if match:
                    cert_name = match.group(1).strip()
                    # Clean up common words and normalize
                    cert_name = re.sub(r'\b(?:the|a|an|in|for|on|by|from|all)\b', '', cert_name, flags=re.IGNORECASE).strip()
                    # Capitalize first letter of each word for consistency
                    cert_name = ' '.join(word.capitalize() if word else '' for word in cert_name.split())
                    if len(cert_name) > 1:  # Valid certification name
                        intent["filters"]["certification_name"] = cert_name
                        print(f"   ✅ Extracted certification name: '{cert_name}'")
                        break
            
            # If no pattern matched, try to extract any capitalized words/phrases
            if not intent["filters"].get("certification_name"):
                # Look for capitalized acronyms or words (like AWS, PMP, Azure, etc.)
                caps_match = re.search(r'\b([A-Z]{2,}(?:\s+[A-Z][a-z]+)*)\b', user_query)
                if caps_match:
                    potential_cert = caps_match.group(1).strip()
                    # Check if it's not a common word
                    common_words = ['AWS', 'THE', 'AND', 'FOR', 'WHO', 'HOW', 'MANY', 'HAVE', 'HAS']
                    if potential_cert not in common_words:
                        intent["filters"]["certification_name"] = potential_cert
                        print(f"   ✅ Extracted certification name (caps): '{potential_cert}'")
        
        return intent
    
    def _enrich_intent(self, intent: Dict[str, Any], user_query: str) -> Dict[str, Any]:
        """
        Enrich intent with smart defaults and normalizations.
        """
        
        # Normalize skill names using aliases
        if "skills_required" in intent.get("filters", {}):
            normalized = []
            for skill in intent["filters"]["skills_required"]:
                normalized.append(self._normalize_skill(skill))
            intent["filters"]["skills_required"] = normalized
        
        if "skills_excluded" in intent.get("filters", {}):
            normalized = []
            for skill in intent["filters"]["skills_excluded"]:
                normalized.append(self._normalize_skill(skill))
            intent["filters"]["skills_excluded"] = normalized
        
        # Smart defaults
        if intent.get("query_type") == "list" and not intent.get("limit"):
            intent["limit"] = 10
        
        # Infer experience ranges for "senior" / "junior"
        query_lower = user_query.lower()
        if "senior" in query_lower and not intent.get("filters", {}).get("min_experience"):
            intent.setdefault("filters", {})["min_experience"] = 5
        elif "junior" in query_lower and not intent.get("filters", {}).get("max_experience"):
            intent.setdefault("filters", {})["max_experience"] = 3
        
        return intent

    def _normalize_skill(self, skill: str) -> str:
        """
        Normalize skill name using aliases.
        """
        skill_lower = skill.lower().strip()
        
        # Check if it's an alias
        for canonical, aliases in self.SKILL_ALIASES.items():
            if skill_lower == canonical or skill_lower in aliases:
                return canonical.title()
        
        return skill.title()
    
    from collections.abc import Mapping

    def _filters_to_dict(self, filters: Any) -> Dict[str, Any]:
        """Accept dict or list[{'field':..,'value':..}] and return a dict."""
        if not filters:
            return {}
        if isinstance(filters, Mapping):
            return dict(filters)
        if isinstance(filters, list):
            out: Dict[str, Any] = {}
            for f in filters:
                if isinstance(f, Mapping):
                    field = f.get("field")
                    value = f.get("value")
                    if field:
                        out[field] = value
            return out
        return {}

    def _fetch_candidates(self, intent: Dict[str, Any]) -> Tuple[List[Candidate], Optional[str]]:
        """
        Advanced candidate fetching with optimized SQL queries.
        Returns (candidates, suggestion_message) where suggestion_message is None if exact match found.
        """
        query = Candidate.query
        filters = self._filters_to_dict(intent.get("filters"))
        suggestion = None

        # ✅ IMPROVED: Name filter with fuzzy matching - check multiple filter keys
        name_filter = filters.get("name_filter") or filters.get("name") or filters.get("candidate_name")
        
        if name_filter:
            # Try exact match first (case-insensitive)
            exact_query = Candidate.query.filter(Candidate.full_name.ilike(f"%{name_filter}%"))
            exact_matches = exact_query.all()
            
            if exact_matches:
                query = exact_query
            else:
                # Try email matching (check if name_filter could be part of an email)
                email_query = Candidate.query.filter(Candidate.email.ilike(f"%{name_filter}%"))
                email_matches = email_query.all()
                
                if email_matches:
                    query = email_query
                    # Suggest the actual name in a natural way
                    if len(email_matches) == 1:
                        actual_name = email_matches[0].full_name
                        email_addr = email_matches[0].email
                        suggestion = f"I couldn't find a candidate named '{name_filter}', but I found a match by email address. The candidate with email '{email_addr}' is **{actual_name}**."
                else:
                    # Fuzzy match: try partial name
                    name_parts = name_filter.split()
                    if name_parts:
                        # Search for any part of the name
                        name_conditions = []
                        for part in name_parts:
                            if len(part) > 2:  # Ignore very short parts
                                name_conditions.append(Candidate.full_name.ilike(f"%{part}%"))
                        
                        if name_conditions:
                            fuzzy_query = Candidate.query.filter(or_(*name_conditions))
                            fuzzy_matches = fuzzy_query.all()
                            
                            if fuzzy_matches:
                                query = fuzzy_query
                                # Suggest closest match
                                if len(fuzzy_matches) == 1:
                                    suggestion = f"I couldn't find an exact match for '{name_filter}', but I found **{fuzzy_matches[0].full_name}** which might be who you're looking for."
                                elif len(fuzzy_matches) <= 3:
                                    names = [c.full_name for c in fuzzy_matches]
                                    suggestion = f"I couldn't find an exact match for '{name_filter}'. Did you mean one of these: {', '.join(f'**{n}**' for n in names)}?"
                            else:
                                # Last resort: search in email (even if no @ in name_filter)
                                # This handles "Merril" matching emails like "merril.almeida@..."
                                email_part_query = Candidate.query.filter(Candidate.email.ilike(f"%{name_filter.lower()}%"))
                                email_part_matches = email_part_query.all()
                                if email_part_matches:
                                    query = email_part_query
                                    if len(email_part_matches) == 1:
                                        suggestion = f"I couldn't find a candidate named '{name_filter}', but I found **{email_part_matches[0].full_name}** with email '{email_part_matches[0].email}'."
                                    else:
                                        names = [f"{c.full_name} ({c.email})" for c in email_part_matches[:3]]
                                        suggestion = f"I couldn't find an exact match. Here are some candidates with similar email addresses: {', '.join(f'**{n}**' for n in names)}"
        
        # Candidate ID filter (for context tracking)
        candidate_id = filters.get("candidate_id")
        if candidate_id:
            query = query.filter(Candidate.id == candidate_id)
        
        # Role bucket filter
        role_bucket = filters.get("role_bucket")
        if role_bucket and role_bucket != "both":
            query = query.filter(Candidate.role_bucket == role_bucket)
        
        # Experience range filters
        min_exp = filters.get("min_experience")
        max_exp = filters.get("max_experience")
        
        if min_exp is not None:
            query = query.filter(Candidate.total_experience_years >= min_exp)
        if max_exp is not None:
            query = query.filter(Candidate.total_experience_years <= max_exp)
        
        # Job title / primary role filter
        job_title = filters.get("job_title") or filters.get("primary_role")
        if job_title:
            query = query.filter(Candidate.primary_role.ilike(f"%{job_title}%"))

        # Keyword search (name, role, email)
        keyword = filters.get("keyword")
        if keyword:
            query = query.filter(
                or_(
                    Candidate.full_name.ilike(f"%{keyword}%"),
                    Candidate.primary_role.ilike(f"%{keyword}%"),
                    Candidate.email.ilike(f"%{keyword}%")
                )
            )
        
        # Certification filter - DON'T filter at SQL level, we'll search all candidates in Python
        # This ensures we don't miss any matches due to variations in how certs are stored
        certification_name = filters.get("certification_name")
        if certification_name:
            # We'll handle certification matching in Python after fetching candidates
            # This allows for more flexible matching (variations, word order, etc.)
            print(f"   ✅ Will search for certification: {certification_name} (searching all candidates)")
        
        # Skills filters (required AND excluded)
        skills_required = filters.get("skills_required", [])
        skills_excluded = filters.get("skills_excluded", [])
        
        if skills_required or skills_excluded:
            # Build skill conditions
            for skill in skills_required:
                # Check all aliases
                aliases = self.SKILL_ALIASES.get(skill.lower(), [skill])
                skill_conditions = []
                
                for alias in [skill] + aliases:
                    skill_conditions.append(cast(Candidate.parsed, String).ilike(f"%{alias}%"))
                    skill_conditions.append(Candidate.raw_text.ilike(f"%{alias}%"))
                
                query = query.filter(or_(*skill_conditions))
            
            for skill in skills_excluded:
                # Exclude candidates with this skill
                aliases = self.SKILL_ALIASES.get(skill.lower(), [skill])
                exclude_conditions = []
                
                for alias in [skill] + aliases:
                    exclude_conditions.append(cast(Candidate.parsed, String).ilike(f"%{alias}%"))
                    exclude_conditions.append(Candidate.raw_text.ilike(f"%{alias}%"))
                
                query = query.filter(~or_(*exclude_conditions))
        
        # Sorting
        sort_by = intent.get("sort_by")
        sort_order = intent.get("sort_order", "desc")
        
        if sort_by == "experience":
            order_col = Candidate.total_experience_years.desc() if sort_order == "desc" else Candidate.total_experience_years.asc()
            query = query.order_by(order_col)
        elif sort_by == "name":
            order_col = Candidate.full_name.asc() if sort_order == "asc" else Candidate.full_name.desc()
            query = query.order_by(order_col)
        elif sort_by == "recent":
            query = query.order_by(Candidate.created_at.desc())
        else:
            # Default: most recent first
            query = query.order_by(Candidate.created_at.desc())
        
        # ✅ FIX: Handle None limit
        limit = intent.get("limit", 10)
        if limit is None:
            limit = 10
        limit = min(limit, 50)  # Cap at 50
        
        if limit:
            query = query.limit(limit)
        
        # ✅ Execute query
        results = query.all()
        
        # ✅ SMART FALLBACK: If no results and we have filters (but NOT certification - that's handled separately)
        if not results and filters and not filters.get("certification_name"):
            print(f"⚠️ No candidates matched filters {filters}, returning recent candidates as fallback")
            results = Candidate.query.order_by(Candidate.created_at.desc()).limit(5).all()
            if not suggestion:
                suggestion = f"I couldn't find any candidates matching '{name_filter}'. Here are some recent candidates instead."
        
        return results, suggestion

    def _generate_response(self, user_query: str, intent: Dict, candidates: List[Candidate], context: Optional[List[Dict]] = None, suggestion: Optional[str] = None) -> Dict[str, Any]:
        """Generate intelligent, context-aware responses with smart table formatting."""
        
        query_type = intent.get("query_type", "list")
        aggregation = intent.get("aggregation")
        
        print(f"🎨 Generating response for query_type={query_type}, aggregation={aggregation}, candidates={len(candidates)}")
        
        # ✅ ALWAYS HANDLE CANDIDATES - Never return "couldn't process"
        if not candidates:
            return self._handle_no_results(intent)
        
        # Extract candidate data first
        candidate_rows = self._extract_candidate_rows(candidates)
        
        # Handle certification queries first - ALWAYS search ALL candidates for maximum accuracy
        query_lower = user_query.lower()
        if any(kw in query_lower for kw in ['certification', 'certificate', 'certified', 'has completed', 'completed']):
            # For certification queries, ALWAYS search ALL candidates to ensure we don't miss any
            # This is critical for accuracy - certifications might be stored in various formats
            from models import Candidate as CandidateModel
            all_candidates = CandidateModel.query.all()
            all_candidate_rows = self._extract_candidate_rows(all_candidates)
            print(f"🔍 Certification query: Searching ALL {len(all_candidate_rows)} candidates")
            return self._format_certification_response(all_candidate_rows, user_query, intent, suggestion)
        
        # Handle aggregation queries
        if aggregation == "count":
            return self._handle_count_query(user_query, intent, candidates)
        elif aggregation in ["average", "avg", "mean"]:
            return self._handle_average_query(user_query, intent, candidates)
        
        # ✅ CHECK FOR SPECIFIC ATTRIBUTE QUERIES (check query text, not just query_type)
        
        # Skills query - HIGHEST PRIORITY (but use table if multiple candidates)
        if any(keyword in query_lower for keyword in ['skill', 'skills', 'technical', 'technologies', 'tech stack', 'expertise', 'proficienc']):
            if len(candidate_rows) > 1:
                # Multiple candidates - use table format
                return self._format_skills_table_response(candidate_rows, user_query, intent, suggestion)
            return self._format_skills_response(candidate_rows, user_query, intent, suggestion)
        
        # Projects query - use table if multiple
        if any(keyword in query_lower for keyword in ['project', 'projects', 'experience on', 'worked on']):
            if len(candidate_rows) > 1:
                return self._format_projects_table_response(candidate_rows, user_query, intent)
            return self._format_projects_response(candidate_rows, user_query, intent)
        
        # Experience query - use table if multiple
        if any(keyword in query_lower for keyword in ['experience', 'years', 'work history', 'how long', 'tenure']):
            if len(candidate_rows) > 1:
                return self._format_experience_table_response(candidate_rows, user_query, intent)
            return self._format_experience_response(candidate_rows, user_query, intent)
        
        # Email/Contact query - use table if multiple
        if any(keyword in query_lower for keyword in ['email', 'contact', 'phone', 'reach', 'contact info']):
            if len(candidate_rows) > 1:
                return self._format_contact_table_response(candidate_rows, user_query, intent)
            return self._format_contact_response(candidate_rows, user_query, intent)
        
        # Role query - use table if multiple
        if any(keyword in query_lower for keyword in ['role', 'position', 'job title', 'what does', 'who is']):
            if len(candidate_rows) > 1:
                return self._format_role_table_response(candidate_rows, user_query, intent)
            return self._format_role_response(candidate_rows, user_query, intent)
        
        # ✅ DEFAULT: Use table format for multiple candidates, detailed text for single
        if len(candidate_rows) == 1:
            c = candidate_rows[0]
            summary = self._generate_smart_summary(user_query, intent, candidate_rows, context, suggestion)
            
            # Still return as table for consistency, but with single row
            return {
                "type": "candidate_table",
                "message": summary,
                "data": {
                    "headers": ["Name", "Email", "Role", "Experience", "Bucket", "Skills", "On Bench"],
                    "rows": [{
                        "cells": [
                            c['name'],
                            c['email'],
                            c['role'],
                            f"{c['experience']} yrs",
                            c['bucket'],
                            ', '.join(c['skills'][:5]) if c['skills'] else 'N/A',
                            'Yes' if c.get('on_bench') else 'No'
                        ]
                    }],
                    "candidate": c,
                    "total": 1,
                    "suggestion": suggestion
                }
            }
        else:
            # Multiple candidates - ALWAYS use table format
            summary = self._generate_smart_summary(user_query, intent, candidate_rows, context, suggestion)
            insights = self._generate_insights(candidate_rows, intent)
            
            # Format as proper table with headers
            table_rows = []
            for c in candidate_rows:
                table_rows.append({
                    "cells": [
                        c['name'],
                        c['email'],
                        c['role'],
                        f"{c['experience']} yrs",
                        c['bucket'],
                        ', '.join(c['skills'][:5]) if c['skills'] else 'N/A',
                        'Yes' if c.get('on_bench') else 'No'
                    ]
                })
            
            return {
                "type": "candidate_table",
                "message": summary,
                "data": {
                    "headers": ["Name", "Email", "Role", "Experience", "Bucket", "Top Skills", "On Bench"],
                    "rows": table_rows,
                    "total": len(candidate_rows),
                    "filters": intent.get("filters", {}),
                    "insights": insights,
                    "suggestion": suggestion
                }
            }

    def _format_skills_response(self, candidates: List[Dict], user_query: str, intent: Dict, suggestion: Optional[str] = None) -> Dict[str, Any]:
        """Format skills in a beautiful, natural response."""
        
        if len(candidates) == 1:
            candidate = candidates[0]
            skills = candidate.get('skills', [])
            
            # Build natural message
            message_parts = []
            if suggestion:
                message_parts.append(suggestion)
                message_parts.append("")
            
            if not skills:
                message_parts.append(f"I couldn't find any technical skills listed for {candidate['name']}. This might mean their resume needs to be re-parsed, or skills weren't extracted during the initial processing.")
                return {
                    "type": "text",
                    "message": "\n".join(message_parts),
                    "data": {"candidate": candidate}
                }
            
            # Categorize skills
            programming = []
            frameworks = []
            databases = []
            cloud = []
            other = []
            
            programming_keywords = ['python', 'java', 'javascript', 'typescript', 'go', 'rust', 'c++', 'c#', 'ruby', 'php', 'r', 'scala', 'kotlin', 'sql']
            framework_keywords = ['react', 'vue', 'angular', 'django', 'flask', 'spring', 'express', 'fastapi', 'nodejs', 'nextjs', 'laravel', 'spark', 'pyspark']
            database_keywords = ['mysql', 'postgresql', 'mongodb', 'redis', 'cassandra', 'dynamodb', 'oracle', 'sqlite', 'elasticsearch', 'ms sql', 'sql server']
            cloud_keywords = ['aws', 'azure', 'gcp', 'docker', 'kubernetes', 'terraform', 'jenkins', 'ci/cd', 'devops']
            
            for skill in skills:
                skill_lower = skill.lower()
                categorized = False
                
                if any(kw in skill_lower for kw in programming_keywords):
                    programming.append(skill)
                    categorized = True
                if any(kw in skill_lower for kw in framework_keywords):
                    frameworks.append(skill)
                    categorized = True
                if any(kw in skill_lower for kw in database_keywords):
                    databases.append(skill)
                    categorized = True
                if any(kw in skill_lower for kw in cloud_keywords):
                    cloud.append(skill)
                    categorized = True
                
                if not categorized:
                    other.append(skill)
            
            # Generate natural message about skills
            if suggestion:
                skills_message_parts = [suggestion, ""]
            else:
                skills_message_parts = []
            
            # More natural phrasing
            if len(skills) <= 5:
                skills_message_parts.append(f"{candidate['name']} has experience with: {', '.join(skills)}.")
            else:
                skills_message_parts.append(f"{candidate['name']} has experience with the following skills:")
                
                if programming:
                    skills_message_parts.append(f"\n**Programming Languages:** {', '.join(programming)}")
                if frameworks:
                    skills_message_parts.append(f"\n**Frameworks & Libraries:** {', '.join(frameworks)}")
                if databases:
                    skills_message_parts.append(f"\n**Databases:** {', '.join(databases)}")
                if cloud:
                    skills_message_parts.append(f"\n**Cloud & DevOps:** {', '.join(cloud)}")
                if other:
                    skills_message_parts.append(f"\n**Other Skills:** {', '.join(other)}")
            
            skills_message = "\n".join(skills_message_parts)
            
            # ✅ Return with proper structure for frontend detection
            return {
                "type": "skills_display",
                "message": skills_message,
                "data": {
                    "candidate": candidate,
                    "skills_by_category": {
                        "Programming Languages": programming,
                        "Frameworks & Libraries": frameworks,
                        "Databases": databases,
                        "Cloud & DevOps": cloud,
                        "Other Skills": other
                    },
                    "total_skills": len(skills)
                }
            }
        
        else:
            # Multiple candidates - skills comparison
            message = f"**Skills Overview for {len(candidates)} Candidates**\n\n"
            
            for c in candidates[:5]:  # Top 5
                skills_preview = ', '.join(c['skills'][:5]) if c['skills'] else 'No skills listed'
                message += f"• **{c['name']}** ({c['experience']} yrs): {skills_preview}\n"
            
            return {
                "type": "text",
                "message": message.strip(),
                "data": {
                    "candidates": candidates,
                    "total": len(candidates)
                }
            }
    
    def _format_skills_table_response(self, candidates: List[Dict], user_query: str, intent: Dict, suggestion: Optional[str] = None) -> Dict[str, Any]:
        """Format skills as table for multiple candidates."""
        if suggestion:
            summary = f"{suggestion}\n\nHere are the technical skills for {len(candidates)} candidate(s):"
        else:
            summary = f"Here are the technical skills for {len(candidates)} candidate(s):"
        
        rows = []
        for c in candidates:
            skills_str = ', '.join(c['skills'][:8]) if c['skills'] else 'No skills listed'
            rows.append({
                "cells": [
                    c['name'],
                    skills_str,
                    f"{c.get('experience', 0)} yrs",
                    c.get('role', 'N/A')
                ]
            })
        
        return {
            "type": "candidate_table",
            "message": summary,
            "data": {
                "headers": ["Name", "Skills", "Experience", "Role"],
                "rows": rows,
                "total": len(candidates),
                "suggestion": suggestion
            }
        }

    def _format_contact_response(self, candidates: List[Dict], user_query: str, intent: Dict) -> Dict[str, Any]:
        """Format contact information."""
        
        if len(candidates) == 1:
            candidate = candidates[0]
            email = candidate.get('email', 'Not available')
            phone = candidate.get('phone', 'Not available')
            
            message = f"**{candidate['name']}'s Contact Information**\n\n"
            message += f"📧 Email: {email}\n"
            message += f"📱 Phone: {phone}"
            
            return {
                "type": "text",
                "message": message,
                "data": {"candidate": candidate}
            }
        else:
            message = f"**Contact Information for {len(candidates)} Candidates**\n\n"
            for c in candidates[:10]:
                email = c.get('email', 'N/A')
                message += f"• **{c['name']}**: {email}\n"
            
            return {
                "type": "text",
                "message": message.strip(),
                "data": {"candidates": candidates}
            }
    
    def _format_contact_table_response(self, candidates: List[Dict], user_query: str, intent: Dict) -> Dict[str, Any]:
        """Format contact information as table."""
        summary = f"Contact information for {len(candidates)} candidates"
        rows = []
        for c in candidates:
            rows.append({
                "cells": [
                    c['name'],
                    c.get('email', 'N/A'),
                    c.get('phone', 'N/A'),
                    c.get('role', 'N/A')
                ]
            })
        
        return {
            "type": "candidate_table",
            "message": summary,
            "data": {
                "headers": ["Name", "Email", "Phone", "Role"],
                "rows": rows,
                "total": len(candidates)
            }
        }


    def _format_role_response(self, candidates: List[Dict], user_query: str, intent: Dict) -> Dict[str, Any]:
        """Format role information."""
        
        if len(candidates) == 1:
            candidate = candidates[0]
            role = candidate.get('role', 'Not specified')
            experience = candidate.get('experience', 0)
            bucket = candidate.get('bucket', 'Unknown')
            
            message = f"**{candidate['name']}**\n\n"
            message += f"👤 Role: {role}\n"
            message += f"💼 Experience: {experience} years\n"
            message += f"🎯 Bucket: {bucket}"
            
            return {
                "type": "text",
                "message": message,
                "data": {"candidate": candidate}
            }
        else:
            message = f"**Roles for {len(candidates)} Candidates**\n\n"
            for c in candidates[:10]:
                message += f"• **{c['name']}**: {c.get('role', 'N/A')} ({c.get('experience', 0)} yrs)\n"
            
            return {
                "type": "text",
                "message": message.strip(),
                "data": {"candidates": candidates}
            }
    
    def _format_role_table_response(self, candidates: List[Dict], user_query: str, intent: Dict) -> Dict[str, Any]:
        """Format role information as table."""
        summary = f"Roles for {len(candidates)} candidates"
        rows = []
        for c in candidates:
            rows.append({
                "cells": [
                    c['name'],
                    c.get('role', 'N/A'),
                    f"{c.get('experience', 0)} yrs",
                    c.get('bucket', 'N/A')
                ]
            })
        
        return {
            "type": "candidate_table",
            "message": summary,
            "data": {
                "headers": ["Name", "Role", "Experience", "Bucket"],
                "rows": rows,
                "total": len(candidates)
            }
        }


    def _format_experience_response(self, candidates: List[Dict], user_query: str, intent: Dict) -> Dict[str, Any]:
        """Format experience information."""
        
        if len(candidates) == 1:
            candidate = candidates[0]
            experience = candidate.get('experience', 0)
            role = candidate.get('role', 'Not specified')
            
            message = f"**{candidate['name']}'s Experience**\n\n"
            message += f"📊 Total Experience: {experience} years\n"
            message += f"👤 Current Role: {role}"
            
            return {
                "type": "text",
                "message": message,
                "data": {"candidate": candidate}
            }
        else:
            message = f"**Experience Overview for {len(candidates)} Candidates**\n\n"
            
            # Sort by experience
            sorted_candidates = sorted(candidates, key=lambda x: x.get('experience', 0), reverse=True)
            
            for c in sorted_candidates[:10]:
                message += f"• **{c['name']}**: {c.get('experience', 0)} years as {c.get('role', 'N/A')}\n"
            
            avg_exp = sum(c.get('experience', 0) for c in candidates) / len(candidates) if candidates else 0
            message += f"\n📈 Average Experience: {avg_exp:.1f} years"
            
            return {
                "type": "text",
                "message": message.strip(),
                "data": {
                    "candidates": candidates,
                    "avg_experience": avg_exp
                }
            }
    
    def _format_experience_table_response(self, candidates: List[Dict], user_query: str, intent: Dict) -> Dict[str, Any]:
        """Format experience information as table."""
        # Sort by experience
        sorted_candidates = sorted(candidates, key=lambda x: x.get('experience', 0), reverse=True)
        avg_exp = sum(c.get('experience', 0) for c in candidates) / len(candidates) if candidates else 0
        
        summary = f"Experience overview for {len(candidates)} candidates (Average: {avg_exp:.1f} years)"
        rows = []
        for c in sorted_candidates:
            rows.append({
                "cells": [
                    c['name'],
                    f"{c.get('experience', 0)} yrs",
                    c.get('role', 'N/A'),
                    c.get('bucket', 'N/A')
                ]
            })
        
        return {
            "type": "candidate_table",
            "message": summary,
            "data": {
                "headers": ["Name", "Experience", "Role", "Bucket"],
                "rows": rows,
                "total": len(candidates),
                "avg_experience": round(avg_exp, 1)
            }
        }


    def _format_projects_response(self, candidates: List[Dict], user_query: str, intent: Dict) -> Dict[str, Any]:
        """Format projects information."""
        
        if len(candidates) == 1:
            candidate = candidates[0]
            
            # Get projects from database
            from models import Candidate as CandidateModel
            db_candidate = CandidateModel.query.get(candidate['id'])
            
            if not db_candidate or not db_candidate.parsed:
                return {
                    "type": "text",
                    "message": f"**{candidate['name']}**\n\nNo project information available.",
                    "data": {"candidate": candidate}
                }
            
            projects = db_candidate.parsed.get('projects', [])
            
            if not projects:
                return {
                    "type": "text",
                    "message": f"**{candidate['name']}**\n\nNo projects found in resume.",
                    "data": {"candidate": candidate}
                }
            
            message = f"**{candidate['name']}'s Projects** ({len(projects)} total)\n\n"
            
            for i, proj in enumerate(projects[:5], 1):  # Top 5 projects
                proj_name = proj.get('project_name', f'Project {i}')
                role = proj.get('role', 'N/A')
                duration = proj.get('duration', 'N/A')
                technologies = proj.get('technologies', [])
                
                message += f"**{i}. {proj_name}**\n"
                message += f"   Role: {role}\n"
                message += f"   Duration: {duration}\n"
                if technologies:
                    message += f"   Tech: {', '.join(technologies[:8])}\n"
                message += "\n"
            
            return {
                "type": "text",
                "message": message.strip(),
                "data": {
                    "candidate": candidate,
                    "projects": projects,
                    "total_projects": len(projects)
                }
            }
        else:
            message = f"**Projects for {len(candidates)} Candidates**\n\n"
            message += "Use 'show projects of [candidate name]' to see details."
            
            return {
                "type": "text",
                "message": message,
                "data": {"candidates": candidates}
            }
    
    def _normalize_cert_name(self, cert_name: str) -> str:
        """Normalize certification name for better matching."""
        if not cert_name:
            return ""
        # Remove extra spaces, convert to lowercase, remove special chars for comparison
        normalized = " ".join(cert_name.lower().split())
        # Remove common words
        normalized = re.sub(r'\b(the|a|an|certification|certificate|certified)\b', '', normalized, flags=re.IGNORECASE)
        return " ".join(normalized.split())
    
    def _cert_name_matches(self, search_cert: str, candidate_cert: str) -> bool:
        """Intelligent certification name matching with variations."""
        if not search_cert or not candidate_cert:
            return False
        
        search_normalized = self._normalize_cert_name(search_cert)
        candidate_normalized = self._normalize_cert_name(candidate_cert)
        
        # Exact match after normalization
        if search_normalized == candidate_normalized:
            return True
        
        # Remove spaces for acronym matching (e.g., "Tensor Flow" vs "TensorFlow")
        search_no_spaces = search_normalized.replace(" ", "")
        candidate_no_spaces = candidate_normalized.replace(" ", "")
        if search_no_spaces == candidate_no_spaces:
            return True
        # Word-based matching - all significant words from search must be in candidate
        search_words = [w for w in search_normalized.split() if len(w) > 2]
        if search_words and all(word in candidate_normalized for word in search_words):
            return True

        # Substring matching for short tokens (acronyms/brands) but with word boundaries.
        # This prevents false positives like matching "azure" just because it appears in unrelated raw text.
        if len(search_normalized) <= 10:
            try:
                pattern = rf"\b{re.escape(search_normalized)}\b"
                if re.search(pattern, candidate_normalized, re.IGNORECASE):
                    return True
            except Exception:
                # Fallback: do not match on error
                pass

        return False
    
    def _format_certification_response(self, candidates: List[Dict], user_query: str, intent: Dict, suggestion: Optional[str] = None) -> Dict[str, Any]:
        """Format certification queries with natural responses and intelligent matching."""
        from models import Candidate as CandidateModel
        import re
        
        query_lower = user_query.lower()
        is_count_query = any(kw in query_lower for kw in ['how many', 'count', 'number of', 'total'])
        cert_name = intent.get("filters", {}).get("certification_name", "").strip()
        cert_name_lower = cert_name.lower() if cert_name else ""
        
        print(f"🔍 Searching for certification: '{cert_name}' in {len(candidates)} candidates")
        
        # Extract certifications from candidates with improved matching
        cert_data = []
        for c in candidates:
            db_candidate = CandidateModel.query.get(c['id'])
            if not db_candidate:
                continue
                
            # Check multiple sources for certifications
            certs = []
            parsed = db_candidate.parsed or {}
            
            # Source 1: parsed.certifications
            if parsed.get("certifications"):
                certs_list = parsed["certifications"] if isinstance(parsed["certifications"], list) else [parsed["certifications"]]
                certs.extend(certs_list)
            
            # Source 2: parsed.certificate
            if parsed.get("certificate"):
                cert_list = parsed["certificate"] if isinstance(parsed["certificate"], list) else [parsed["certificate"]]
                certs.extend(cert_list)
            
            # Source 3: Candidate.certifications field (if exists)
            if hasattr(db_candidate, 'certifications') and db_candidate.certifications:
                if isinstance(db_candidate.certifications, list):
                    certs.extend(db_candidate.certifications)
                else:
                    certs.append(db_candidate.certifications)
            
            # If we're looking for a specific cert, filter with intelligent matching
            if cert_name:
                matching_certs = []
                
                for cert in certs:
                    is_match = False
                    
                    if isinstance(cert, dict):
                        cert_name_str = str(cert.get("name", ""))
                        cert_issuer = str(cert.get("issuer", ""))
                        cert_org = str(cert.get("organization", ""))
                        
                        # Check all fields for matches
                        if (self._cert_name_matches(cert_name, cert_name_str) or
                            self._cert_name_matches(cert_name, cert_issuer) or
                            self._cert_name_matches(cert_name, cert_org)):
                            is_match = True
                    elif isinstance(cert, str):
                        if self._cert_name_matches(cert_name, cert):
                            is_match = True
                    
                    if is_match:
                        if isinstance(cert, str):
                            matching_certs.append({"name": cert})
                        else:
                            matching_certs.append(cert)
                
                if matching_certs:
                    cert_data.append({
                        "name": c['name'],
                        "email": c.get('email', 'N/A'),
                        "certifications": matching_certs,
                        "total_certs": len(matching_certs)
                    })
            else:
                # All certifications
                if certs:
                    cert_data.append({
                        "name": c['name'],
                        "email": c.get('email', 'N/A'),
                        "certifications": certs,
                        "total_certs": len(certs)
                    })
        
        # Handle no results - provide helpful feedback
        if not cert_data:
            if cert_name:
                # Try to suggest similar certifications or variations
                message = f"I searched through all {len(candidates)} candidates in the database but couldn't find anyone with the '{cert_name}' certification."
                message += "\n\nThis could mean:"
                message += "\n• The certification might be stored under a different name (e.g., 'TensorFlow' vs 'Tensor Flow')"
                message += "\n• No candidates in the database have this certification"
                message += "\n• The certification information might not have been extracted from resumes"
                message += f"\n\nTry searching for variations like: '{cert_name.replace(' ', '')}' or individual keywords from the certification name."
            else:
                message = f"I searched through all {len(candidates)} candidates but found no certification information in the database."
            
            if suggestion:
                message = f"{suggestion}\n\n{message}"
            
            return {
                "type": "text",
                "message": message,
                "data": {
                    "total": 0,
                    "certification_name": cert_name,
                    "candidates_searched": len(candidates)
                }
            }
        
        # Count query
        if is_count_query:
            count = len(cert_data)
            if cert_name:
                message = f"{count} candidate(s) {'have' if count != 1 else 'has'} completed the {cert_name} certification."
            else:
                message = f"{count} candidate(s) {'have' if count != 1 else 'has'} certifications in the database."
            
            if suggestion:
                message = f"{suggestion}\n\n{message}"
            
            # Build table with details
            rows = []
            for item in cert_data:
                cert_names = []
                for cert in item['certifications']:
                    if isinstance(cert, dict):
                        cert_name_str = cert.get("name", "Unknown")
                        cert_org = cert.get("organization") or cert.get("issuer", "")
                        if cert_org:
                            cert_names.append(f"{cert_name_str} ({cert_org})")
                        else:
                            cert_names.append(cert_name_str)
                    else:
                        cert_names.append(str(cert))
                
                rows.append({
                    "cells": [
                        item['name'],
                        item['email'],
                        ', '.join(cert_names[:5]) if cert_names else 'N/A',
                        f"{item['total_certs']} cert(s)"
                    ]
                })
            
            response_data = {
                "type": "candidate_table",
                "message": message,
                "data": {
                    "headers": ["Name", "Email", "Certifications", "Count"],
                    "rows": rows,
                    "total": count,
                    "certification_name": cert_name,
                    "candidates_searched": len(candidates)
                }
            }
            print(f"✅ Found {count} candidate(s) with {cert_name} certification")
            return response_data
        
        # List query - show all certifications
        if cert_name:
            message = f"Here are the candidates who have completed the {cert_name} certification:"
        else:
            message = f"Here are candidates with certifications:"
        
        if suggestion:
            message = f"{suggestion}\n\n{message}"
        
        rows = []
        for item in cert_data:
            cert_names = []
            for cert in item['certifications']:
                if isinstance(cert, dict):
                    cert_name_str = cert.get("name", "Unknown")
                    cert_org = cert.get("organization") or cert.get("issuer", "")
                    if cert_org:
                        cert_names.append(f"{cert_name_str} ({cert_org})")
                    else:
                        cert_names.append(cert_name_str)
                else:
                    cert_names.append(str(cert))
            
            rows.append({
                "cells": [
                    item['name'],
                    item['email'],
                    ', '.join(cert_names[:5]) if cert_names else 'N/A',
                    f"{item['total_certs']} cert(s)"
                ]
            })
        
        response_data = {
            "type": "candidate_table",
            "message": message,
            "data": {
                "headers": ["Name", "Email", "Certifications", "Count"],
                "rows": rows,
                "total": len(cert_data),
                "certification_name": cert_name,
                "candidates_searched": len(candidates)
            }
        }
        print(f"✅ Found {len(cert_data)} candidate(s) with certifications")
        return response_data
    
    def _format_projects_table_response(self, candidates: List[Dict], user_query: str, intent: Dict) -> Dict[str, Any]:
        """Format projects as table for multiple candidates."""
        from models import Candidate as CandidateModel
        
        summary = f"Projects for {len(candidates)} candidates"
        rows = []
        
        for c in candidates:
            db_candidate = CandidateModel.query.get(c['id'])
            project_count = 0
            project_preview = "No projects"
            
            if db_candidate and db_candidate.parsed:
                projects = db_candidate.parsed.get('projects', [])
                project_count = len(projects)
                if projects:
                    project_names = [p.get('name', 'Unknown')[:30] for p in projects[:3]]
                    project_preview = f"{project_count} projects: {', '.join(project_names)}"
            
            rows.append({
                "cells": [
                    c['name'],
                    project_preview,
                    f"{c.get('experience', 0)} yrs",
                    c.get('role', 'N/A')
                ]
            })
        
        return {
            "type": "candidate_table",
            "message": summary,
            "data": {
                "headers": ["Name", "Projects", "Experience", "Role"],
                "rows": rows,
                "total": len(candidates)
            }
        }


        def _extract_candidate_rows(self, candidates: List[Candidate]) -> List[Dict[str, Any]]:
            """
            Enhanced candidate data extraction with better skill parsing.
            """
            
            rows = []
            
            for c in candidates:
                parsed = c.parsed or {}
                
                # Multi-source skill extraction
                skills = self._extract_skills_advanced(c, parsed)
                
                rows.append({
                    "id": c.id,
                    "name": c.full_name or parsed.get("candidate_name", "Unknown"),
                    "role": c.primary_role or parsed.get("primary_role", "—"),
                    "bucket": c.role_bucket or "data_practice",
                    "experience": c.total_experience_years or parsed.get("total_experience_years", 0),
                    "skills": skills[:15],  # Top 15 skills
                    "email": c.email or parsed.get("email", "—"),
                    "phone": c.phone or parsed.get("phone", "—"),
                    "created_at": c.created_at.isoformat() if c.created_at else None
                })
            
            return rows
    
    def _extract_skills_advanced(self, candidate: Candidate, parsed: Dict) -> List[str]:
        """
        Advanced skill extraction with deduplication and prioritization.
        """
        
        skills_map = {}  # skill_lower -> original_case
        
        # Priority 1: primary_skills
        primary_skills = parsed.get("primary_skills") or []
        if isinstance(primary_skills, list):
            for skill in primary_skills:
                if skill:
                    skills_map[str(skill).lower().strip()] = str(skill).strip()
        
        # Priority 2: technical_skills
        technical_skills = parsed.get("technical_skills") or []
        if isinstance(technical_skills, list):
            for skill in technical_skills:
                if skill:
                    skill_str = str(skill).strip()
                    skills_map.setdefault(skill_str.lower(), skill_str)
        
        # Priority 3: skill_categories (hierarchical)
        skill_categories = parsed.get("skill_categories") or []
        if isinstance(skill_categories, list):
            for cat in skill_categories:
                if isinstance(cat, dict):
                    cat_skills = cat.get("skills") or []
                    if isinstance(cat_skills, list):
                        for skill in cat_skills:
                            if skill:
                                skill_str = str(skill).strip()
                                skills_map.setdefault(skill_str.lower(), skill_str)
        
        # Priority 4: skills array
        skills = parsed.get("skills") or []
        if isinstance(skills, list):
            for skill in skills:
                if skill:
                    skill_str = str(skill).strip()
                    skills_map.setdefault(skill_str.lower(), skill_str)
        
        # Priority 5: Extract from raw text (last resort)
        if not skills_map and candidate.raw_text:
            common_skills = [
                "Python", "SQL", "Java", "JavaScript", "React", "Node.js",
                "AWS", "Azure", "GCP", "Docker", "Kubernetes",
                "Spark", "Hadoop", "Kafka", "Airflow", "Databricks",
                "TensorFlow", "PyTorch", "Scikit-learn",
                "Pandas", "NumPy", "Matplotlib", "Tableau", "Power BI",
                "MongoDB", "PostgreSQL", "MySQL", "Redis",
                "Flask", "FastAPI", "Django", "Spring Boot"
            ]
            raw_lower = candidate.raw_text.lower()
            for skill in common_skills:
                if skill.lower() in raw_lower:
                    skills_map.setdefault(skill.lower(), skill)
        
        return list(skills_map.values())
    
    def _handle_count_query(self, user_query: str, intent: Dict, candidates: List[Candidate]) -> Dict[str, Any]:
        """Handle count queries with detailed breakdown."""
        
        count = len(candidates)
        filters_desc = self._describe_filters(intent.get("filters", {}))
        
        # Generate breakdown
        breakdown = {
            "total": count,
            "by_bucket": {
                "data_scientist": sum(1 for c in candidates if c.role_bucket == "data_scientist"),
                "data_practice": sum(1 for c in candidates if c.role_bucket == "data_practice")
            },
            "by_experience": {
                "junior": sum(1 for c in candidates if (c.total_experience_years or 0) < 3),
                "mid": sum(1 for c in candidates if 3 <= (c.total_experience_years or 0) < 7),
                "senior": sum(1 for c in candidates if (c.total_experience_years or 0) >= 7)
            }
        }
        
        message = f"Found **{count}** candidates{filters_desc}."
        
        if count > 0:
            ds_count = breakdown['by_bucket']['data_scientist']
            dp_count = breakdown['by_bucket']['data_practice']
            junior_count = breakdown['by_experience']['junior']
            mid_count = breakdown['by_experience']['mid']
            senior_count = breakdown['by_experience']['senior']
            
            # Build message without backslashes in f-string
            breakdown_text = "\n\n**Breakdown:**\n"
            breakdown_text += f"- Data Scientists: {ds_count}\n"
            breakdown_text += f"- Data Practice: {dp_count}\n"
            breakdown_text += "\n**By Experience:**\n"
            breakdown_text += f"- Junior (<3 yrs): {junior_count}\n"
            breakdown_text += f"- Mid (3-7 yrs): {mid_count}\n"
            breakdown_text += f"- Senior (7+ yrs): {senior_count}"
            
            message += breakdown_text
        
        return {
            "type": "text",
            "message": message,
            "data": {
                "count": count,
                "breakdown": breakdown,
                "filters": intent.get("filters", {})
            }
        }
    
    def _handle_average_query(self, user_query: str, intent: Dict, candidates: List[Candidate]) -> Dict[str, Any]:
        """Handle average/stats queries."""
        
        if not candidates:
            return {
                "type": "text",
                "message": "No candidates found matching your criteria.",
                "data": {}
            }
        
        experiences = [c.total_experience_years or 0 for c in candidates]
        avg_exp = sum(experiences) / len(experiences)
        max_exp = max(experiences)
        min_exp = min(experiences)
        
        filters_desc = self._describe_filters(intent.get("filters", {}))
        
        # Build message without backslashes in f-string
        message = f"**Statistics{filters_desc}:**\n\n"
        message += f"- Average experience: **{avg_exp:.1f} years**\n"
        message += f"- Range: {min_exp:.1f} - {max_exp:.1f} years\n"
        message += f"- Based on {len(candidates)} candidates"
        
        return {
            "type": "text",
            "message": message,
            "data": {
                "average": round(avg_exp, 1),
                "max": max_exp,
                "min": min_exp,
                "count": len(candidates),
                "filters": intent.get("filters", {})
            }
        }
    
    def _handle_grouped_query(self, user_query: str, intent: Dict, candidates: List[Candidate], group_by: str) -> Dict[str, Any]:
        """Handle grouped/aggregate queries."""
        
        if group_by == "bucket":
            groups = {}
            for c in candidates:
                bucket = c.role_bucket or "data_practice"
                if bucket not in groups:
                    groups[bucket] = []
                groups[bucket].append(c.total_experience_years or 0)
            
            message_parts = ["**Average experience by bucket:**", ""]
            for bucket, exps in groups.items():
                avg = sum(exps) / len(exps) if exps else 0
                label = "Data Scientists" if bucket == "data_scientist" else "Data Practice"
                message_parts.append(f"- {label}: {avg:.1f} years ({len(exps)} candidates)")
            
            message = "\n".join(message_parts)
            
            return {
                "type": "text",
                "message": message,
                "data": {
                    "groups": {
                        bucket: {
                            "average": round(sum(exps) / len(exps), 1) if exps else 0,
                            "count": len(exps)
                        }
                        for bucket, exps in groups.items()
                    }
                }
            }
        
        elif group_by == "experience_range":
            ranges = {
                "0-3 years": [],
                "3-7 years": [],
                "7+ years": []
            }
            
            for c in candidates:
                exp = c.total_experience_years or 0
                if exp < 3:
                    ranges["0-3 years"].append(c)
                elif exp < 7:
                    ranges["3-7 years"].append(c)
                else:
                    ranges["7+ years"].append(c)
            
            message_parts = ["**Candidates by experience range:**", ""]
            for range_name, cands in ranges.items():
                message_parts.append(f"- {range_name}: {len(cands)} candidates")
            
            message = "\n".join(message_parts)
            
            return {
                "type": "text",
                "message": message,
                "data": {
                    "ranges": {
                        range_name: len(cands)
                        for range_name, cands in ranges.items()
                    }
                }
            }
        
        # Unknown group_by - treat as regular list
        else:
            if not candidates:
                return self._handle_no_results(intent)
            
            candidate_rows = self._extract_candidate_rows(candidates)
            summary = f"Found {len(candidates)} candidates. (Note: grouping by '{group_by}' is not yet supported)"
            insights = self._generate_insights(candidate_rows, intent)
            
            return {
                "type": "table",
                "message": summary,
                "data": {
                    "candidates": candidate_rows,
                    "total": len(candidate_rows),
                    "filters": intent.get("filters", {}),
                    "insights": insights
                }
            }
    
    def _handle_no_results(self, intent: Dict) -> Dict[str, Any]:
        """Smart no-results handler with suggestions."""
        
        filters = intent.get("filters", {})
        suggestions = []
        
        if filters.get("min_experience"):
            suggestions.append(f"Try lowering the minimum experience requirement (currently {filters['min_experience']} years)")
        
        if filters.get("skills_required"):
            skills_str = ", ".join(filters["skills_required"])
            suggestions.append(f"Remove some required skills (currently: {skills_str})")
        
        if filters.get("role_bucket"):
            suggestions.append(f"Try searching in both buckets instead of just {filters['role_bucket']}")
        
        if not suggestions:
            suggestions.append("Try a broader search without filters")
            suggestions.append("Check the Candidates tab to see all available profiles")
        
        # Build message without backslashes in f-string
        message_parts = ["No candidates found matching your criteria.", "", "**Suggestions:**"]
        for s in suggestions:
            message_parts.append(f"- {s}")
        
        message = "\n".join(message_parts)
        
        return {
            "type": "text",
            "message": message,
            "data": {"suggestions": suggestions}
        }
    
    def _generate_smart_summary(self, user_query: str, intent: Dict, candidates: List[Dict], context: Optional[List[Dict]], suggestion: Optional[str] = None) -> str:
        """
        LLM-powered smart summary generation with ChatGPT-like natural responses.
        """
        
        # Check if this is a single-candidate query (follow-up about specific person)
        is_single_candidate = len(candidates) == 1 and intent.get("filters", {}).get("name_filter")
        
        # Build better candidate summary with key info
        candidate_summary = "\n".join([
            f"- {c['name']}: {c['role']} ({c['experience']} yrs exp) | Bucket: {c['bucket']} | "
            f"Skills: {', '.join(c['skills'][:4]) if c['skills'] else 'N/A'}"
            for c in candidates[:8]  # Show more candidates in summary
        ])
        
        context_str = ""
        if context:
            context_lines = []
            for msg in context[-2:]:
                user_msg = msg.get('user', '')
                
                # ✅ FIX: Safely handle assistant message which might be dict or string
                assistant_value = msg.get('assistant', '')
                if isinstance(assistant_value, dict):
                    assistant_msg = assistant_value.get('message', str(assistant_value))[:100]
                elif isinstance(assistant_value, str):
                    assistant_msg = assistant_value[:100]
                else:
                    assistant_msg = str(assistant_value)[:100] if assistant_value else ''
                
                context_lines.append(f"User: {user_msg}")
                if assistant_msg:
                    context_lines.append(f"Assistant: {assistant_msg}")
            
            context_str = "\n".join(context_lines)
        
        # Build filters description
        filters_desc = self._describe_filters(intent.get("filters", {}))
        
        prompt_parts = []
        prompt_parts.append("You are a helpful, conversational AI assistant helping query a candidate database.")
        prompt_parts.append("Your responses should be natural, friendly, and informative - like ChatGPT.")
        prompt_parts.append("IMPORTANT: Write as if you're directly answering the question. Don't say 'The user asked...' or 'You asked...' - just answer naturally.")
        prompt_parts.append("")
        
        if suggestion:
            prompt_parts.append(f"IMPORTANT: {suggestion}")
            prompt_parts.append("Include this information naturally in your response if relevant.")
            prompt_parts.append("")
        
        if context_str:
            prompt_parts.append("RECENT CONVERSATION:")
            prompt_parts.append(context_str)
            prompt_parts.append("")
        
        # Build natural context without "USER ASKED"
        prompt_parts.append(f"Query: \"{user_query}\"")
        if filters_desc:
            prompt_parts.append(f"Filters: {filters_desc}")
        prompt_parts.append("")
        prompt_parts.append(f"Database Results ({len(candidates)} candidate(s)):")
        prompt_parts.append(candidate_summary)
        
        if len(candidates) > 8:
            prompt_parts.append(f"... and {len(candidates) - 8} more candidates")
        
        prompt_parts.append("")
        
        if is_single_candidate:
            c = candidates[0]
            # Extract what they're asking about
            query_lower = user_query.lower()
            
            if any(kw in query_lower for kw in ['skill', 'skills', 'technical', 'technologies']):
                skills_list = ', '.join(c['skills'][:10]) if c['skills'] else 'No skills listed'
                prompt_parts.append(f"Generate a natural, conversational response about {c['name']}'s skills.")
                prompt_parts.append(f"Format: Start naturally (e.g., '{c['name']} has experience with...' or 'Here are {c['name']}'s skills:').")
                prompt_parts.append(f"Then list the skills: {skills_list}")
                prompt_parts.append("Be conversational and helpful, like you're explaining to a friend.")
            elif any(kw in query_lower for kw in ['project', 'projects', 'worked on']):
                prompt_parts.append(f"Generate a natural response about {c['name']}'s projects.")
                prompt_parts.append(f"Format: Start naturally (e.g., '{c['name']} has worked on...' or 'Here are {c['name']}'s projects:').")
            elif any(kw in query_lower for kw in ['experience', 'years', 'how long']):
                prompt_parts.append(f"Generate a natural response about {c['name']}'s experience.")
                prompt_parts.append(f"Format: Start naturally (e.g., '{c['name']} has {c['experience']} years of experience...').")
            else:
                prompt_parts.append(f"Generate a natural, conversational response about {c['name']}.")
                prompt_parts.append(f"Format: Start naturally (e.g., '{c['name']} is...' or 'Here's what I found about {c['name']}:').")
                prompt_parts.append("Be friendly and informative.")
        else:
            prompt_parts.append("Generate a natural, conversational summary (2-3 sentences) that:")
            prompt_parts.append("- Sounds like a helpful human assistant (not robotic)")
            prompt_parts.append("- Mentions the number of candidates found naturally")
            prompt_parts.append("- Highlights key characteristics in a conversational way")
            prompt_parts.append("- Example: 'I found 5 data scientists with Python experience. They range from 3 to 8 years of experience...'")
            prompt_parts.append("- NEVER say 'The user asked' or 'You asked' - just answer directly")
            prompt_parts.append("- Avoid phrases like 'Found X candidates' - be more natural")
        
        prompt = "\n".join(prompt_parts)
        
        try:
            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are a friendly, helpful AI assistant. Write naturally and conversationally, like ChatGPT. Be informative but not robotic. Use natural language, not database jargon. NEVER say 'The user asked' or 'You asked' - just answer the question directly as if you're having a conversation."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,  # Higher temperature for more natural responses
                max_tokens=300
            )
            
            summary = response.choices[0].message.content.strip()
            
            # Prepend suggestion if exists and not already included
            if suggestion and suggestion not in summary:
                summary = f"{suggestion}\n\n{summary}"
            
            return summary
            
        except Exception as e:
            print(f"❌ Summary generation failed: {e}")
            # Natural fallback
            if is_single_candidate:
                c = candidates[0]
                query_lower = user_query.lower()
                
                if any(kw in query_lower for kw in ['skill', 'skills']):
                    skills = ', '.join(c['skills'][:10]) if c['skills'] else 'No skills listed'
                    fallback = f"{c['name']} has experience with: {skills}."
                elif any(kw in query_lower for kw in ['project', 'projects']):
                    fallback = f"Here are {c['name']}'s projects from their resume."
                elif any(kw in query_lower for kw in ['experience', 'years']):
                    fallback = f"{c['name']} has {c['experience']} years of experience as a {c['role']}."
                else:
                    fallback = f"Here's what I found about {c['name']}."
                
                if suggestion:
                    return f"{suggestion}\n\n{fallback}"
                return fallback
            
            # Build natural fallback for multiple candidates
            filters_desc = self._describe_filters(intent.get("filters", {}))
            if suggestion:
                return f"{suggestion}\n\nI found {len(candidates)} candidate(s) that might be relevant."
            elif filters_desc:
                return f"I found {len(candidates)} candidate(s){filters_desc}."
            else:
                return f"I found {len(candidates)} candidate(s) matching your query."
    
    def _generate_insights(self, candidates: List[Dict], intent: Dict) -> List[str]:
        """
        Generate actionable insights from results.
        """
        
        insights = []
        
        if not candidates:
            return insights
        
        # Experience distribution insight
        avg_exp = sum(c["experience"] for c in candidates) / len(candidates)
        if avg_exp > 7:
            insights.append(f"💡 This is a senior pool - average experience is {avg_exp:.1f} years")
        elif avg_exp < 3:
            insights.append(f"💡 This is a junior pool - average experience is {avg_exp:.1f} years")
        
        # Skill coverage insight
        all_skills = set()
        for c in candidates:
            all_skills.update([s.lower() for s in c["skills"]])
        
        if len(all_skills) > 20:
            insights.append(f"💡 Diverse skill set - {len(all_skills)} unique skills across candidates")
        
        # Bucket distribution insight
        ds_count = sum(1 for c in candidates if c["bucket"] == "data_scientist")
        if ds_count > 0 and ds_count < len(candidates):
            insights.append(f"💡 Mixed pool: {ds_count} Data Scientists, {len(candidates) - ds_count} Data Practice")
        
        return insights
    
    def _describe_filters(self, filters: Dict) -> str:
        """Generate human-readable filter description."""
        
        parts = []
        
        if filters.get("role_bucket") == "data_scientist":
            parts.append("Data Scientists")
        elif filters.get("role_bucket") == "data_practice":
            parts.append("Data Practice professionals")
        
        if filters.get("min_experience"):
            parts.append(f"{filters['min_experience']}+ years experience")
        
        if filters.get("max_experience"):
            # Use regular less-than-or-equal without unicode
            parts.append(f"<={filters['max_experience']} years experience")
        
        if filters.get("skills_required"):
            skills_str = ", ".join(filters["skills_required"])
            parts.append(f"with skills: {skills_str}")
        
        if filters.get("skills_excluded"):
            skills_str = ", ".join(filters["skills_excluded"])
            parts.append(f"excluding: {skills_str}")
        
        if filters.get("keyword"):
            parts.append(f"matching '{filters['keyword']}'")
        
        if filters.get("name_filter"):
            parts.append(f"name contains '{filters['name_filter']}'")
        
        if parts:
            return " (" + " • ".join(parts) + ")"
        return ""

    def _extract_entities_from_response(self, response_text: str) -> Optional[str]:
        """
        Extract candidate name or ID from a previous response.
        Returns the most likely entity mentioned.
        """
        import re

        # Pattern 1: "Found [Name]" or "Here is [Name]"
        name_patterns = [
            r"(?:Found|Showing|Here (?:is|are))\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]?\.?)?)",
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]?\.?)?)(?:'s|has|is|was)",
        ]

        for pattern in name_patterns:
            match = re.search(pattern, response_text)
            if match:
                return match.group(1).strip()

        # Pattern 2: "Candidate ID: 5" or "(ID 5)"
        id_match = re.search(r'(?:ID[:\s]+|candidate\s+)(\d+)', response_text, re.IGNORECASE)
        if id_match:
            return f"ID:{id_match.group(1)}"

        return None
    
    # ============ CACHING ============
    
    def _get_cache_key(self, query: str, context: Optional[List[Dict]]) -> str:
        """Generate cache key from query and context."""
        context_key = str(context[-1] if context else "")
        return f"{query.lower().strip()}:{context_key}"
    
    def _get_from_cache(self, key: str) -> Optional[Dict]:
        """Get from cache if not expired."""
        if key in self._cache:
            entry = self._cache[key]
            if datetime.now().timestamp() - entry["timestamp"] < self._cache_ttl:
                return entry["data"]
        return None
    
    def _set_cache(self, key: str, data: Dict):
        """Set cache entry."""
        self._cache[key] = {
            "data": data,
            "timestamp": datetime.now().timestamp()
        }
        
        # Simple cache size management (keep last 100 entries)
        if len(self._cache) > 100:
            oldest = min(self._cache.items(), key=lambda x: x[1]["timestamp"])
            del self._cache[oldest[0]]

# Singleton instance
_query_handler = None

def get_query_handler():
    """Get or create GeneralQueryHandler instance."""
    global _query_handler
    if _query_handler is None:
        _query_handler = GeneralQueryHandler()
    return _query_handler

