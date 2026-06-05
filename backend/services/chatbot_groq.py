import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List


GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.1-8b-instant"
ALLOWED_INTENTS = {
    "matched_skills",
    "missing_skills",
    "projects",
    "interview_tips",
    "resume_improvements",
    "general",
}
ALLOWED_MODES = {"resume_context", "general"}

FREE_RESOURCES = {
    "distributed systems": [
        "MIT 6.824 Distributed Systems (free lectures/labs): https://pdos.csail.mit.edu/6.824/",
        "Distributed Systems for Practitioners (free chapters/articles): https://github.com/jeffgerickson/algorithms (supporting foundations)",
    ],
    "microservices": [
        "Microservices.io patterns (free): https://microservices.io/",
        "freeCodeCamp Microservices courses (free): https://www.freecodecamp.org/news/tag/microservices/",
    ],
    "system design": [
        "System Design Primer (free): https://github.com/donnemartin/system-design-primer",
        "Gaurav Sen YouTube system design playlist (free): https://www.youtube.com/@gkcs",
    ],
    "azure": [
        "Microsoft Learn Azure Fundamentals path (free): https://learn.microsoft.com/training/paths/azure-fundamentals/",
    ],
    "ci/cd": [
        "GitHub Actions docs and guides (free): https://docs.github.com/actions",
        "Azure DevOps CI/CD Learn modules (free): https://learn.microsoft.com/training/azure/devops/",
    ],
    "docker": [
        "Docker official getting started (free): https://docs.docker.com/get-started/",
    ],
    "kubernetes": [
        "Kubernetes official tutorials (free): https://kubernetes.io/docs/tutorials/",
    ],
    "rest api": [
        "REST API design best practices (free): https://learn.microsoft.com/azure/architecture/best-practices/api-design",
    ],
    "c#": [
        "C# fundamentals on Microsoft Learn (free): https://learn.microsoft.com/training/paths/csharp-first-steps/",
    ],
    "c++": [
        "LearnCpp (free comprehensive C++): https://www.learncpp.com/",
    ],
}


def _load_local_env() -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    for env_name in [".env", ".env.local"]:
        env_path = backend_dir / env_name
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#") or "=" not in raw:
                continue
            key, value = raw.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


_load_local_env()


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _clean_answer_text(value: Any) -> str:
    """Preserve line structure so bullets/numbered points stay readable in UI."""
    raw = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in raw.split("\n")]
    compact: List[str] = []
    previous_blank = False
    for ln in lines:
        if not ln:
            if not previous_blank:
                compact.append("")
            previous_blank = True
            continue
        compact.append(ln)
        previous_blank = False
    return "\n".join(compact).strip()


def _post_process_resume_answer(answer: str) -> str:
    text = str(answer or "").replace("\r\n", "\n").replace("\r", "\n")

    # Fix malformed duplicated prefix like: "Interview Tips## Interview Tips"
    text = re.sub(r"^\s*([A-Za-z][A-Za-z\s]{2,48})\s*##\s*\1\b", r"## \1", text, flags=re.IGNORECASE)

    # Remove standalone ruler lines (full lines of =, -, _, etc.)
    text = re.sub(r"^[ \t]*={3,}[ \t]*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[ \t]*-{3,}[ \t]*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[ \t]*_{3,}[ \t]*$", "", text, flags=re.MULTILINE)
    
    # Remove trailing ruler markers at end of lines (e.g., "Title =====")
    text = re.sub(r"[ \t]+={3,}[ \t]*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"[ \t]+-{4,}[ \t]*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"[ \t]+_{4,}[ \t]*$", "", text, flags=re.MULTILINE)
    
    # Keep separator isolated for frontend rendering (--- on its own line is OK)
    text = re.sub(r"\s*---\s*", "\n---\n", text)

    # Fix escaped asterisks and ensure bold markers render properly
    text = text.replace("\\*", "*")  # Remove escape chars before asterisks
    text = re.sub(r"\*\*\s+([^*]+?)\s+\*\*", r"**\1**", text)  # Normalize spacing around bold
    
    # Remove ### symbols that appear as decorative markers (not as heading syntax)
    text = re.sub(r"^[ \t]*#{3,}[ \t]*$", "", text, flags=re.MULTILINE)  # Standalone ###
    text = re.sub(r"[ \t]+#{3,}[ \t]*$", "", text, flags=re.MULTILINE)  # Trailing ###
    
    # Collapse excessive blank lines.
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def _clip(text: str, limit: int = 1400) -> str:
    clean = _clean_text(text)
    if len(clean) <= limit:
        return clean
    return f"{clean[:limit].rstrip()}..."


def _compact_for_prompt(value: Any, *, max_depth: int = 4, depth: int = 0) -> Any:
    """Keep prompt payload bounded to avoid upstream HTTP 413 errors."""
    if depth >= max_depth:
        if isinstance(value, str):
            return _clip(value, 180)
        if isinstance(value, (int, float, bool)) or value is None:
            return value
        return _clip(str(value), 180)

    if isinstance(value, str):
        return _clip(value, 260)

    if isinstance(value, list):
        limit = 8 if depth <= 1 else 6
        return [_compact_for_prompt(item, max_depth=max_depth, depth=depth + 1) for item in value[:limit]]

    if isinstance(value, dict):
        max_keys = 20 if depth == 0 else (14 if depth == 1 else 10)
        out: Dict[str, Any] = {}
        for idx, (k, v) in enumerate(value.items()):
            if idx >= max_keys:
                break
            out[str(k)] = _compact_for_prompt(v, max_depth=max_depth, depth=depth + 1)
        return out

    return value


def _extract_raw_text_prompt_context(context: Dict[str, Any]) -> Dict[str, str]:
    snippets = context.get("text_snippets", {}) if isinstance(context.get("text_snippets"), dict) else {}
    resume_text = _clean_text(snippets.get("resume_excerpt", ""))
    jd_text = _clean_text(snippets.get("job_description_excerpt", ""))
    return {
        "resume_raw_text": _clip(resume_text, 2600),
        "jd_raw_text": _clip(jd_text, 2600),
    }


