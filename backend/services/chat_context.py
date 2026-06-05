import json
import re
from pathlib import Path
from typing import Any, Dict, List


SESSIONS_DIR = Path(__file__).resolve().parents[1] / "data" / "sessions"


def _normalize_whitespace(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _clip(text: Any, limit: int) -> str:
    clean = _normalize_whitespace(text)
    if len(clean) <= limit:
        return clean
    return f"{clean[:limit].rstrip()}..."


def _to_int(value: Any) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def _pick_skills(items: List[Any], key: str = "skill", limit: int = 12) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in items or []:
        if isinstance(item, dict):
            skill = _normalize_whitespace(item.get(key))
        else:
            skill = _normalize_whitespace(item)
        if not skill:
            continue
        low = skill.lower()
        if low in seen:
            continue
        seen.add(low)
        out.append(skill)
        if len(out) >= limit:
            break
    return out


def _split_technologies(text: str) -> List[str]:
    if not text:
        return []
    parts = re.split(r",|/|\||;", text)
    cleaned = []
    seen = set()
    for part in parts:
        item = _normalize_whitespace(part)
        if not item:
            continue
        low = item.lower()
        if low in seen:
            continue
        seen.add(low)
        cleaned.append(item)
        if len(cleaned) >= 12:
            break
    return cleaned


def _extract_resume_projects(resume_raw_text: str) -> List[Dict[str, Any]]:
    text = str(resume_raw_text or "")
    if not text:
        return []

    block_match = re.search(
        r"\bPROJECTS\b(.*?)(?=\n\s*(INTERNSHIPS|CERTIFICATIONS|CODING PROFILES|EDUCATION|SKILLS)\b|\Z)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not block_match:
        return []

    projects_block = block_match.group(1).strip()
    if not projects_block:
        return []

    project_pattern = re.compile(
        r"(^|\n)(?P<name>[A-Z][A-Za-z0-9 .&+\-]{2,60})\s*\((?P<duration>[^\)]{3,50})\):\s*(?P<body>.*?)(?=\n[A-Z][A-Za-z0-9 .&+\-]{2,60}\s*\([^\)]{3,50}\):|\Z)",
        flags=re.DOTALL,
    )

    projects: List[Dict[str, Any]] = []
    for match in project_pattern.finditer(projects_block):
        name = _normalize_whitespace(match.group("name"))
        duration = _normalize_whitespace(match.group("duration"))
        body = _normalize_whitespace(match.group("body"))
        if not name or not body:
            continue

        tech_match = re.search(r"Technologies\s*:\s*(.*)$", body, flags=re.IGNORECASE)
        technologies = _split_technologies(_normalize_whitespace(tech_match.group(1) if tech_match else ""))
        summary = re.sub(r"Technologies\s*:\s*.*$", "", body, flags=re.IGNORECASE).strip()

        projects.append(
            {
                "name": name,
                "duration": duration,
                "summary": _clip(summary, 320),
                "technologies": technologies,
            }
        )

        if len(projects) >= 6:
            break

    return projects


def load_session_metadata(session_id: str) -> Dict[str, Any]:
    sid = _normalize_whitespace(session_id)
    if not sid:
        raise FileNotFoundError("Session id is empty")

    metadata_path = SESSIONS_DIR / sid / "metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"Session metadata not found for {sid}")

    with metadata_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _extract_context_groups(context_analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Extract context_validations from the session's context_analysis into labelled groups."""
    validations = context_analysis.get("context_validations", []) if isinstance(context_analysis, dict) else []
    groups: Dict[str, List[Any]] = {
        "implicit_matches": [],
        "contextually_validated": [],
        "actual_gaps": [],
        "additional_skills": [],
        "false_positives": [],
    }
    for item in (validations or []):
        if not isinstance(item, dict):
            continue
        atype = str(item.get("analysis_type") or item.get("category") or "").lower().replace(" ", "_")
        skill = _normalize_whitespace(item.get("skill_name") or item.get("name") or "")
        if not skill:
            continue
        reasoning = _normalize_whitespace(item.get("reasoning") or item.get("details") or "")[:180]
        entry = {"skill": skill, "reasoning": reasoning} if reasoning else {"skill": skill}
        if "implicit" in atype:
            groups["implicit_matches"].append(entry)
        elif "context" in atype or "validated" in atype:
            groups["contextually_validated"].append(entry)
        elif "gap" in atype or "missing" in atype or "actual" in atype:
            groups["actual_gaps"].append(entry)
        elif "additional" in atype or "extra" in atype:
            groups["additional_skills"].append(entry)
        elif "false" in atype or "positive" in atype:
            groups["false_positives"].append(entry)
    return {
        "implicit_matches": groups["implicit_matches"][:15],
        "contextually_validated": groups["contextually_validated"][:15],
        "actual_gaps": groups["actual_gaps"][:12],
        "additional_skills": groups["additional_skills"][:10],
        "context_summary": _clip(context_analysis.get("context_summary", "") if isinstance(context_analysis, dict) else "", 400),
    }


def build_chat_context(metadata: Dict[str, Any]) -> Dict[str, Any]:
    bert = metadata.get("bert_results", {}) if isinstance(metadata.get("bert_results"), dict) else {}
    summary = bert.get("summary", {}) if isinstance(bert.get("summary"), dict) else {}
    partition = bert.get("skill_partition", {}) if isinstance(bert.get("skill_partition"), dict) else {}

    resume_versions = metadata.get("resume_versions", {}) if isinstance(metadata.get("resume_versions"), dict) else {}
    jd_versions = metadata.get("jd_versions", {}) if isinstance(metadata.get("jd_versions"), dict) else {}

    resume_skills_obj = metadata.get("resume_skills", {}) if isinstance(metadata.get("resume_skills"), dict) else {}
    jd_skills_obj = metadata.get("jd_skills", {}) if isinstance(metadata.get("jd_skills"), dict) else {}
    ai_enrichment = metadata.get("ai_enrichment", {}) if isinstance(metadata.get("ai_enrichment"), dict) else {}
    context_analysis_raw = metadata.get("context_analysis", {}) if isinstance(metadata.get("context_analysis"), dict) else {}
    candidate_decision_layer = metadata.get("candidate_decision_layer", {}) if isinstance(metadata.get("candidate_decision_layer"), dict) else {}
    hr_decision_layer = metadata.get("hr_decision_layer", {}) if isinstance(metadata.get("hr_decision_layer"), dict) else {}

    exact_matches = _pick_skills(partition.get("exact_match", []), limit=16)

    semantic_pairs: List[str] = []
    for group_name in ["strong_semantic", "moderate_semantic"]:
        for item in partition.get(group_name, []) or []:
            if not isinstance(item, dict):
                continue
            src = _normalize_whitespace(item.get("skill"))
            dst = _normalize_whitespace(item.get("similar_to"))
            score = item.get("score")
            if not src or not dst:
                continue
            try:
                s_text = f" ({float(score):.2f})"
            except Exception:
                s_text = ""
            semantic_pairs.append(f"{src} -> {dst}{s_text}")
            if len(semantic_pairs) >= 16:
                break
        if len(semantic_pairs) >= 16:
            break

    missing = _pick_skills(bert.get("missing_from_resume", []), key="skill", limit=16)
    extras = _pick_skills(bert.get("extra_resume_skills", []), limit=16)

    resume_tech = _pick_skills(resume_skills_obj.get("technical_skills", []), limit=24)
    resume_soft = _pick_skills(resume_skills_obj.get("soft_skills", []), limit=16)
    jd_tech = _pick_skills(jd_skills_obj.get("technical_skills", []), limit=24)
    jd_soft = _pick_skills(jd_skills_obj.get("soft_skills", []), limit=16)

    projects = _extract_resume_projects(resume_versions.get("raw_text", ""))
    interview_focus = ai_enrichment.get("interview_focus", []) if isinstance(ai_enrichment.get("interview_focus"), list) else []
    top_recommendations = ai_enrichment.get("top_recommendations", []) if isinstance(ai_enrichment.get("top_recommendations"), list) else []

    # Extract structured context analysis groups
    context_groups = _extract_context_groups(context_analysis_raw)

    context = {
        "session": {
            "session_id": metadata.get("session_id"),
            "timestamp": metadata.get("timestamp"),
            "domain": resume_skills_obj.get("domain") or jd_skills_obj.get("domain") or "software",
            "resume_filename": metadata.get("resume_filename", ""),
            "jd_filename": metadata.get("jd_filename", ""),
        },
        # ── Taxonomy analysis summary ─────────────────────────────────────────
        "summary": {
            "overall_alignment_score": _to_int(summary.get("overall_alignment_score")),
            "total_jd_skills": _to_int(summary.get("total_jd_skills")),
            "resume_detected_skills": _to_int(summary.get("resume_detected_skills")),
            "exact_match_count": _to_int(summary.get("exact_match_count")),
            "semantic_match_count": _to_int(summary.get("semantic_match_count")),
            "missing_skills_count": _to_int(summary.get("missing_skills_count")),
        },
        # ── Key findings from taxonomy ────────────────────────────────────────
        "key_findings": {
            "exact_matches": exact_matches,
            "semantic_matches": semantic_pairs,
            "missing_skills": missing,
            "additional_resume_skills": extras,
        },
        # ── Context analysis findings (deep NLU) ─────────────────────────────
        "context_analysis_findings": {
            "implicit_matches": context_groups["implicit_matches"],
            "contextually_validated": context_groups["contextually_validated"],
            "actual_gaps": context_groups["actual_gaps"],
            "additional_skills": context_groups["additional_skills"],
            "context_summary": context_groups["context_summary"],
        },
        # ── Full skill inventory ──────────────────────────────────────────────
        "skills_inventory": {
            "resume_technical": resume_tech,
            "resume_soft": resume_soft,
            "jd_technical": jd_tech,
            "jd_soft": jd_soft,
        },
        "candidate_profile": {
            "projects": projects,
            "project_names": [p.get("name") for p in projects if p.get("name")],
        },
        "ai_guidance": {
            "interview_focus": interview_focus[:8],
            "top_recommendations": top_recommendations[:8],
        },
        "decision_layers": {
            "candidate": candidate_decision_layer,
            "hr": hr_decision_layer,
        },
        # ── Full raw texts so chatbot has complete signal ─────────────────────
        "text_snippets": {
            "job_description_excerpt": _clip(jd_versions.get("raw_text", ""), 2400),
            "resume_excerpt": _clip(resume_versions.get("raw_text", ""), 2400),
        },
    }

    return context

