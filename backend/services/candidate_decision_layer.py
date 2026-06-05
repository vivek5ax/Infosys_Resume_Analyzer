"""
Candidate Decision Layer - Career Development & Gap Closure Roadmap for Candidates.
Provides role-fit assessment, evidence strength analysis, gap closure roadmap, and action plans.
"""

from typing import Any, Dict, List
from datetime import datetime, timezone


def _to_float(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return fallback


def _clean_text(value: Any) -> str:
    text = str(value or "").strip()
    return " ".join(text.split())


def _calculate_readiness_score(exact_count: int, semantic_count: int, missing_count: int, alignment_score: int, evidence_quality: float = 0.7) -> int:
    """
    Calculate overall readiness score (0-100).
    Based on: exact matches, semantic matches, gaps, and evidence quality.
    Adjusted by how well skills are backed with evidence snippets.
    """
    total_skills = exact_count + semantic_count + missing_count
    if total_skills == 0:
        return 0
    
    match_percentage = ((exact_count + semantic_count) / total_skills) * 100
    gap_penalty = (missing_count / total_skills) * 30
    alignment_weight = alignment_score * 0.4
    evidence_boost = evidence_quality * 15
    
    readiness = match_percentage * 0.35 + alignment_weight + evidence_boost - gap_penalty
    return int(max(0, min(100, round(readiness))))


def _categorize_skills(partition: Dict[str, Any], triage_items: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """
    Categorize skills into: Strong, Similar, Emerging, Critical Gaps.
    """
    exact_matches = partition.get("exact_match", []) if isinstance(partition.get("exact_match"), list) else []
    
    strong_skills = exact_matches[:12] if isinstance(exact_matches, list) else []
    
    similar_skills = []
    semantic_items = partition.get("strong_semantic", []) if isinstance(partition.get("strong_semantic"), list) else []
    if isinstance(semantic_items, list):
        similar_skills = [
            item.get("skill") for item in semantic_items 
            if isinstance(item, dict) and _to_float(item.get("score", 0)) > 0.70
        ][:5]
    
    emerging_skills = []
    moderate_items = partition.get("moderate_semantic", []) if isinstance(partition.get("moderate_semantic"), list) else []
    if isinstance(moderate_items, list):
        emerging_skills = [
            item.get("skill") for item in moderate_items 
            if isinstance(item, dict) and _to_float(item.get("score", 0)) > 0.60
        ][:5]
    
    critical_gaps = []
    if isinstance(triage_items, list):
        for item in triage_items:
            if isinstance(item, dict):
                priority = str(item.get("priority") or "").lower()
                # Accept multiple terms for critical
                if priority in {"role_critical", "critical", "high"}:
                    skill = _clean_text(item.get("skill"))
                    if skill and skill not in critical_gaps:
                        critical_gaps.append(skill)
                        if len(critical_gaps) >= 3:
                            break
    
    return {
        "strong": strong_skills,
        "similar": similar_skills,
        "emerging": emerging_skills,
        "critical_gaps": critical_gaps,
    }


def _estimate_learning_timeline(skill_name: str, skill_count_in_domain: int = 0) -> Dict[str, Any]:
    """
    Estimate realistic timeline for learning a skill based on complexity heuristics.
    """
    skill_lower = skill_name.lower()
    
    # Very Hard (8-12 weeks)
    very_hard_keywords = ["kubernetes", "system design", "distributed systems", "machine learning", "deep learning", 
                         "architecture", "devops", "cloud architect"]
    
    # Medium (4-6 weeks)
    medium_keywords = ["docker", "ci/cd", "microservices", "graphql", "grpc", "oauth", "websockets",
                      "react", "vue", "angular", "aws", "gcp", "azure", "terraform"]
    
    # Easy (2-3 weeks)
    easy_keywords = ["git", "sql", "rest", "json", "http", "testing", "logging", "monitoring",
                    "typescript", "python basics"]
    
    difficulty = "🟢 Easy"
    weeks = 2
    description = "Relatively quick to learn with existing knowledge"
    
    for keyword in very_hard_keywords:
        if keyword in skill_lower:
            difficulty = "🔴 Very Hard"
            weeks = 10
            description = "Requires deep learning and multiple projects"
            break
    
    for keyword in medium_keywords:
        if keyword in skill_lower:
            difficulty = "🟡 Medium"
            weeks = 5
            description = "Moderate complexity; requires hands-on practice"
            break
    
    for keyword in easy_keywords:
        if keyword in skill_lower:
            difficulty = "🟢 Easy"
            weeks = 2
            description = "Quick to learn, especially with programming background"
            break
    
    return {
        "difficulty": difficulty,
        "weeks_to_proficiency": weeks,
        "description": description,
    }


def _generate_learning_path(skill_name: str, weeks: int) -> List[str]:
    """
    Generate a realistic week-by-week learning path for a skill.
    """
    if weeks <= 2:
        return [
            f"Week 1: Learn fundamentals of {skill_name} (online course, tutorials)",
            f"Week 2: Build small project and document learnings",
        ]
    elif weeks <= 4:
        return [
            f"Week 1: Learn fundamentals and core concepts of {skill_name}",
            f"Week 2: Follow structured tutorial / course",
            f"Week 3: Build moderately complex project using {skill_name}",
            f"Week 4: Document project, create portfolio entry, prepare interview stories",
        ]
    elif weeks <= 6:
        return [
            f"Week 1: Complete foundational course on {skill_name}",
            f"Week 2: Study architecture patterns and best practices",
            f"Week 3-4: Build substantial project demonstrating {skill_name} mastery",
            f"Week 5: Optimize project, add documentation, industry best practices",
            f"Week 6: Create case study / blog post, refine interview explanations",
        ]
    else:  # 8+ weeks
        return [
            f"Week 1-2: Deep dive foundational course on {skill_name}",
            f"Week 3-4: Study architecture, design patterns, advanced concepts",
            f"Week 5-6: Build first substantial project, encounter and solve real problems",
            f"Week 7-8: Optimize, refactor, document decisions and trade-offs",
            f"Week 9-10: Create production-ready examples, write technical articles",
            f"Week 11+: Contribute to open source, mentor others, develop expert perspective",
        ]


def _generate_6week_action_plan(critical_gaps: List[str], important_gaps: List[str], readiness: int) -> List[Dict[str, Any]]:
    """
    Generate a concrete 6-week action plan with weekly milestones.
    """
    plan = []
    
    # Weeks 1-2: Critical gaps foundational learning
    if critical_gaps:
        skill = critical_gaps[0]
        plan.append({
            "week": 1,
            "phase": "Foundation",
            "focus_topic": skill,
            "goal": f"Complete foundational course on {skill}",
            "actions": _generate_learning_path(skill, 2)[:1],
            "artifact_to_create": f"Course completion certificate or GitHub repo with notes",
            "validation": f"Can you explain {skill} core concepts in your own words?",
            "confidence_gain": "+15%",
        })
        
        plan.append({
            "week": 2,
            "phase": "Hands-On",
            "focus_topic": skill,
            "goal": f"Build first project using {skill}",
            "actions": _generate_learning_path(skill, 2)[1:],
            "artifact_to_create": f"GitHub repo with {skill} project (well-documented README)",
            "validation": "Demo your project to a peer or mentor",
            "confidence_gain": "+20%",
        })
    
    # Weeks 3-4: Important gaps + deepen first skill
    if len(critical_gaps) > 1 or important_gaps:
        skill = critical_gaps[1] if len(critical_gaps) > 1 else (important_gaps[0] if important_gaps else critical_gaps[0])
        plan.append({
            "week": 3,
            "phase": "Deep Dive",
            "focus_topic": skill,
            "goal": f"Learn advanced concepts in {skill}",
            "actions": [f"Study {skill} beyond basics", "Learn architecture & best practices", "Review industry standards"],
            "artifact_to_create": f"Blog post or Medium article: 'My {skill} Journey'",
            "validation": "Explain your learning path to someone new to the skill",
            "confidence_gain": "+15%",
        })
        
        plan.append({
            "week": 4,
            "phase": "Integration",
            "focus_topic": "Role Knowledge",
            "goal": "Understand role responsibilities deeply",
            "actions": ["Analyze job description detail", "Map your skills to role needs", "Identify interview questions likely to be asked"],
            "artifact_to_create": "Document: 'How My Skills Match This Role'",
            "validation": "Can you map 10+ of your experiences to role requirements?",
            "confidence_gain": "+10%",
        })
    
    # Weeks 5-6: Interview prep
    plan.append({
        "week": 5,
        "phase": "Interview Prep",
        "focus_topic": "Technical Storytelling",
        "goal": "Prepare compelling project stories",
        "actions": [
            "Document 5-6 key projects with: problem, your solution, impact",
            "Prepare for technical deep-dives",
            "Create cheat sheet of technical concepts",
        ],
        "artifact_to_create": "Interview preparation document with STAR stories",
        "validation": "Can you tell 5 minute stories about your projects without hesitation?",
        "confidence_gain": "+15%",
    })
    
    plan.append({
        "week": 6,
        "phase": "Final Polish",
        "focus_topic": "Mock Interviews",
        "goal": "Do mock interviews and refine answers",
        "actions": [
            "Conduct mock interview with peer or mentor",
            "Record yourself answering technical questions",
            "Review and refine your explanations",
        ],
        "artifact_to_create": "Recording of mock interview or feedback notes",
        "validation": "Peer feedback: 'I'd hire you based on this interview'",
        "confidence_gain": "+10%",
    })
    
    return plan[:6]  # Return exactly 6 weeks


def _parse_confidence_gain(value: Any, fallback: int = 10) -> int:
    """Parse confidence gain values like '+15%' or numeric inputs into an integer."""
    if isinstance(value, (int, float)):
        return int(value)

    text = _clean_text(value)
    if not text:
        return fallback

    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return fallback

    try:
        return int(digits)
    except Exception:
        return fallback


def build_candidate_decision_layer(
    *,
    bert_results: Dict[str, Any],
    ai_enrichment: Dict[str, Any],
    jd_text: str,
    resume_text: str,
    domain: str = "software",
) -> Dict[str, Any]:
    """
    Build candidate-focused decision layer with:
    - Role-fit assessment (readiness score, skill breakdown)
    - Evidence strength analysis
    - Gap closure roadmap (learning paths with timelines)
    - 6-week action plan
    - Career insights
    """
    
    # Extract base data
    summary = bert_results.get("summary", {}) if isinstance(bert_results.get("summary"), dict) else {}
    partition = bert_results.get("skill_partition", {}) if isinstance(bert_results.get("skill_partition"), dict) else {}
    match_evidence = bert_results.get("match_evidence", []) if isinstance(bert_results.get("match_evidence"), list) else []
    
    exact_count = int(summary.get("exact_match_count") or 0)
    semantic_count = int(summary.get("semantic_match_count") or 0)
    missing_count = int(summary.get("missing_skills_count") or 0)
    alignment_score = int(round(_to_float(summary.get("overall_alignment_score"), 0.0)))
    
    # AI Enrichment Data
    triage = ai_enrichment.get("missing_skill_triage", []) if isinstance(ai_enrichment.get("missing_skill_triage"), list) else []
    interview_focus = ai_enrichment.get("interview_focus", []) if isinstance(ai_enrichment.get("interview_focus"), list) else []
    
    # Calculate evidence quality (base on snippet presence and specificity)
    evidence_with_context = sum(1 for e in match_evidence if isinstance(e, dict) and (e.get("jd_snippet") or e.get("resume_snippet")))
    evidence_quality = (evidence_with_context / max(1, len(match_evidence))) if match_evidence else 0.5
    
    # Calculate readiness score
    readiness_score = _calculate_readiness_score(exact_count, semantic_count, missing_count, alignment_score, evidence_quality)
    
    # Categorize skills
    skills = _categorize_skills(partition, triage)
    strong_skills = skills.get("strong", [])
    similar_skills = skills.get("similar", [])
    emerging_skills = skills.get("emerging", [])
    critical_gaps = skills.get("critical_gaps", [])
    
    # Extract important gaps from triage, avoiding duplicates with critical gaps
    important_gaps = []
    if isinstance(triage, list):
        for item in triage:
            if isinstance(item, dict):
                priority = str(item.get("priority") or "").lower()
                skill = _clean_text(item.get("skill"))
                if skill and skill not in critical_gaps and skill not in important_gaps:
                    important_gaps.append(skill)
                    if len(important_gaps) >= 3:
                        break
    
    # If we STILL have no critical gaps but we have important gaps, promote the top important gap to critical
    # to ensure the gap closure roadmap always gives the candidate a high-priority focus area.
    if not critical_gaps and important_gaps:
        critical_gaps.append(important_gaps.pop(0))
    
    # === SECTION 1: ROLE-FIT ASSESSMENT ===
    
    readiness_interpretation = (
        f"You're a strong match. You have most core skills, minimal gaps."
        if readiness_score >= 80
        else f"You're a competitive candidate. Target gaps and you're highly competitive."
        if readiness_score >= 65
        else f"You're borderline. With focused 6-week effort on key gaps, you can be highly competitive."
        if readiness_score >= 50
        else "You have significant gaps. Consider upskilling before applying or discuss growth potential in interview."
    )
    
    can_interview = readiness_score >= 40
    interview_likelihood = (
        "Very likely"
        if readiness_score >= 80
        else "Likely"
        if readiness_score >= 65
        else "Possible"
        if readiness_score >= 50
        else "Unlikely"
    )
    
    role_fit_assessment = {
        "readiness_score": readiness_score,
        "interpretation": readiness_interpretation,
        "can_interview": can_interview,
        "interview_likelihood": interview_likelihood,
        "skills_breakdown": {
            "matched_exact": {
                "count": exact_count,
                "list": strong_skills,
                "interpretation": f"You have {exact_count} exact core skills matches",
            },
            "matched_semantic": {
                "count": semantic_count,
                "list": similar_skills,
                "interpretation": f"{len(similar_skills)} additional related skills transferred from your experience",
            },
            "partial_emerging": {
                "count": len(emerging_skills),
                "list": emerging_skills,
                "interpretation": f"{len(emerging_skills)} skills you're developing or have partial exposure",
            },
            "critical_gaps": {
                "count": len(critical_gaps),
                "list": critical_gaps,
                "interpretation": f"{len(critical_gaps)} critical role-specific skill(s) not evident in your resume",
            },
        },
    }
    
    # === SECTION 2: EVIDENCE STRENGTH ===
    
    strong_evidence_items = []
    weak_evidence_items = []
    missing_evidence_items = []
    
    for evidence in match_evidence:
        if not isinstance(evidence, dict):
            continue
        
        skill = _clean_text(evidence.get("skill"))
        has_jd_snippet = bool(_clean_text(evidence.get("jd_snippet")))
        has_resume_snippet = bool(_clean_text(evidence.get("resume_snippet")))
        snippet_length = len(_clean_text(evidence.get("resume_snippet") or ""))
        
        if has_jd_snippet and has_resume_snippet and snippet_length > 50:
            strong_evidence_items.append({
                "skill": skill,
                "match_type": evidence.get("match_type", "unknown"),
                "evidence_source": evidence.get("resume_snippet", "")[:100] + "...",
            })
        elif has_resume_snippet:
            weak_evidence_items.append({
                "skill": skill,
                "issue": "Mentioned but with minimal context or details",
                "recommendation": f"Add specific project examples demonstrating {skill}",
            })
    
    # Skills mentioned in JD but not in resume
    jd_only = partition.get("jd_only", []) if isinstance(partition.get("jd_only"), list) else []
    for skill in jd_only[:5]:
        if isinstance(skill, str):
            missing_evidence_items.append({
                "skill": skill,
                "issue": "Mentioned in job description, not in your resume",
                "recommendation": f"If you have experience with {skill}, add it to your resume or be prepared to discuss",
            })
    
    evidence_quality_score = int((evidence_with_context / max(1, len(match_evidence))) * 100) if match_evidence else 0
    coverage_percentage = int(((exact_count + semantic_count) / max(1, exact_count + semantic_count + missing_count)) * 100)
    
    evidence_strength = {
        "overall_quality_score": evidence_quality_score,
        "coverage_percentage": coverage_percentage,
        "strong_evidence": {
            "count": len(strong_evidence_items),
            "items": strong_evidence_items[:5],
            "summary": f"You've provided {len(strong_evidence_items)} skills with strong, specific evidence",
        },
        "weak_evidence": {
            "count": len(weak_evidence_items),
            "items": weak_evidence_items[:5],
            "summary": f"{len(weak_evidence_items)} skills mentioned with minimal supporting details",
        },
        "missing_evidence": {
            "count": len(missing_evidence_items),
            "items": missing_evidence_items[:5],
            "summary": f"{len(missing_evidence_items)} role-required skills not mentioned in your resume",
        },
        "interview_talking_points": {
            "discuss_in_depth": strong_skills[:3],
            "can_briefly_mention": similar_skills[:2],
            "avoid_claiming": critical_gaps[:2],
        },
    }
    
    # === SECTION 3: GAP CLOSURE ROADMAP ===
    
    gap_roadmap = []
    
    # Add critical gaps
    for idx, skill in enumerate(critical_gaps[:3]):
        timeline = _estimate_learning_timeline(skill)
        gap_roadmap.append({
            "priority": "CRITICAL",
            "priority_order": idx + 1,
            "skill": skill,
            "difficulty": timeline["difficulty"],
            "weeks_to_proficiency": timeline["weeks_to_proficiency"],
            "why_needed": f"{skill} is explicitly required for this role based on the job description",
            "learning_phases": _generate_learning_path(skill, timeline["weeks_to_proficiency"]),
            "evidence_artifact": f"GitHub project demonstrating {skill} implementation with architecture decisions documented",
            "interview_signal": f"'Walk us through a project where you used {skill}. Explain your architectural decisions.'",
            "expected_boost": f"+{max(8, 20 - idx*4)}% to match strength",
            "realistic_timeline": f"{timeline['weeks_to_proficiency']} weeks of focused learning with 10-15 hours/week",
        })
    
    # Add important gaps
    for idx, skill in enumerate(important_gaps[:2]):
        timeline = _estimate_learning_timeline(skill)
        gap_roadmap.append({
            "priority": "IMPORTANT",
            "priority_order": idx + 1,
            "skill": skill,
            "difficulty": timeline["difficulty"],
            "weeks_to_proficiency": timeline["weeks_to_proficiency"],
            "why_needed": f"{skill} would significantly improve your capability for this role",
            "learning_phases": _generate_learning_path(skill, timeline["weeks_to_proficiency"]),
            "evidence_artifact": f"Side project or contribution demonstrating {skill} expertise",
            "interview_signal": f"'Have you worked with {skill}? Tell us about that experience.'",
            "expected_boost": f"+{max(5, 12 - idx*3)}% to match strength",
            "realistic_timeline": f"{timeline['weeks_to_proficiency']} weeks with regular practice",
        })
    
    # === SECTION 4: 6-WEEK ACTION PLAN ===
    
    action_plan = _generate_6week_action_plan(critical_gaps, important_gaps, readiness_score)
    
    # Calculate projected readiness at end of plan
    improvements = sum(
        _parse_confidence_gain(item.get("confidence_gain", "+10%"), fallback=10)
        for item in action_plan
        if isinstance(item, dict)
    )
    if improvements <= 0:
        improvements = 40
    
    projected_readiness = int(min(95, readiness_score + improvements))
    
    action_plan_summary = {
        "timeline_days": 42,
        "weeks": 6,
        "current_readiness": readiness_score,
        "projected_readiness_after_plan": projected_readiness,
        "readiness_improvement": projected_readiness - readiness_score,
        "weekly_commitment_hours": "10-15 hours per week optimal",
        "milestones": action_plan,
        "evidence_checklist": [
            "✅ GitHub projects (well-documented, production-ready code)",
            "✅ Blog posts or Medium articles explaining your learning",
            "✅ Technical videos (demo videos of your projects acceptable)",
            "✅ Project case studies with problem, solution, impact metrics",
            "✅ LinkedIn recommendations from colleagues/mentors",
            "✅ Open source contributions (optional but impressive)",
        ],
    }
    
    # === SECTION 5: CAREER INSIGHTS ===
    
    role_level_match = (
        "Perfect Match"
        if readiness_score >= 80
        else "Good Match"
        if readiness_score >= 60
        else "Developing Fit"
    )
    
    career_insights = {
        "this_role": {
            "level_match": role_level_match,
            "fit_assessment": f"Your background aligns well with this {'Senior' if alignment_score >= 70 else 'Mid-level' if alignment_score >= 50 else 'Junior'} role",
            "day_one_impact": "You can contribute meaningfully from day 1" if readiness_score >= 75 else "You'll need 2-4 weeks ramp-up time" if readiness_score >= 50 else "You'll need 6-8 weeks structured onboarding",
        },
        "career_path": {
            "next_level_opportunity": "Senior/Staff Engineer" if alignment_score >= 70 else "Senior Engineer" if alignment_score >= 50 else "Mid-level Engineer",
            "timeline_to_next_level": "2-3 years" if alignment_score >= 70 else "3-4 years",
            "skills_that_accelerate_growth": critical_gaps[:2] if critical_gaps else ["System Design", "Architecture Planning"],
        },
        "industry_outlook": {
            "domain_relevance": f"The {domain} domain remains in-demand and growing",
            "skill_demand_2026_vs_2036": f"Skills needed for this role will be even more valuable in 10 years",
            "career_longevity": "Specializing in this area sets you up for long-term career growth and higher compensation",
        },
        "compensation_insights": {
            "median_salary_range": {
                "junior": "$90K-120K",
                "mid": "$130K-170K",
                "senior": "$160K-220K",
                "staff": "$200K-300K+",
            },
            "promotion_timeline": "Typically 3-4 years to next level with consistent performance",
            "equity_upside_potential": "Early stage companies offer higher equity; established tech offers stability",
        },
        "long_term_value": "This role provides skills and experience that will be valuable across 50+ other opportunities in the industry",
    }
    
    # === MAIN PAYLOAD ===
    
    candidate_decision_layer = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "domain": domain,
        "role_fit_assessment": role_fit_assessment,
        "evidence_strength": evidence_strength,
        "gap_closure_roadmap": gap_roadmap,
        "action_plan": action_plan_summary,
        "career_insights": career_insights,
        "overall_guidance": {
            "primary_message": readiness_interpretation,
            "recommended_action": (
                "Apply now — you're a strong fit"
                if readiness_score >= 80
                else "Apply and prepare for technical deep dives"
                if readiness_score >= 65
                else "Follow the 6-week action plan, then apply as a stronger candidate"
                if readiness_score >= 50
                else "Consider upskilling on key gaps; then revisit"
            ),
            "confidence_level": interview_likelihood,
        },
    }
    
    return candidate_decision_layer