def _to_float(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except Exception:
        return fallback


def _is_retryable_status(status_code: int) -> bool:
    return status_code in {408, 425, 429, 500, 502, 503, 504}


def _fallback_answer(question: str, context: Dict[str, Any], reason: str = "", mode: str = "resume_context") -> str:
    if mode == "general":
        base = "I could not complete the response right now"
        if reason:
            base += f" ({_clip(reason, 120)})"
        base += ". Please retry your question and I will answer it directly."
        return base

    q = _clean_text(question).lower()
    summary = context.get("summary", {}) if isinstance(context.get("summary"), dict) else {}
    findings = context.get("key_findings", {}) if isinstance(context.get("key_findings"), dict) else {}

    score = summary.get("overall_alignment_score", 0)
    missing = findings.get("missing_skills", []) or []
    exact = findings.get("exact_matches", []) or []

    if "missing" in q and missing:
        top = ", ".join(missing[:6])
        return f"Top missing skills in this session are: {top}. Focus first on these to improve role fit."

    if "score" in q or "alignment" in q:
        return (
            f"Current overall alignment score is {score}%. "
            "To increase it, prioritize adding high-demand missing skills from the JD and evidence of recent usage."
        )

    if "match" in q and exact:
        top_match = ", ".join(exact[:6])
        return f"Strongly matched skills include: {top_match}. You can highlight these in your resume summary and project bullets."

    base = "I could not complete the Groq response right now"
    if reason:
        base += f" ({_clip(reason, 120)})"
    base += ". I can still answer from session summary if you ask about matched skills, missing skills, projects, interview tips, or resume improvements."
    return base


def _top_semantic_items(context: Dict[str, Any], limit: int = 8) -> List[str]:
    findings = context.get("key_findings", {}) if isinstance(context.get("key_findings"), dict) else {}
    semantic = findings.get("semantic_matches", []) or []
    out: List[str] = []
    for item in semantic:
        text = _clean_text(item)
        if not text:
            continue
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _contains_any(text: str, words: List[str]) -> bool:
    return any(re.search(rf"\b{re.escape(word)}\b", text) for word in words)


def _resource_suggestions_for_missing(missing_skills: List[str], limit: int = 6) -> List[str]:
    suggestions: List[str] = []
    seen = set()

    for skill in missing_skills:
        key = _clean_text(skill).lower()
        resources = FREE_RESOURCES.get(key, [])
        for item in resources:
            if item in seen:
                continue
            seen.add(item)
            suggestions.append(f"- {skill}: {item}")
            if len(suggestions) >= limit:
                return suggestions

    fallback = [
        "- Microsoft Learn (free role paths): https://learn.microsoft.com/training/",
        "- freeCodeCamp full curriculum (free): https://www.freecodecamp.org/learn",
        "- Coursera audit mode (free course access): https://www.coursera.org/",
    ]
    for item in fallback:
        if len(suggestions) >= limit:
            break
        if item not in seen:
            suggestions.append(item)

    return suggestions


def _deterministic_context_answer(question: str, context: Dict[str, Any], intent: str = "general") -> str | None:
    q = _clean_text(question).lower()
    intent = _normalize_intent(intent)
    summary = context.get("summary", {}) if isinstance(context.get("summary"), dict) else {}
    findings = context.get("key_findings", {}) if isinstance(context.get("key_findings"), dict) else {}
    profile = context.get("candidate_profile", {}) if isinstance(context.get("candidate_profile"), dict) else {}
    projects = profile.get("projects", []) if isinstance(profile.get("projects"), list) else []
    inventory = context.get("skills_inventory", {}) if isinstance(context.get("skills_inventory"), dict) else {}

    exact = findings.get("exact_matches", []) or []
    missing = findings.get("missing_skills", []) or []
    semantic = _top_semantic_items(context)
    resume_soft = inventory.get("resume_soft", []) if isinstance(inventory.get("resume_soft"), list) else []
    score = int(summary.get("overall_alignment_score", 0) or 0)

    asks_projects = bool(re.search(r"\b(project|projects)\b", q))
    asks_interview = bool(re.search(r"\b(interview|interviewer|interviewing)\b", q))
    asks_presentation = bool(re.search(r"\b(present|presentation|confident|confidence|explain)\b", q))
    asks_resources = bool(re.search(r"\b(resource|resources|course|courses|roadmap|learn|learning|tutorial)\b", q))
    asks_preparation = bool(re.search(r"\b(prepare|preparation|practice|practise|improve|stronger|confidence|confident)\b", q))
    asks_softskills = bool(re.search(r"\b(soft\s*skills?|communication|teamwork|leadership|collaboration|problem\s*solving|time\s*management)\b", q))

    asks_matching = (intent == "matched_skills") or (bool(re.search(r"\b(match|matches|matching|matched)\b", q)) and bool(re.search(r"\b(skill|skills)\b", q)) and "missing" not in q)
    asks_missing = (intent == "missing_skills") or bool(re.search(r"\b(missing|gap|gaps)\b", q))
    asks_score = bool(re.search(r"\b(score|alignment)\b", q))

    if intent == "resume_improvements" and asks_softskills:
        soft_lines = "\n".join([f"- {s}" for s in resume_soft[:8]]) if resume_soft else "- Communication\n- Problem Solving"
        return (
            "To improve soft-skills presentation in your resume, make them evidence-based:\n\n"
            "Current detected soft skills:\n"
            f"{soft_lines}\n\n"
            "How to upgrade resume bullets:\n"
            "- Communication: mention stakeholder updates, demos, or documentation ownership.\n"
            "- Problem Solving: add one tough issue and your fix with measurable impact.\n"
            "- Time Management: show deadlines met, sprint delivery, or prioritization decisions.\n"
            "Use STAR style in one line: Situation + Action + Result (with numbers)."
        )

    if (intent == "interview_tips") or (asks_projects and (asks_interview or asks_presentation)):
        lines: List[str] = [
            "Use a 4-step structure for each project in interviews:",
            "- Problem: what real issue you solved and for whom.",
            "- Ownership: what exactly you designed or implemented.",
            "- Technical depth: architecture, trade-offs, and key decisions.",
            "- Outcome: measurable impact (latency, time saved, accuracy, adoption).",
        ]

        if projects:
            lines.append("")
            lines.append("For your resume projects, present them like this:")
            for item in projects[:3]:
                name = _clean_text(item.get("name"))
                summary_text = _clean_text(item.get("summary"))
                tech = item.get("technologies", []) if isinstance(item.get("technologies"), list) else []
                tech_line = ", ".join([_clean_text(t) for t in tech[:5] if _clean_text(t)])
                lines.append(f"- {name}: {_clip(summary_text, 170)}")
                if tech_line:
                    lines.append(f"  Tech to emphasize: {tech_line}")

        lines.extend([
            "",
            "Confidence tip: rehearse a 60-second and a 2-minute version of each project, then end with one challenge and how you solved it.",
        ])
        return "\n".join(lines)

    if (intent == "projects") or asks_projects:
        if projects:
            lines = ["Projects in your resume and how to present them briefly:"]
            for item in projects[:4]:
                name = _clean_text(item.get("name"))
                summary_text = _clean_text(item.get("summary"))
                tech = item.get("technologies", []) if isinstance(item.get("technologies"), list) else []
                tech_line = ", ".join([_clean_text(t) for t in tech[:5] if _clean_text(t)])
                lines.append(f"- {name}: {_clip(summary_text, 170)}")
                if tech_line:
                    lines.append(f"  Core tech: {tech_line}")
            lines.append("")
            lines.append("Keep a 60-second pitch ready for each project: problem, your implementation, and measurable outcome.")
            return "\n".join(lines)
        return "No project details were extracted from the current session resume text."

    if asks_matching:
        if asks_preparation:
            exact_part = "\n".join([f"- {s}" for s in exact[:10]]) if exact else "- No exact matches found in this session."
            sem_part = "\n".join([f"- {s}" for s in semantic[:6]]) if semantic else "- No semantic matches found in this session."
            return (
                "To become more confident with your existing matching skills, use this plan:\n\n"
                f"Core strengths to deepen:\n{exact_part}\n\n"
                f"Semantic strengths to convert into exact-strength narratives:\n{sem_part}\n\n"
                "Practice routine (free): 3 project walkthroughs/week, 2 mock interviews/week, and 1 revision pass to add measurable outcomes in resume bullets."
            )
        exact_part = "\n".join([f"- {s}" for s in exact[:12]]) if exact else "- No exact matches found in this session."
        sem_part = "\n".join([f"- {s}" for s in semantic[:8]]) if semantic else "- No semantic matches found in this session."
        return (
            f"Here are your matched skills from this session:\n\n"
            f"Exact matches ({len(exact)}):\n{exact_part}\n\n"
            f"Partial (semantic) matches ({len(semantic)}):\n{sem_part}\n\n"
            f"Overall alignment score: {score}%."
        )

    if asks_missing:
        if asks_resources:
            miss_part = "\n".join([f"- {s}" for s in missing[:10]]) if missing else "- No missing skills detected."
            resource_lines = "\n".join(_resource_suggestions_for_missing(missing, limit=8))
            return (
                f"These are your top missing skills:\n{miss_part}\n\n"
                "Free resources to improve them:\n"
                f"{resource_lines}\n\n"
                "Tip: pick 1 core backend skill + 1 platform skill weekly and build a mini project to prove learning."
            )
        miss_part = "\n".join([f"- {s}" for s in missing[:12]]) if missing else "- No missing skills detected."
        return (
            f"Top missing skills from this session ({len(missing)}):\n{miss_part}\n\n"
            f"Overall alignment score: {score}%"
        )

    return None


def _normalize_intent(intent: str | None) -> str:
    raw = _clean_text(intent or "general").lower().replace(" ", "_")
    if raw in ALLOWED_INTENTS:
        return raw
    return "general"


def _normalize_mode(mode: str | None) -> str:
    raw = _clean_text(mode or "resume_context").lower().replace(" ", "_")
    if raw in ALLOWED_MODES:
        return raw
    return "resume_context"


def _extract_decision_layer_insights(context: Dict[str, Any]) -> Dict[str, Any]:
    """Extract evidence from decision layers to ground responses in analysis."""
    decision_layers = context.get("decision_layers", {}) if isinstance(context.get("decision_layers"), dict) else {}
    candidate_layer = decision_layers.get("candidate", {}) if isinstance(decision_layers.get("candidate"), dict) else {}
    hr_layer = decision_layers.get("hr", {}) if isinstance(decision_layers.get("hr"), dict) else {}

    insights = {
        "candidate_strengths": [],
        "candidate_gaps": [],
        "hr_recommendations": [],
        "hiring_sentiment": "neutral",
        "priority_development_areas": [],
    }

    # Extract candidate layer insights
    if isinstance(candidate_layer.get("strengths"), list):
        insights["candidate_strengths"] = [_clean_text(s) for s in candidate_layer.get("strengths", [])[:5] if _clean_text(s)]

    if isinstance(candidate_layer.get("gaps"), list):
        insights["candidate_gaps"] = [_clean_text(g) for g in candidate_layer.get("gaps", [])[:5] if _clean_text(g)]

    if isinstance(candidate_layer.get("development_roadmap"), list):
        roadmap = candidate_layer.get("development_roadmap", [])
        insights["priority_development_areas"] = [_clean_text(item) for item in roadmap[:4] if _clean_text(item)]

    # Extract HR layer insights
    if isinstance(hr_layer.get("recommendations"), list):
        insights["hr_recommendations"] = [_clean_text(r) for r in hr_layer.get("recommendations", [])[:4] if _clean_text(r)]

    hiring_signal = hr_layer.get("hiring_signal")
    if hiring_signal:
        insights["hiring_sentiment"] = str(hiring_signal).lower()

    return insights


def _analyze_question_intent(question: str, intent: str) -> Dict[str, Any]:
    """Deep analyze question to determine emphasis areas and context priorities."""
    q_lower = _clean_text(question).lower()

    question_topics = {
        "strengths": {"patterns": [r"\bstrength", r"\bexcel", r"\bdo well", r"\bcompetent", r"\bexperience"], "keywords": ["strengths", "good at", "excel", "comfortable"]},
        "improvement": {"patterns": [r"\bimprove", r"\bweak", r"\bgap", r"\blearn", r"\bdevelop"], "keywords": ["improve", "weakness", "gap", "learn", "missing"]},
        "justification": {"patterns": [r"\bwhy", r"\bshow", r"\bprove", r"\bevidence", r"\bsupport"], "keywords": ["why", "how", "prove", "evidence", "show"]},
        "action": {"patterns": [r"\bhow to", r"\bactions?", r"\bsteps", r"\bplan", r"\broadmap"], "keywords": ["how to", "actions", "steps", "plan", "roadmap"]},
        "interview": {"patterns": [r"\binterview", r"\bpresentation", r"\bcommunicate", r"\bconfidence"], "keywords": ["interview", "present", "communicate", "practice"]},
        "ats": {"patterns": [r"\bats", r"\break through", r"\bkeyword", r"\boptimize"], "keywords": ["ats", "keyword", "screen", "parse"]},
    }

    topics_detected = {}
    for topic, config in question_topics.items():
        patterns_matched = sum(1 for pattern in config["patterns"] if re.search(pattern, q_lower))
        keywords_matched = sum(1 for kw in config["keywords"] if kw in q_lower)
        topics_detected[topic] = {"patterns": patterns_matched, "keywords": keywords_matched, "score": patterns_matched + keywords_matched * 0.5}

    return {
        "topics": {k: v["score"] for k, v in topics_detected.items()},
        "emphasis": max(topics_detected.items(), key=lambda x: x[1]["score"])[0] if topics_detected else "general",
        "depth_requested": "detailed" if len(question) > 120 else "concise",
    }


def _intent_directive(intent: str) -> str:
    """Detailed intent directives with emphasis on response structure and evidence grounding."""
    directives = {
        "matched_skills": (
            "CRITICAL: Provide a structured SKILLS REVISION ROUTINE using ONLY matched skills from the provided matched_skills_only list. "
            "⚠️  DO NOT reference ANY skills from previous sessions or make up skills. Use ONLY the skills provided in this session's analysis. "
            "1. Direct Answer: 2-4 sentences answering how to prepare/revise matched skills\n"
            "2. Skill Alignment Overview: List exact number of matched skills, top 3-5 skills with confidence scores from current session ONLY, overall alignment %, key strength areas\n"
            "3. Quick Revision Plan (7 days): 3-5 specific, actionable daily/weekly activities (Days 1-2, 3-4, etc.) using ONLY the matched skills provided\n"
            "4. Free Resources: 3-6 links in format '- [Skill]: [Resource](URL)' for proper markdown rendering, based ONLY on matched skills in this session\n"
            "5. Resume Context Reference: Show ONLY which exact skills matched in THIS session, their scores, and strategies to leverage in interviews\n"
            "GROUNDING: Every skill mentioned MUST be from matched_skills_only list. Do not include skills from previous analyses.\n"
            "MARKDOWN: Use **skill name** for bold skills, [Link](URL) for links. NEVER escape with backslashes."
        ),
        "missing_skills": (
            "CRITICAL: Provide a PRIORITIZED LEARNING ROADMAP using ONLY missing skills from the current session analysis. "
            "⚠️  DO NOT reference ANY skills from previous sessions or make up skills. Use ONLY the skills provided in missing_skills_only list from THIS session. "
            "1. Direct Answer: 2-4 sentences on gap-closing strategy\n"
            "2. Priority Skills Analysis: List total missing count FROM CURRENT SESSION ONLY, top 3 priority skills ranked by job relevance, time estimate per skill (weeks), alignment impact\n"
            "3. 30/60/90 Day Roadmap: Three subsections with 2-3 weekly timed steps each; explicitly link each to specific missing skills FROM THIS SESSION ONLY\n"
            "4. Mini Project Plan: 1-2 projects that teach multiple missing skills (FROM THIS SESSION ONLY); include tech stack, time investment, learning outcomes\n"
            "5. Resume Context Reference: Show missing skill count FROM THIS SESSION ONLY, priority ranking, learning timelines, expected alignment score improvement\n"
            "GROUNDING: Every skill mentioned MUST be from missing_skills_only list. Do not include skills from previous analyses.\n"
            "MARKDOWN: Use **Skill Name** for emphasis. Use ### for subsections (Days 1-30). NEVER escape with backslashes."
        ),
        "projects": (
            "Answer with PROJECT STORYTELLING FRAMEWORK using extracted projects. "
            "MUST use only project names and technologies available in resume context. "
            "NEVER invent project names, technologies, outcomes, or company examples. "
            "If no projects are present in resume context, explicitly state that and provide only a generic STAR/PAR template. "
            "Teach STAR/PAR structure and show how to map candidate's actual projects to skill demonstration. "
            "Structure: [Direct Answer] → [Project Story Framework] → [Your Projects with Skills Map] → [Sample Pitch] → [Resume Context Reference]"
        ),
        "interview_tips": (
            "Answer with CONFIDENCE-BUILDING STRATEGIES tied to soft skills and projects. "
            "MUST reference detected soft skills and project evidence. "
            "Provide 60-second and 2-minute talking points, behavioral frames, and practice routines. "
            "Structure: [Direct Answer] → [Soft Skills Strengths] → [60-Second Pitch Template] → [Practice Routine] → [Resume Context Reference]"
        ),
        "resume_improvements": (
            "Answer with ATS-FOCUSED IMPROVEMENTS tied to alignment score and missing keywords. "
            "MUST reference specific missing skills from JD and show before/after bullet improvements. "
            "Provide concrete rewrites, keyword additions, and metric injection strategies. "
            "Structure: [Direct Answer] → [Current Alignment Analysis] → [ATS Issues to Fix] → [Before/After Examples] → [Resume Context Reference]"
        ),
        "general": "Answer the user question directly without resume context reference.",
    }
    return directives.get(intent, "Use the selected intent semantics to guide your answer, but prioritize answering the exact question.")


def _question_keywords(question: str, limit: int = 12) -> List[str]:
    text = _clean_text(question).lower()
    terms = re.findall(r"[a-z][a-z0-9+#.\-]{2,}", text)
    seen = set()
    out: List[str] = []
    for term in terms:
        if term in seen:
            continue
        seen.add(term)
        out.append(term)
        if len(out) >= limit:
            break
    return out


def _prioritize_by_question(items: List[str], question: str, limit: int = 8) -> List[str]:
    keywords = _question_keywords(question)
    scored = []
    for item in items or []:
        text = _clean_text(item)
        if not text:
            continue
        low = text.lower()
        score = sum(1 for k in keywords if k in low)
        scored.append((score, text))
    scored.sort(key=lambda x: (-x[0], x[1]))
    out = [text for _, text in scored[:limit]]
    return out


def _project_reference_items(context: Dict[str, Any], limit: int = 4) -> List[Dict[str, Any]]:
    profile = context.get("candidate_profile", {}) if isinstance(context.get("candidate_profile"), dict) else {}
    projects = profile.get("projects", []) if isinstance(profile.get("projects"), list) else []
    out: List[Dict[str, Any]] = []
    for project in projects[:limit]:
        if not isinstance(project, dict):
            continue
        name = _clean_text(project.get("name"))
        if not name:
            continue
        summary = _clip(_clean_text(project.get("summary")), 180)
        tech = project.get("technologies", []) if isinstance(project.get("technologies"), list) else []
        out.append({
            "name": name,
            "summary": summary,
            "technologies": [_clean_text(t) for t in tech[:6] if _clean_text(t)],
        })
    return out


def _project_names_from_context(context: Dict[str, Any], limit: int = 8) -> List[str]:
    names: List[str] = []
    seen = set()
    for item in _project_reference_items(context, limit=limit):
        name = _clean_text(item.get("name"))
        if not name:
            continue
        low = name.lower()
        if low in seen:
            continue
        seen.add(low)
        names.append(name)
        if len(names) >= limit:
            break
    return names


def _is_projects_answer_grounded(answer: str, context: Dict[str, Any]) -> bool:
    project_names = _project_names_from_context(context, limit=8)
    if not project_names:
        return True

    answer_low = _clean_text(answer).lower()
    has_known_project = any(_clean_text(name).lower() in answer_low for name in project_names)
    if not has_known_project:
        return False

    suspicious = [
        "e-commerce website development",
        "machine learning model deployment",
        "to-do list app",
        "personal project chatbot",
    ]
    known_tokens = {_clean_text(name).lower() for name in project_names}
    for token in suspicious:
        if token in answer_low and token not in known_tokens:
            return False

    return True


def _matched_skills_from_context(context: Dict[str, Any]) -> List[str]:
    """Extract matched skills (exact + semantic + implicit + contextually validated) from current session context."""
    findings = context.get("key_findings", {}) if isinstance(context.get("key_findings"), dict) else {}
    exact = findings.get("exact_matches", []) if isinstance(findings.get("exact_matches"), list) else []
    
    skills = list(exact)
    # Include taxonomy semantic matches
    semantic = findings.get("semantic_matches", []) if isinstance(findings.get("semantic_matches"), list) else []
    for item in semantic:
        if isinstance(item, str):
            parts = item.split(" -> ")
            if len(parts) > 0:
                skill_name = parts[0].strip()
                if skill_name and skill_name.lower() not in [s.lower() for s in skills]:
                    skills.append(skill_name)
    
    # Also include implicit matches and contextually validated from context analysis
    ctx_findings = context.get("context_analysis_findings", {}) if isinstance(context.get("context_analysis_findings"), dict) else {}
    for group_key in ["implicit_matches", "contextually_validated"]:
        for item in ctx_findings.get(group_key, []) or []:
            skill_name = ""
            if isinstance(item, dict):
                skill_name = _clean_text(item.get("skill", ""))
            elif isinstance(item, str):
                skill_name = _clean_text(item.split(":")[0])
            if skill_name and skill_name.lower() not in [s.lower() for s in skills]:
                skills.append(skill_name)
    
    return skills[:20]


def _missing_skills_from_context(context: Dict[str, Any]) -> List[str]:
    """Extract missing skills from taxonomy analysis AND actual_gaps from context analysis."""
    findings = context.get("key_findings", {}) if isinstance(context.get("key_findings"), dict) else {}
    missing = findings.get("missing_skills", []) if isinstance(findings.get("missing_skills"), list) else []
    
    # Extract skill names from taxonomy missing skills list
    skills = []
    for item in missing:
        if isinstance(item, dict):
            skill_name = item.get("skill", "").strip()
        else:
            skill_name = str(item).strip()
        if skill_name and skill_name.lower() not in [s.lower() for s in skills]:
            skills.append(skill_name)
    
    # Also include actual_gaps from context analysis
    ctx_findings = context.get("context_analysis_findings", {}) if isinstance(context.get("context_analysis_findings"), dict) else {}
    for item in ctx_findings.get("actual_gaps", []) or []:
        skill_name = ""
        if isinstance(item, dict):
            skill_name = _clean_text(item.get("skill", ""))
        elif isinstance(item, str):
            skill_name = _clean_text(item.split(":")[0])
        if skill_name and skill_name.lower() not in [s.lower() for s in skills]:
            skills.append(skill_name)
    
    return skills[:16]


def _is_missing_skills_answer_grounded(answer: str, context: Dict[str, Any]) -> bool:
    """Validate that missing_skills answer only references skills from current session analysis."""
    missing_skills = _missing_skills_from_context(context)
    if not missing_skills:
        return True
    
    answer_low = _clean_text(answer).lower()
    # Check if at least one missing skill is mentioned in answer
    has_known_skill = any(_clean_text(skill).lower() in answer_low for skill in missing_skills)
    if not has_known_skill:
        return False
    
    # Check for hallucinated skills (common false positives from software domain)
    suspicious_skills = [
        "docker", "kubernetes", "aws", "azure", "gcp", "distributed systems",
        "microservices", "cloud architecture", "ci/cd", "github actions",
        "rabbitmq", "apache kafka", "node.js", "python", "java", "golang",
        "react", "angular", "vue.js", "system design",
    ]
    known_tokens = {_clean_text(skill).lower() for skill in missing_skills}
    for token in suspicious_skills:
        if token in answer_low and token not in known_tokens:
            return False
    
    return True


def _is_matched_skills_answer_grounded(answer: str, context: Dict[str, Any]) -> bool:
    """Validate that matched_skills answer only references skills from current session analysis."""
    matched_skills = _matched_skills_from_context(context)
    if not matched_skills:
        return True
    
    answer_low = _clean_text(answer).lower()
    # Check if at least one matched skill is mentioned in answer
    has_known_skill = any(_clean_text(skill).lower() in answer_low for skill in matched_skills)
    if not has_known_skill:
        return False
    
    # Check for hallucinated skills (common false positives)
    suspicious_skills = [
        "java", "javascript", "python", "docker", "kubernetes", "aws", "azure",
        "react", "node.js", "sql", "mongodb", "golang", "rust",
        "devops", "microservices", "system design", "distributed systems",
    ]
    known_tokens = {_clean_text(skill).lower() for skill in matched_skills}
    for token in suspicious_skills:
        if token in answer_low and token not in known_tokens:
            return False
    
    return True


def _intent_output_contract(intent: str) -> str:
    """Strict output contracts specifying exact expectations for each intent."""
    contracts = {
        "matched_skills": (
            "STRUCTURE (required): 5 sections with exact markdown headings: '## Direct Answer', '## Skill Alignment Overview', '## Quick Revision Plan (7 days)', '## Free Resources', '## Resume Context Reference'\n"
            "CRITICAL GROUNDING RULE: Use ONLY skills from the 'matched_skills_only' list provided. Do NOT mention any skills from previous sessions or sessions not in the current analysis.\n"
            "CONTENT RULES:\n"
            "1. Direct Answer: 2-4 sentences answering without any resume data\n"
            "2. Skill Alignment Overview: bullets showing (a) total exact matches count from THIS SESSION ONLY, (b) top 3-5 matched skills from matched_skills_only with confidence/score, (c) overall alignment %, (d) key strength area\n"
            "3. Quick Revision Plan: 3-5 specific actionable items (Day 1-2, Day 3-4, etc.) using ONLY matched skills from matched_skills_only list; include concrete activities like coding platform names or project types\n"
            "4. Free Resources: 3-6 resource links based ONLY on matched skills in THIS SESSION; REQUIRED FORMAT: '- Skill Name: [Link Title](URL)' to ensure markdown links render properly (NOT **[Link]**))\n"
            "5. Resume Context Reference: header + 5-7 bullets showing matched skills FROM THIS SESSION ONLY, scores, interview leveraging strategies, and recommended depths\n"
            "GROUNDING VALIDATION: Every single skill mentioned MUST appear in matched_skills_only list. Do not hallucinate or reference skills from other sessions.\n"
            "MARKDOWN RULES (CRITICAL):\n"
            "- NEVER escape asterisks with backslashes (\\*); use plain ** for bold\n"
            "- Use format: **exact skill name from matched_skills_only** for bold skill names (no escaping)\n"
            "- Use [Link Text](URL) for markdown links in Free Resources section\n"
            "- Use - [item]: value format for key-value bullets\n"
            "SEPARATOR RULE (required): Include '---' on its own line before Resume Context Reference section\n"
            "TONE: Encouraging and practical, focus on deepening existing matched strengths\n"
            "VALIDATION: Every skill mention uses a skill from matched_skills_only. No generic skill references. No skills from previous sessions."
        ),
        "missing_skills": (
            "STRUCTURE (required): 5 sections with exact markdown headings: '## Direct Answer', '## Priority Skills Analysis', '## 30/60/90 Day Roadmap', '## Mini Project Plan', '## Resume Context Reference'\n"
            "CRITICAL GROUNDING RULE: Use ONLY skills from the 'missing_skills_only' list provided. Do NOT mention any skills from previous sessions or sessions not in the current analysis.\n"
            "CONTENT RULES:\n"
            "1. Direct Answer: 2-4 sentences directly addressing skill gap closure\n"
            "2. Priority Skills Analysis: bullets listing (a) total missing count FROM THIS SESSION ONLY, (b) Priority 1/2/3 with skills from missing_skills_only ranked by job relevance, (c) learning time estimate per skill (weeks), (d) expected alignment score impact\n"
            "3. 30/60/90 Day Roadmap: three labeled subsections (Days 1-30 / Days 31-60 / Days 61-90) with 2-3 timed steps each; explicitly link ONLY to specific missing skills from missing_skills_only; include weekly breakdown\n"
            "4. Mini Project Plan: 1-2 projects with (a) project idea, (b) tech stack, (c) which missing skills it teaches (ONLY from missing_skills_only), (d) time investment estimate\n"
            "5. Resume Context Reference: header + 6-8 bullets listing top missing skills FROM THIS SESSION ONLY, learning timeline, and effort estimates\n"
            "GROUNDING VALIDATION: Every single skill mentioned MUST appear in missing_skills_only list. Do not hallucinate or reference skills from other sessions.\n"
            "MARKDOWN RULES (CRITICAL):\n"
            "- NEVER escape asterisks; use plain ** for bold\n"
            "- Use format: **Skill Name from missing_skills_only** for bold skill references\n"
            "- Use ### for subsection headings (Days 1-30, etc.)\n"
            "- AVOID ** in summary bullets; use bold for emphasis only in main content\n"
            "SEPARATOR RULE (required): Include '---' on its own line before Resume Context Reference section\n"
            "TONE: Motivating and strategic; emphasize progress milestones and concrete skill-building\n"
            "MUST VALIDATE: Every skill mentioned uses a skill from missing_skills_only. No generic skill references. No skills from previous sessions. Time estimates realistic (2-6 weeks)"
        ),
        "projects": (
            "STRUCTURE (required): 4 sections with exact markdown headings: '## Direct Answer', '## Project Story Framework (STAR/PAR)', '## How To Showcase Your Skills In Each Project', '## Resume Context Reference'\n"
            "CONTENT RULES:\n"
            "1. Direct Answer: 2-4 sentences directly answering how to present projects\n"
            "2. Project Story Framework: explain STAR or PAR method with 1-2 sentence examples\n"
            "3. How To Showcase: include ONLY candidate's actual project names and technologies from resume context, map each to 2-3 core skills\n"
            "4. Resume Context Reference: header + 3-5 bullets listing candidate's projects with tech stack and recommended skill emphasis\n"
            "SEPARATOR RULE (required): Include '---' on its own line before Resume Context Reference section\n"
            "TONE: Confident and structured, focus on compelling narratives\n"
            "MUST VALIDATE: Uses only actual candidate project names and technologies provided in resume context; no fabricated projects"
        ),
        "interview_tips": (
            "STRUCTURE (required): 4 sections with exact markdown headings: '## Direct Answer', '## Confidence Building Practice', '## Sample Answer Frames', '## Resume Context Reference'\n"
            "CONTENT RULES:\n"
            "1. Direct Answer: 2-4 sentences addressing the interview question\n"
            "2. Confidence Building Practice: 3-5 bulleted practice exercises tied to detected soft skills\n"
            "3. Sample Answer Frames: provide 2-3 behavioral answer templates (60-second and 2-minute versions)\n"
            "4. Resume Context Reference: header + 3-5 bullets listing soft skills, interview focus from analysis, sample projects to discuss\n"
            "SEPARATOR RULE (required): Include '---' on its own line before Resume Context Reference section\n"
            "TONE: Motivating and coaching-like, build confidence through practice\n"
            "MUST VALIDATE: At least 2 soft skills from context are referenced in practice exercises or sample frames"
        ),
        "resume_improvements": (
            "STRUCTURE (required): 4 sections with exact markdown headings: '## Direct Answer', '## ATS Optimization Actions', '## Before/After Bullet Improvements', '## Resume Context Reference'\n"
            "CONTENT RULES:\n"
            "1. Direct Answer: 2-4 sentences directly addressing resume improvement\n"
            "2. ATS Optimization Actions: 4-6 specific actions (keyword injection, formatting, structure fixes) tied to missing keywords from JD\n"
            "3. Before/After Bullet Improvements: show 2-3 concrete before/after resume bullet rewrites with metrics\n"
            "4. Resume Context Reference: header + bullets showing current alignment score, top missing keywords, priority improvement areas\n"
            "SEPARATOR RULE (required): Include '---' on its own line before Resume Context Reference section\n"
            "TONE: Direct and actionable, focus on ATS parsing and keyword coverage\n"
            "MUST VALIDATE: Before/After examples use specific missing skills or keywords from context"
        ),
    }
    return contracts.get(intent, (
        "Structure response with clear markdown headings. Use bullet points for readability. "
        "Include a '---' separator before 'Resume Context Reference' section. "
        "Keep sections concise and avoid dense paragraphs."
    ))


def _intent_response_template(intent: str) -> Dict[str, Any]:
    """Enhanced templates with detailed structure guidance and examples."""
    templates: Dict[str, Dict[str, Any]] = {
        "matched_skills": {
            "title": "Matched Skills — Deep Revision Routine",
            "sections": [
                "Direct Answer",
                "Skill Alignment Overview",
                "Quick Revision Plan (7 days)",
                "Free Resources",
                "Resume Context Reference",
            ],
            "format_guidance": {
                "Direct Answer": "2-4 sentences directly answering without resume data",
                "Skill Alignment Overview": "Structured bullets: (1) exact matched skill count, (2) top 3-5 matched skills with confidence, (3) alignment percentage, (4) key strengths",
                "Quick Revision Plan (7 days)": "3-5 specific actionable items (daily/weekly) using matched skills; include concrete exercises, coding platforms, or projects",
                "Free Resources": "3-6 resource links specific to matched skills; format as: '- [Skill]: [Resource Title](URL)' for proper markdown rendering",
                "Resume Context Reference": "Header + 5-7 bullets: (1) exact matched count, (2) top skills with scores, (3) leveraging in interviews, (4) depth-building areas",
            },
            "example_structure": "## Direct Answer\nYour matched skills provide a strong foundation. Here's how to deepen them:\n\n## Skill Alignment Overview\n- Exact Matched Skills: 9 core technical requirements\n- Top Skills: Java, JavaScript, Python, Data Structures and Algorithms, Git\n- Overall Alignment Score: 44%\n- Key Strength: Strong fundamentals in problem-solving and full-stack development\n\n## Quick Revision Plan (7 days)\n- Day 1-2: LeetCode medium problems using Java/Python\n- Day 3-4: Build a Git-based JavaScript project\n\n## Free Resources\n- Java Fundamentals: [FreeCodeCamp Java Course](https://www.freecodecamp.org/learn/java/)\n- JavaScript: [JavaScript.Info Tutorial](https://javascript.info/)\n\n---\n\n## Resume Context Reference\nYour analysis shows:",
            "emphasis": "Specific skill names with confidence scores; actionable daily activities",
        },
        "missing_skills": {
            "title": "Missing Skills — Phased Mastery Plan",
            "sections": [
                "Direct Answer",
                "Priority Skills Analysis",
                "30/60/90 Day Roadmap",
                "Mini Project Plan",
                "Resume Context Reference",
            ],
            "format_guidance": {
                "Direct Answer": "2-4 sentences directly addressing gap closure",
                "Priority Skills Analysis": "Structured bullets listing: (1) total missing skills, (2) top 3 priority skills (ranked by job relevance), (3) learning time estimate per skill, (4) impact on role fit",
                "30/60/90 Day Roadmap": "Three subsections with 2-3 concrete, timed steps each; explicitly link each to missing skills; include specific resources and milestones",
                "Mini Project Plan": "1-2 mini-projects that demonstrate multiple missing skills; include tech stack, learning outcomes, and time investment",
                "Resume Context Reference": "Header + 6-8 bullets: (1) missing skill count, (2) top priority skills ranked, (3) learning time estimates, (4) expected impact on alignment score",
            },
            "example_structure": "## Direct Answer\nYou're missing key skills like Distributed Systems, Microservices, and Docker. Here's a structured path to close the gaps:\n\n## Priority Skills Analysis\n- Missing Skills Count: 6 critical areas\n- Priority 1 (High Impact): Docker, CI/CD - 2-3 weeks per skill\n- Priority 2 (Medium Impact): Microservices, System Design - 3-4 weeks per skill\n- Priority 3 (Building): Azure, Distributed Systems - 4-6 weeks per skill\n- Current Alignment Impact: Estimated +20% with Priority 1 skills\n\n## 30/60/90 Day Roadmap\n### Days 1-30: Foundation (Docker + CI/CD)\n- Week 1: Docker fundamentals - containers, images, Docker Compose\n- Week 2-3: GitHub Actions/GitLab CI hands-on practice\n- Week 4: Build a CI/CD pipeline for a sample app\n\n### Days 31-60: Design Thinking (System Design + Microservices)\n- Week 5-6: System Design fundamentals (scaling, databases, APIs)\n- Week 7: Microservices architecture patterns\n- Week 8: Design a microservices-based system\n\n### Days 61-90: Cloud & Distribution (Azure + Distributed Systems)\n- Week 9-10: Azure cloud fundamentals\n- Week 11: Distributed systems concepts\n- Week 12: Real-time project applying all three\n\n## Mini Project Plan\n1. Build a dockerized multi-service app (Node.js backend + Python worker) with GitHub Actions CI/CD\n   - Learn: Docker, Docker Compose, CI/CD, containerization\n   - Time: 2 weeks\n2. Deploy microservices on Azure with system design considerations\n   - Learn: Microservices, System Design, Azure, cloud architecture\n   - Time: 3 weeks\n\n---\n\n## Resume Context Reference\nYour analysis shows:",
            "emphasis": "Clear prioritization; realistic learning timeline; measurable skill progression",
        },
        "projects": {
            "title": "Projects — Skill Showcase Strategy",
            "sections": [
                "Direct Answer",
                "Project Story Framework (STAR/PAR)",
                "How To Showcase Your Skills In Each Project",
                "Resume Context Reference",
            ],
            "format_guidance": {
                "Direct Answer": "2-4 sentences answering how to present projects",
                "Project Story Framework (STAR/PAR)": "Explain STAR or PAR with 1-2 sentence examples; distinguish situation, action, result",
                "How To Showcase Your Skills In Each Project": "Use only candidate's actual project names and technologies from resume context; map each project to 2-3 core skills",
                "Resume Context Reference": "Header + 3-5 bullets listing candidate's projects (from resume context), tech stack, and skill emphasis",
            },
            "example_structure": "## Direct Answer\nPresenting projects effectively means storytelling plus technical depth:\n\n## Project Story Framework (STAR/PAR)\n**STAR Method**: Situation → Task → Action → Result\n\n## How To Showcase Your Skills In Each Project\nYour [project name] (Technologies: [tech]) demonstrates:\n- [Skill 1]: ...\n\n---\n\n## Resume Context Reference\nYour detected projects:",
            "emphasis": "Narrative clarity and skill mapping",
        },
        "interview_tips": {
            "title": "Interview Tips — Confidence & Practice",
            "sections": [
                "Direct Answer",
                "Confidence Building Practice",
                "Sample Answer Frames",
                "Resume Context Reference",
            ],
            "format_guidance": {
                "Direct Answer": "2-4 sentences addressing interview challenges",
                "Confidence Building Practice": "3-5 practice exercises tied to soft skills; format as actionable drills",
                "Sample Answer Frames": "2-3 behavioral answer templates with 60-second and 2-minute versions",
                "Resume Context Reference": "Header + 3-5 bullets listing soft skills (from analysis), practice projects, confidence boosters",
            },
            "example_structure": "## Direct Answer\nInterview success comes from preparing [soft skill] stories:\n\n## Confidence Building Practice\n1. Project walkthrough drill: 60-second version of your [project]\n   - Situation: [one sentence]\n   - Solution: [one sentence]\n   - Impact: [one sentence]\n\n## Sample Answer Frames\n**60-Second Version** (for questions like 'Tell me about yourself')\n\n**2-Minute Version** (for group interviews)\n\n---\n\n## Resume Context Reference\nYour soft skills strengths:",
            "emphasis": "Practice routines and behavioral confidence",
        },
        "resume_improvements": {
            "title": "Resume Improvements — ATS & Keywords",
            "sections": [
                "Direct Answer",
                "ATS Optimization Actions",
                "Before/After Bullet Improvements",
                "Resume Context Reference",
            ],
            "format_guidance": {
                "Direct Answer": "2-4 sentences directly addressing resume improvement",
                "ATS Optimization Actions": "4-6 specific actions (keyword injection, section ordering, formatting); tie each to missing keywords",
                "Before/After Bullet Improvements": "2-3 concrete before→after resume bullet rewrites with metrics and keywords",
                "Resume Context Reference": "Header + bullets showing current alignment score, top missing keywords, priority areas from JD",
            },
            "example_structure": "## Direct Answer\nYour resume is [X]% aligned to the JD. Key improvement areas:\n\n## ATS Optimization Actions\n1. Inject these keywords in your skills section: [keywords]\n2. Reorder bullets to frontload [skills]\n\n## Before/After Bullet Improvements\n**Before**: Worked on cloud infrastructure\n**After**: Led cloud infrastructure migrations using Docker & Kubernetes, reducing deployment time by 40%\n\n---\n\n## Resume Context Reference\nCurrent alignment: [score]%\nTop missing skills: [skills]\nTop missing keywords: [keywords]",
            "emphasis": "Practical keyword coverage and metric injection",
        },
    }
    return templates.get(intent, {
        "title": "Answer",
        "sections": ["Direct Answer", "Resume Context Reference"],
        "format_guidance": {"Direct Answer": "Answer directly", "Resume Context Reference": "Reference relevant context"},
        "emphasis": "Clarity and relevance",
    })


def _validate_response_structure(response: str, intent: str, template: Dict[str, Any]) -> Dict[str, Any]:
    """Validate that response matches expected structure and identify missing sections."""
    sections = template.get("sections", [])
    response_lower = response.lower()
    
    found_sections = {}
    for section in sections:
        section_pattern = re.escape(section).lower()
        if re.search(rf"#{{{1,3}}}\s*{section_pattern}|{section_pattern}", response_lower):
            found_sections[section] = True
        else:
            found_sections[section] = False

    has_separator = bool(re.search(r"---", response))
    section_count = len([s for s in found_sections.values() if s])
    min_sections_expected = len(sections) - 1  # Allow one missing section
    
    is_valid = (
        section_count >= min_sections_expected and
        (has_separator or "Resume Context Reference" in response)
    )

    return {
        "is_valid": is_valid,
        "found_sections": found_sections,
        "section_count": section_count,
        "expected_sections": len(sections),
        "has_separator": has_separator,
        "quality_score": section_count / len(sections) if sections else 1.0,
    }


def _build_intent_reference_context(intent: str, question: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Build intent-specific context with decision layer insights and evidence grounding."""
    summary = context.get("summary", {}) if isinstance(context.get("summary"), dict) else {}
    findings = context.get("key_findings", {}) if isinstance(context.get("key_findings"), dict) else {}
    inventory = context.get("skills_inventory", {}) if isinstance(context.get("skills_inventory"), dict) else {}
    guidance = context.get("ai_guidance", {}) if isinstance(context.get("ai_guidance"), dict) else {}
    decision_insights = _extract_decision_layer_insights(context)

    exact = findings.get("exact_matches", []) if isinstance(findings.get("exact_matches"), list) else []
    semantic = findings.get("semantic_matches", []) if isinstance(findings.get("semantic_matches"), list) else []
    missing = findings.get("missing_skills", []) if isinstance(findings.get("missing_skills"), list) else []
    resume_tech = inventory.get("resume_technical", []) if isinstance(inventory.get("resume_technical"), list) else []
    resume_soft = inventory.get("resume_soft", []) if isinstance(inventory.get("resume_soft"), list) else []

    matched_ranked = _prioritize_by_question(exact or resume_tech, question, limit=8)
    missing_ranked = _prioritize_by_question(missing, question, limit=8)
    
    question_analysis = _analyze_question_intent(question, intent)

    base = {
        "summary": {
            "overall_alignment_score": summary.get("overall_alignment_score", 0),
            "exact_match_count": summary.get("exact_match_count", 0),
            "semantic_match_count": summary.get("semantic_match_count", 0),
            "missing_skills_count": summary.get("missing_skills_count", 0),
            "total_jd_skills": summary.get("total_jd_skills", 0),
        },
        "matched_skills_focus": matched_ranked[:8],
        "missing_skills_focus": missing_ranked[:8],
        "soft_skills_focus": _prioritize_by_question(resume_soft, question, limit=6),
        "semantic_evidence": semantic[:6],
        "project_references": _project_reference_items(context, limit=4),
        "interview_focus": guidance.get("interview_focus", [])[:6] if isinstance(guidance.get("interview_focus"), list) else [],
        "top_recommendations": guidance.get("top_recommendations", [])[:6] if isinstance(guidance.get("top_recommendations"), list) else [],
        "decision_layer_insights": decision_insights,
        "question_analysis": question_analysis,
    }

    if intent == "matched_skills":
        resources = _resource_suggestions_for_missing(base["matched_skills_focus"][:6], limit=6)
        base["free_revision_resources"] = resources
        base["emphasis"] = "Deepen existing strength areas with targeted practice"
    elif intent == "missing_skills":
        base["free_gap_resources"] = _resource_suggestions_for_missing(base["missing_skills_focus"][:8], limit=8)
        base["emphasis"] = "Close capability gaps with structured learning plan"
    elif intent == "projects":
        base["emphasis"] = "Showcase skills through project narrative and architecture"
    elif intent == "interview_tips":
        base["emphasis"] = "Build confidence through soft skill awareness and practice"
    elif intent == "resume_improvements":
        base["emphasis"] = f"Improve from {summary.get('overall_alignment_score', 0)}% alignment through ATS optimization"

    return base


def _build_minimal_context(full_context: Dict[str, Any]) -> Dict[str, Any]:
    """Extract essential context grounded in session analysis: summary stats, skill inventory, projects, and decision layers."""
    decision_layers = full_context.get("decision_layers", {}) if isinstance(full_context.get("decision_layers"), dict) else {}
    
    return {
        "session": full_context.get("session", {}),
        "summary": full_context.get("summary", {}),
        "key_findings": full_context.get("key_findings", {}),
        "context_analysis_findings": full_context.get("context_analysis_findings", {}),
        "skills_inventory": full_context.get("skills_inventory", {}),
        "ai_guidance": full_context.get("ai_guidance", {}),
        "candidate_profile": {"projects": _project_reference_items(full_context, limit=4)},
        "decision_layers": {
            "candidate": decision_layers.get("candidate", {}),
            "hr": decision_layers.get("hr", {}),
        },
    }


def ask_contextual_chat(
    *,
    question: str,
    context: Dict[str, Any],
    history: List[Dict[str, str]] | None = None,
    intent: str = "general",
    mode: str = "resume_context",
) -> Dict[str, Any]:
    history = history or []
    normalized_intent = _normalize_intent(intent)
    normalized_mode = _normalize_mode(mode)

    enabled = os.getenv("CHATBOT_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
    configured_model = (os.getenv("CHATBOT_GROQ_MODEL") or os.getenv("GROQ_MODEL") or DEFAULT_MODEL).strip()
    fallback_model = (os.getenv("CHATBOT_GROQ_FALLBACK_MODEL") or DEFAULT_MODEL).strip()
    current_model = configured_model
    switched_to_fallback = False
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    groq_url = (os.getenv("CHATBOT_GROQ_URL") or os.getenv("GROQ_API_URL") or GROQ_URL).strip()

    if not enabled:
        return {
            "status": "disabled",
            "answer": "Chatbot is disabled in server config.",
            "model": current_model,
            "intent_used": normalized_intent,
            "mode_used": normalized_mode,
            "grounded": True,
            "warning": "CHATBOT_ENABLED is false",
        }

    if not api_key:
        return {
            "status": "disabled",
            "answer": "Chatbot is not configured because GROQ_API_KEY is missing on the backend.",
            "model": current_model,
            "intent_used": normalized_intent,
            "mode_used": normalized_mode,
            "grounded": True,
            "warning": "Missing GROQ_API_KEY",
        }

    timeout_sec = max(5.0, min(45.0, _to_float(os.getenv("CHATBOT_TIMEOUT_SEC", "12"), 12.0)))
    temperature = max(0.0, min(1.0, _to_float(os.getenv("CHATBOT_TEMPERATURE", "0.2"), 0.2)))
    max_tokens = int(max(180, min(1200, _to_float(os.getenv("CHATBOT_MAX_TOKENS", "520"), 520))))
    max_retries = int(max(0, min(3, _to_float(os.getenv("CHATBOT_MAX_RETRIES", "2"), 2))))

    if normalized_mode == "general":
        # For general mode, reduce max_tokens to encourage medium-length, compact responses
        max_tokens = min(max_tokens, 450)
        system_prompt = (
            "You are a concise and practical assistant for skills, jobs, and general career questions. "
            "Do not reference any resume analysis session context. "
            "CRITICAL FORMAT: Respond primarily as bullet points, not dense paragraphs. "
            "Provide around 6 to 8 concise bullet points that fully answer the question. "
            "Each bullet should be practical, specific, and easy to scan (1-2 lines each). "
            "Keep the response moderate in length, direct, and complete without unnecessary elaboration. "
            "Use clear markdown and short optional heading only if it improves readability."
        )
    else:
        response_template = _intent_response_template(intent)
        template_example = response_template.get("example_structure", "")
        system_prompt = (
            "You are an expert career coaching assistant with access to a COMPLETE resume analysis. "
            "\n\n"
            "## YOUR DATA SOURCES (use ALL of them together):\n"
            "1. resume_raw_text — the candidate's actual resume content\n"
            "2. jd_raw_text — the full job description\n"
            "3. taxonomy_key_findings — exact and semantic skill matches from rule-based analysis\n"
            "4. context_analysis_findings — deep NLU analysis results:\n"
            "   - implicit_matches: skills the candidate has but expressed differently\n"
            "   - contextually_validated: skills confirmed through project/experience context\n"
            "   - actual_gaps: confirmed missing skills after NLU analysis\n"
            "   - additional_skills: candidate has these but JD didn't ask for them\n"
            "\n\n"
            "## YOUR PRIMARY MISSION:\n"
            "Answer the user's exact question clearly, directly, and practically. Your answer must be:\n"
            "- Grounded ONLY in the provided resume raw text, JD raw text, taxonomy findings, and context analysis\n"
            "- When discussing strengths/matched skills: include BOTH exact matches AND implicit/contextually validated skills\n"
            "- When discussing gaps: reference BOTH taxonomy missing_skills AND context_analysis actual_gaps\n"
            "- Structured in the EXACT markdown format specified below\n"
            "- Action-oriented and specific (not generic)\n"
            "\n\n"
            "## RESPONSE STRUCTURE (MANDATORY):\n"
            f"{_intent_output_contract(normalized_intent)}\n\n"
            "## FORMATTING RULES (CRITICAL - PREVENT ESCAPING):\n"
            "1. Use exact section headings specified in response_structure_template (with ## markdown)\n"
            "2. MARKDOWN LINKS: Use [Link Text](URL) format for all external links\n"
            "3. BOLD TEXT: Use **text** for bold emphasis - NEVER escape with backslashes\n"
            "4. Answer main content FIRST, then add separator '---' on its own line\n"
            "5. After separator, add 'Resume Context Reference:' section showing which analysis data supports your answer\n"
            "6. Use concise bullet points for readability; avoid dense paragraphs\n"
            "7. Keep output compact but informative: prefer short, structured sections with mostly bullet points\n"
            "8. For skill names in bullets: use **Skill Name** format for emphasis\n"
            "9. For key metrics, use format: - Metric: value\n"
            "10. For numbered lists, use: 1. item, 2. item format\n"
            "\n\n"
            "## EXAMPLE STRUCTURE FOR THIS INTENT:\n"
            f"{template_example}\n\n"
            "## EVIDENCE GROUNDING:\n"
            "- Ground claims in resume_raw_text, jd_raw_text, taxonomy_key_findings, and context_analysis_findings\n"
            "- Implicit matches and contextually validated skills are REAL confirmed skills, treat them as strengths\n"
            "- In Resume Context Reference, cite which data source supports each claim\n"
            f"- Emphasis: {response_template.get('emphasis', 'Practical and specific')}\n"
            "- Avoid generic advice; personalize to candidate's actual skills and analysis results\n"
            "- Be direct; avoid disclaimers and hedging language\n"
        )
    intent_hint = _intent_directive(normalized_intent)

    history_mode = _clean_text(os.getenv("CHATBOT_HISTORY_MODE", "off")).lower()
    compact_history = []
    if history_mode in {"on", "limited"}:
        for turn in history[-4:]:
            if not isinstance(turn, dict):
                continue
            role = str(turn.get("role", "")).strip().lower()
            content = _clip(turn.get("content", ""), 500)
            if role not in {"user", "assistant"} or not content:
                continue
            compact_history.append({"role": role, "content": content})

    if normalized_mode == "general":
        payload_user = {
            "mode": normalized_mode,
            "intent": "general",
            "intent_directive": intent_hint,
            "question": _clip(question, 1500),
        }
    else:
        response_template = _intent_response_template(normalized_intent)
        raw_text_context = _extract_raw_text_prompt_context(context)
        resume_projects_only = _project_reference_items(context, limit=6)

        # Build the context_analysis_findings block for this session
        ctx_findings = context.get("context_analysis_findings", {}) if isinstance(context.get("context_analysis_findings"), dict) else {}
        taxonomy_findings = context.get("key_findings", {}) if isinstance(context.get("key_findings"), dict) else {}

        payload_user = {
            "mode": normalized_mode,
            "question": _clip(question, 1500),
            "intent": normalized_intent,
            "intent_directive": intent_hint,
            "intent_output_contract": _intent_output_contract(normalized_intent),
            "response_structure_template": {
                "title": response_template.get("title"),
                "sections": response_template.get("sections"),
                "format_guidance": response_template.get("format_guidance"),
                "emphasis": response_template.get("emphasis"),
            },
            "answer_guidance": (
                "1. Answer the user's question DIRECTLY and PRACTICALLY\n"
                "2. Ground each claim in resume_raw_text, jd_raw_text, taxonomy_key_findings, AND context_analysis_findings\n"
                "3. When listing strengths/matched skills: include both exact taxonomy matches AND implicit/contextually validated skills\n"
                "4. When listing gaps: reference both taxonomy missing_skills AND context_analysis actual_gaps\n"
                "5. Create a '---' separator line before 'Resume Context Reference' section\n"
                "6. In Resume Context Reference, cite which data source supports each point\n"
                "7. Use exact section headings from response_structure_template with ## markdown\n"
                "8. Keep response compact and structured with bullet-first formatting"
            ),
            "resume_reference_context": raw_text_context,
            # ── Taxonomy results ─────────────────────────────────────────────
            "taxonomy_key_findings": {
                "exact_matches": taxonomy_findings.get("exact_matches", [])[:16],
                "semantic_matches": taxonomy_findings.get("semantic_matches", [])[:12],
                "missing_skills": taxonomy_findings.get("missing_skills", [])[:16],
                "additional_resume_skills": taxonomy_findings.get("additional_resume_skills", [])[:10],
            },
            # ── Context analysis results ─────────────────────────────────────
            "context_analysis_findings": {
                "implicit_matches": ctx_findings.get("implicit_matches", [])[:12],
                "contextually_validated": ctx_findings.get("contextually_validated", [])[:12],
                "actual_gaps": ctx_findings.get("actual_gaps", [])[:10],
                "additional_skills": ctx_findings.get("additional_skills", [])[:8],
                "context_summary": ctx_findings.get("context_summary", ""),
            },
        }
        if normalized_intent == "matched_skills":
            matched_skills_list = _matched_skills_from_context(context)
            payload_user["answer_guidance"] += (
                "\n6. Use ONLY skills from matched_skills_only in your answer"
                "\n7. If matched_skills_only is empty, clearly state no matched skills were found in current analysis"
                "\n8. Do not invent any skills not in the provided matched_skills_only list"
            )
            payload_user["matched_skills_only"] = matched_skills_list
        elif normalized_intent == "missing_skills":
            missing_skills_list = _missing_skills_from_context(context)
            payload_user["answer_guidance"] += (
                "\n6. Use ONLY skills from missing_skills_only in your answer"
                "\n7. If missing_skills_only is empty, clearly state no missing skills were found in current analysis"
                "\n8. Do not invent any missing skills not in the provided missing_skills_only list"
            )
            payload_user["missing_skills_only"] = missing_skills_list
        elif normalized_intent == "projects":
            payload_user["answer_guidance"] += (
                "\n6. Use ONLY project names from resume_projects_only in your answer"
                "\n7. If resume_projects_only is empty, clearly state no projects were found in resume context"
                "\n8. Do not invent any project names, technologies, or outcomes"
            )
            payload_user["resume_projects_only"] = resume_projects_only
        payload_user = _compact_for_prompt(payload_user)

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(compact_history)
    if normalized_mode == "general":
        messages.append({
            "role": "user",
            "content": f"Answer this question directly without resume context. The intent hint is optional guidance:\n{json.dumps(payload_user, ensure_ascii=False)}",
        })
    else:
        messages.append({
            "role": "user",
            "content": f"Answer the question directly (main focus), then append resume context references below (use the provided resume_reference_context). Follow response_structure_template exactly in markdown headings and bullet points. Keep bullets concise, keep the overall response compact, and avoid dense paragraphs.\n\nExpected separator rule: include '---' before the 'Resume Context Reference' section.\n\nHere is the context:\n{json.dumps(payload_user, ensure_ascii=False)}",
        })

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "ResumeAnalyzerChat/1.0",
    }

    for attempt in range(max_retries + 1):
        body = {
            "model": current_model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        request_bytes = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(groq_url, data=request_bytes, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
            obj = json.loads(raw)
            answer = _clean_answer_text(obj.get("choices", [{}])[0].get("message", {}).get("content", ""))
            if not answer:
                raise ValueError("Empty response content from Groq")
            
            # Apply post-processing to BOTH modes to clean markdown artifacts
            answer = _post_process_resume_answer(answer)
            
            if normalized_mode == "resume_context":
                # Validate response structure for resume context
                response_template = _intent_response_template(normalized_intent)
                validation = _validate_response_structure(answer, normalized_intent, response_template)
                if normalized_intent == "projects" and not _is_projects_answer_grounded(answer, context):
                    fallback_projects_answer = _deterministic_context_answer(question, context, "projects")
                    if fallback_projects_answer:
                        answer = _post_process_resume_answer(fallback_projects_answer)
                        validation = _validate_response_structure(answer, normalized_intent, response_template)
                elif normalized_intent == "matched_skills" and not _is_matched_skills_answer_grounded(answer, context):
                    fallback_matched_answer = _deterministic_context_answer(question, context, "matched_skills")
                    if fallback_matched_answer:
                        answer = _post_process_resume_answer(fallback_matched_answer)
                        validation = _validate_response_structure(answer, normalized_intent, response_template)
                elif normalized_intent == "missing_skills" and not _is_missing_skills_answer_grounded(answer, context):
                    fallback_missing_answer = _deterministic_context_answer(question, context, "missing_skills")
                    if fallback_missing_answer:
                        answer = _post_process_resume_answer(fallback_missing_answer)
                        validation = _validate_response_structure(answer, normalized_intent, response_template)
            else:
                # General mode - no validation needed
                validation = None
            return {
                "status": "success",
                "answer": _clip(answer, 2600),
                "model": current_model,
                "intent_used": normalized_intent,
                "mode_used": normalized_mode,
                "grounded": True,
                "validation": validation,
            }
        except urllib.error.HTTPError as err:
            status_code = int(getattr(err, "code", 0) or 0)
            detail = err.read().decode("utf-8", errors="ignore") if hasattr(err, "read") else str(err)

            # If throttled, switch once to the configured fallback model for better throughput.
            if status_code == 429 and not switched_to_fallback and fallback_model and fallback_model != current_model:
                current_model = fallback_model
                switched_to_fallback = True
                time.sleep(0.4)
                continue

            if attempt < max_retries and _is_retryable_status(status_code):
                time.sleep(0.6 * (attempt + 1))
                continue
            return {
                "status": "failed",
                "answer": _fallback_answer(question, context, reason=f"HTTP {status_code}", mode=normalized_mode),
                "model": current_model,
                "intent_used": normalized_intent,
                "mode_used": normalized_mode,
                "grounded": True,
                "warning": _clip(detail, 220),
            }
        except (urllib.error.URLError, TimeoutError) as err:
            if attempt < max_retries:
                time.sleep(0.6 * (attempt + 1))
                continue
            return {
                "status": "failed",
                "answer": _fallback_answer(question, context, reason="Network error", mode=normalized_mode),
                "model": current_model,
                "intent_used": normalized_intent,
                "mode_used": normalized_mode,
                "grounded": True,
                "warning": _clip(str(err), 220),
            }
        except Exception as err:
            if attempt < max_retries:
                time.sleep(0.6 * (attempt + 1))
                continue
            return {
                "status": "failed",
                "answer": _fallback_answer(question, context, reason="Unexpected error", mode=normalized_mode),
                "model": current_model,
                "intent_used": normalized_intent,
                "mode_used": normalized_mode,
                "grounded": True,
                "warning": _clip(str(err), 220),
            }

    return {
        "status": "failed",
        "answer": _fallback_answer(question, context, reason="Retries exhausted", mode=normalized_mode),
        "model": current_model,
        "intent_used": normalized_intent,
        "mode_used": normalized_mode,
        "grounded": True,
        "warning": "Retries exhausted",
    }
