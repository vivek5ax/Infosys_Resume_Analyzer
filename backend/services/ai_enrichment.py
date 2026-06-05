import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "mixtral-8x7b-32768"


def _load_local_env() -> None:
    """Load backend/.env and backend/.env.local into process env if present."""
    backend_dir = Path(__file__).resolve().parents[1]
    candidates = [backend_dir / ".env", backend_dir / ".env.local"]

    for env_path in candidates:
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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_float(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return fallback


def _clean_term(value: Any) -> str:
    text = str(value or "").strip()
    return re.sub(r"\s+", " ", text)


def _default_response(run_id: str, model: str, status: str, reason: str = "") -> Dict[str, Any]:
    warnings = [reason] if reason else []
    return {
        "status": status,
        "version": "1.0.0",
        "run_id": run_id,
        "model": model,
        "created_at": _now_iso(),
        "normalization": {
            "mappings": [],
            "unmapped_terms": [],
        },
        "missing_skill_triage": [],
        "interview_focus": [],
        "report_narrative": {
            "executive_overview": "",
            "strengths": [],
            "risk_flags": [],
            "onboarding_plan": [],
            "interview_strategy": "",
            "final_recommendation": "",
        },
        # --- New extended report sections ---
        "ats_readiness": {
            "verdict": "",
            "score": 0,
            "explanation": "",
            "tips": [],
        },
        "hard_skills_narrative": "",
        "soft_skills_assessment": {
            "detected": [],
            "missing": [],
            "narrative": "",
        },
        "top_recommendations": [],
        "quality": {
            "hallucination_risk": "medium",
            "coverage_score": 0.0,
            "warnings": warnings,
            "used_inputs": {
                "jd_chars": 0,
                "resume_chars": 0,
                "jd_skill_count": 0,
                "resume_skill_count": 0,
                "missing_skill_count": 0,
            },
        },
    }



def _classify_http_error(status_code: int, detail: str) -> str:
    text = (detail or "").strip()
    lower = text.lower()

    if "error code: 1010" in lower:
        return (
            "Groq access denied (Cloudflare 1010). This is usually a network/IP policy block. "
            "Use a different egress network or allowlist access to api.groq.com."
        )
    if status_code == 401 or "invalid api key" in lower:
        return "Groq authentication failed (401). Verify GROQ_API_KEY."
    if status_code == 429:
        return "Groq rate limit reached (429). Retry after a short delay."
    if status_code in {500, 502, 503, 504}:
        return f"Groq service temporarily unavailable ({status_code})."
    if "<html" in lower and "cloudflare" in lower:
        return "Groq gateway returned an HTML protection page. Check network/proxy/firewall settings."

    compact = re.sub(r"\s+", " ", text)[:180]
    if compact:
        return f"Groq HTTP error ({status_code}): {compact}"
    return f"Groq HTTP error ({status_code})"


def _should_retry_http(status_code: int) -> bool:
    return status_code in {408, 425, 429, 500, 502, 503, 504}


def _extract_jd_snippet_for_skill(jd_text: str, skill: str, limit: int = 220) -> str:
    text = _clean_term(jd_text)
    target = _clean_term(skill)
    if not text or not target:
        return target

    # Try sentence-level extraction first to keep evidence human-readable.
    sentence_candidates = re.split(r"(?<=[.!?])\s+", text)
    lower_target = target.lower()
    for sentence in sentence_candidates:
        if lower_target in sentence.lower():
            return sentence[:limit]

    idx = text.lower().find(lower_target)
    if idx == -1:
        return target

    start = max(0, idx - 80)
    end = min(len(text), idx + len(target) + 120)
    return text[start:end][:limit]


def _priority_from_position(position: int) -> str:
    if position <= 1:
        return "role_critical"
    if position <= 4:
        return "important"
    return "nice_to_have"


def _impact_from_priority(priority: str) -> str:
    if priority == "role_critical":
        return "high"
    if priority == "important":
        return "medium"
    return "low"


def _trainability_from_priority(priority: str) -> str:
    if priority == "role_critical":
        return "hard_to_train_fast"
    if priority == "important":
        return "trainable_mid_term"
    return "trainable_short_term"


def _build_deterministic_triage(missing_skills: List[str], jd_text: str) -> List[Dict[str, Any]]:
    triage: List[Dict[str, Any]] = []
    for idx, skill in enumerate(missing_skills[:8]):
        priority = _priority_from_position(idx)
        confidence = max(0.45, 0.86 - (idx * 0.05))
        triage.append(
            {
                "skill": skill[:120],
                "priority": priority,
                "trainability": _trainability_from_priority(priority),
                "impact": _impact_from_priority(priority),
                "confidence": round(max(0.0, min(1.0, confidence)), 2),
                "reason": f"{skill} is missing from the resume and appears as a JD requirement.",
                "evidence": {
                    "jd_snippet": _extract_jd_snippet_for_skill(jd_text, skill),
                    "resume_signal": "not_found",
                },
            }
        )
    return triage


def _build_deterministic_interview_focus(triage: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    focus: List[Dict[str, Any]] = []
    for idx, item in enumerate(triage[:6]):
        skill = _clean_term(item.get("skill"))
        if not skill:
            continue
        conf = max(0.35, 0.82 - (idx * 0.06))
        focus.append(
            {
                "topic": skill[:120],
                "objective": f"Validate practical depth and recency for {skill}.",
                "question": f"Describe one recent project where you applied {skill} end-to-end. What constraints and trade-offs did you handle?",
                "expected_signal": "Candidate explains architecture decisions, ownership, and measurable outcomes.",
                "confidence": round(max(0.0, min(1.0, conf)), 2),
            }
        )
    return focus


def _build_deterministic_normalization(partition: Dict[str, Any]) -> List[Dict[str, Any]]:
    mappings: List[Dict[str, Any]] = []
    seen = set()
    for bucket in ["strong_semantic", "moderate_semantic"]:
        items = partition.get(bucket, []) if isinstance(partition.get(bucket), list) else []
        for item in items[:24]:
            if not isinstance(item, dict):
                continue
            source = _clean_term(item.get("skill"))
            normalized = _clean_term(item.get("similar_to"))
            if not source or not normalized:
                continue
            key = (source.lower(), normalized.lower())
            if key in seen:
                continue
            seen.add(key)
            confidence = max(0.0, min(1.0, _to_float(item.get("confidence"), 0.0)))
            if confidence <= 0.0:
                confidence = 0.72 if bucket == "strong_semantic" else 0.58
            mappings.append(
                {
                    "source_term": source[:120],
                    "normalized_term": normalized[:120],
                    "relation": "related",
                    "confidence": round(confidence, 2),
                    "evidence": {
                        "source": "both",
                        "snippet": f"Semantic proximity observed between {source} and {normalized}.",
                    },
                    "notes": "Derived from deterministic semantic matching layer.",
                }
            )
    return mappings[:12]


def _build_deterministic_ats_readiness(
    score: float, missing_count: int, total_skills: int, exact_count: int
) -> Dict[str, Any]:
    """Deterministic ATS readiness fallback based on alignment score."""
    if score >= 75:
        verdict = "Pass"
        ats_score = min(95, int(score))
        explanation = (
            f"Strong keyword alignment ({score:.0f}%) — resume is likely to clear most ATS filters "
            f"for this role with {exact_count} exact keyword match(es)."
        )
        tips = [
            "Include role-specific job title keywords in your resume header or summary.",
            "Use standard section headings: 'Work Experience', 'Education', 'Skills'.",
            "Save the resume as a plain PDF or Word .docx — avoid scanned images.",
        ]
    elif score >= 50:
        verdict = "Borderline"
        ats_score = max(45, int(score - 10))
        explanation = (
            f"Moderate keyword alignment ({score:.0f}%) — ATS pass-through is inconsistent. "
            f"{missing_count} missing skill(s) reduce the match rate below safe thresholds."
        )
        tips = [
            "Add the top 5 missing hard skills explicitly to your Skills section.",
            "Mirror exact phrases from the job description — ATS is case/spelling sensitive.",
            "Avoid tables, columns, headers/footers that ATS parsers can't read.",
            "Include measurable achievements (e.g., '40% latency reduction') for recruiter review.",
        ]
    else:
        verdict = "At Risk"
        ats_score = max(10, int(score - 15))
        explanation = (
            f"Low alignment ({score:.0f}%) — resume will likely fail most ATS filters. "
            f"{missing_count} of {total_skills} required skills are missing."
        )
        tips = [
            "Rewrite resume summary to include the exact job title and domain keywords.",
            "Add a dedicated 'Technical Skills' section listing all missing required skills.",
            "Use the same terminology as the job description (e.g., 'CI/CD', not 'continuous delivery').",
            "Remove graphics, infographics, or non-standard fonts that break ATS parsing.",
            "Consider applying after closing at least 60% of the identified skill gaps.",
        ]
    return {"verdict": verdict, "score": ats_score, "explanation": explanation, "tips": tips}


def _build_deterministic_hard_skills_narrative(
    exact_count: int, semantic_count: int, missing_count: int, total_skills: int, domain: str
) -> str:
    pct = round(((exact_count + semantic_count) / max(1, total_skills)) * 100)
    return (
        f"The candidate covers {exact_count} exact technical keyword(s) and {semantic_count} semantically "
        f"related skill(s), yielding a {pct}% hard skill coverage rate against the {domain} job description. "
        f"{missing_count} technical gap(s) remain that are explicitly required by the role. "
        f"Closing these gaps — especially role-critical items — would materially improve ATS pass-through "
        f"and signal competency depth to the hiring panel."
    )


def _build_deterministic_soft_skills_assessment(
    resume_skills: List[str], jd_skills: List[str], partition: Dict[str, Any]
) -> Dict[str, Any]:
    soft_keywords = {
        "communication", "leadership", "teamwork", "collaboration", "problem solving",
        "critical thinking", "adaptability", "time management", "creativity", "attention to detail",
        "presentation", "negotiation", "conflict resolution", "mentoring", "project management",
        "stakeholder management", "analytical", "organisational", "organisation", "interpersonal",
    }

    def _is_soft(skill: str) -> bool:
        return any(kw in skill.lower() for kw in soft_keywords)

    detected = sorted({s for s in resume_skills if _is_soft(s)})[:8]
    needed   = sorted({s for s in jd_skills     if _is_soft(s)})[:8]
    missing  = [s for s in needed if s not in {d.lower() for d in detected}][:5]

    narrative = (
        f"Detected {len(detected)} soft skill(s) in the resume. "
        + (f"The following are matched with JD requirements: {', '.join(detected[:4])}. " if detected else "")
        + (f"{len(missing)} soft skill gap(s) noted: {', '.join(missing)}." if missing else
           "All JD soft skill requirements appear covererd.")
    )
    return {"detected": detected, "missing": missing, "narrative": narrative}


def _build_deterministic_top_recommendations(
    triage: List[Dict[str, Any]], score: float
) -> List[Dict[str, Any]]:
    recs = []
    for item in triage[:5]:
        pri = item.get("priority", "important")
        recs.append({
            "priority": "Critical" if pri == "role_critical" else "High" if pri == "important" else "Medium",
            "action": f"Add '{item.get('skill','')}' to your resume.",
            "reason": item.get("reason", "")[:200],
        })
    if score < 75:
        recs.append({
            "priority": "High",
            "action": "Quantify at least 3 bullet points with measurable outcomes (e.g., '30% faster').",
            "reason": "ATS and recruiters favour concrete, numbers-backed achievements over vague statements.",
        })
    if score < 55:
        recs.append({
            "priority": "Critical",
            "action": "Add a targeted 'Technical Skills' section listing role-required technologies.",
            "reason": "Missing a dedicated skills section significantly reduces ATS keyword matching.",
        })
    return recs[:6]


def _merge_unique_dict_items(existing: List[Dict[str, Any]], incoming: List[Dict[str, Any]], key_name: str, limit: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen = set()
    for item in [*existing, *incoming]:
        if not isinstance(item, dict):
            continue

        key_value = _clean_term(item.get(key_name)).lower()
        if not key_value or key_value in seen:
            continue
        seen.add(key_value)
        out.append(item)
        if len(out) >= limit:
            break
    return out


def _compute_coverage_score(
    triage_count: int,
    interview_count: int,
    mapping_count: int,
    missing_count: int,
    semantic_candidates: int,
    narrative_items: int = 0,
) -> float:
    expected_triage = min(6, max(1, missing_count))
    expected_interview = min(5, max(1, missing_count))
    expected_mapping = min(8, max(1, semantic_candidates))

    triage_ratio = min(1.0, triage_count / expected_triage)
    interview_ratio = min(1.0, interview_count / expected_interview)
    mapping_ratio = min(1.0, mapping_count / expected_mapping)

    narrative_ratio = min(1.0, narrative_items / 4) if narrative_items > 0 else 0.0

    score = (0.38 * triage_ratio) + (0.28 * interview_ratio) + (0.16 * mapping_ratio) + (0.18 * narrative_ratio)
    return round(max(0.0, min(1.0, score)), 2)


def _build_deterministic_narrative(
    *,
    score: float,
    exact_count: int,
    semantic_count: int,
    missing_count: int,
    total_skills: int,
    domain: str,
) -> Dict[str, Any]:
    score_band = "strong" if score >= 75 else "good" if score >= 60 else "borderline" if score >= 45 else "low"

    if score >= 75:
        recommendation = "Proceed to final rounds. Validate depth and recency for role-critical architecture and delivery ownership."
    elif score >= 60:
        recommendation = "Proceed to technical interview. Focus on gap closure potential and scenario-based problem solving."
    elif score >= 45:
        recommendation = "Run a targeted technical assessment before progression."
    else:
        recommendation = "Hold for this role and evaluate adjacent positions with lower mandatory-skill dependency."

    strengths = [
        f"Exact match coverage is {exact_count} skill(s), indicating direct overlap with the role baseline.",
        f"Semantic alignment includes {semantic_count} related skill(s), suggesting transferable capability.",
    ]

    risk_flags = [
        f"{missing_count} required skill(s) are currently missing out of {total_skills} total JD skills.",
        "Missing role-critical items should be validated via practical examples rather than keyword-only claims.",
    ]

    onboarding = [
        "Week 1-2: close foundational tool/process gaps with guided tasks and codebase walkthroughs.",
        "Week 3-4: assign scoped ownership aligned to strongest matched categories.",
        "Week 5-6: evaluate independence on medium-complexity deliverables and stakeholder communication.",
    ]

    return {
        "executive_overview": (
            f"Candidate demonstrates {score_band} fit for {domain} with {round(score)}% alignment, "
            f"based on exact matches, semantic overlap, and quantified missing-skill risk."
        ),
        "strengths": strengths,
        "risk_flags": risk_flags,
        "onboarding_plan": onboarding,
        "interview_strategy": (
            "Use behavior + system-design style prompts tied to missing skills; request one recent project walkthrough "
            "per critical competency with measurable outcomes."
        ),
        "final_recommendation": recommendation,
    }


def _parse_json_object(raw_text: str) -> Dict[str, Any]:
    text = (raw_text or "").strip()
    if not text:
        return {}

    # First attempt: full JSON
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass

    # Fallback: extract first JSON object substring
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}

    candidate = text[start : end + 1]
    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _validate_and_sanitize(
    payload: Dict[str, Any],
    run_id: str,
    model: str,
    jd_text: str,
    resume_text: str,
    jd_skills: List[str],
    resume_skills: List[str],
    missing_skills: List[str],
) -> Dict[str, Any]:
    out = _default_response(run_id=run_id, model=model, status="success")
    out["quality"]["used_inputs"] = {
        "jd_chars": len(jd_text or ""),
        "resume_chars": len(resume_text or ""),
        "jd_skill_count": len(jd_skills),
        "resume_skill_count": len(resume_skills),
        "missing_skill_count": len(missing_skills),
    }

    allowed_terms = {_clean_term(s).lower() for s in [*jd_skills, *resume_skills, *missing_skills] if _clean_term(s)}
    missing_set = {_clean_term(s).lower() for s in missing_skills if _clean_term(s)}

    normalization = payload.get("normalization") if isinstance(payload.get("normalization"), dict) else {}
    mappings = normalization.get("mappings") if isinstance(normalization.get("mappings"), list) else []
    sanitized_mappings = []

    for item in mappings[:300]:
        if not isinstance(item, dict):
            continue
        source_term = _clean_term(item.get("source_term"))
        normalized_term = _clean_term(item.get("normalized_term"))
        relation = str(item.get("relation") or "related")
        confidence = max(0.0, min(1.0, _to_float(item.get("confidence"), 0.0)))

        if not source_term or not normalized_term:
            continue

        # Guardrail: at least one side must exist in known extracted terms.
        if source_term.lower() not in allowed_terms and normalized_term.lower() not in allowed_terms:
            continue

        if relation not in {"exact", "alias", "abbreviation", "related"}:
            relation = "related"

        evidence_obj = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
        source = str(evidence_obj.get("source") or "both")
        if source not in {"jd", "resume", "both"}:
            source = "both"
        snippet = _clean_term(evidence_obj.get("snippet"))[:400] or f"{source_term} -> {normalized_term}"

        sanitized_mappings.append(
            {
                "source_term": source_term[:120],
                "normalized_term": normalized_term[:120],
                "relation": relation,
                "confidence": confidence,
                "evidence": {"source": source, "snippet": snippet},
                "notes": _clean_term(item.get("notes"))[:240],
            }
        )

    out["normalization"]["mappings"] = sanitized_mappings
    unmapped_terms = normalization.get("unmapped_terms") if isinstance(normalization.get("unmapped_terms"), list) else []
    out["normalization"]["unmapped_terms"] = [_clean_term(v)[:120] for v in unmapped_terms[:100] if _clean_term(v)]

    triage = payload.get("missing_skill_triage") if isinstance(payload.get("missing_skill_triage"), list) else []
    sanitized_triage = []
    for item in triage[:120]:
        if not isinstance(item, dict):
            continue
        skill = _clean_term(item.get("skill"))
        if not skill:
            continue
        # Strong guardrail: triage must map to known missing skills only.
        if skill.lower() not in missing_set:
            continue

        priority = str(item.get("priority") or "important")
        if priority not in {"role_critical", "important", "nice_to_have"}:
            priority = "important"

        trainability = str(item.get("trainability") or "trainable_mid_term")
        if trainability not in {"hard_to_train_fast", "trainable_short_term", "trainable_mid_term"}:
            trainability = "trainable_mid_term"

        impact = str(item.get("impact") or "medium")
        if impact not in {"high", "medium", "low"}:
            impact = "medium"

        confidence = max(0.0, min(1.0, _to_float(item.get("confidence"), 0.0)))
        reason = _clean_term(item.get("reason"))[:300]

        evidence_obj = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
        jd_snippet = _clean_term(evidence_obj.get("jd_snippet"))[:400]
        resume_signal = str(evidence_obj.get("resume_signal") or "not_found")
        if resume_signal not in {"present_as_related", "not_found", "weak_signal"}:
            resume_signal = "not_found"

        sanitized_triage.append(
            {
                "skill": skill[:120],
                "priority": priority,
                "trainability": trainability,
                "impact": impact,
                "confidence": confidence,
                "reason": reason or f"{skill} appears under missing skills for this role.",
                "evidence": {
                    "jd_snippet": jd_snippet or skill,
                    "resume_signal": resume_signal,
                },
            }
        )

    out["missing_skill_triage"] = sanitized_triage

    interview_focus = payload.get("interview_focus") if isinstance(payload.get("interview_focus"), list) else []
    sanitized_focus = []
    for item in interview_focus[:20]:
        if not isinstance(item, dict):
            continue
        topic = _clean_term(item.get("topic"))[:120]
        question = _clean_term(item.get("question"))[:400]
        objective = _clean_term(item.get("objective"))[:220]
        expected_signal = _clean_term(item.get("expected_signal"))[:220]
        if not topic or not question:
            continue

        confidence = max(0.0, min(1.0, _to_float(item.get("confidence"), 0.0)))
        sanitized_focus.append(
            {
                "topic": topic,
                "objective": objective or "Validate practical experience for this skill area.",
                "question": question,
                "expected_signal": expected_signal or "Candidate demonstrates concrete project-level depth.",
                "confidence": confidence,
            }
        )

    out["interview_focus"] = sanitized_focus

    narrative = payload.get("report_narrative") if isinstance(payload.get("report_narrative"), dict) else {}
    strengths = narrative.get("strengths") if isinstance(narrative.get("strengths"), list) else []
    risk_flags = narrative.get("risk_flags") if isinstance(narrative.get("risk_flags"), list) else []
    onboarding_plan = narrative.get("onboarding_plan") if isinstance(narrative.get("onboarding_plan"), list) else []

    out["report_narrative"] = {
        "executive_overview": _clean_term(narrative.get("executive_overview"))[:500],
        "strengths": [_clean_term(v)[:240] for v in strengths[:6] if _clean_term(v)],
        "risk_flags": [_clean_term(v)[:240] for v in risk_flags[:6] if _clean_term(v)],
        "onboarding_plan": [_clean_term(v)[:240] for v in onboarding_plan[:6] if _clean_term(v)],
        "interview_strategy": _clean_term(narrative.get("interview_strategy"))[:500],
        "final_recommendation": _clean_term(narrative.get("final_recommendation"))[:500],
    }

    quality = payload.get("quality") if isinstance(payload.get("quality"), dict) else {}
    risk = str(quality.get("hallucination_risk") or "medium")
    if risk not in {"low", "medium", "high"}:
        risk = "medium"

    coverage_score = max(0.0, min(1.0, _to_float(quality.get("coverage_score"), 0.0)))
    warnings = quality.get("warnings") if isinstance(quality.get("warnings"), list) else []
    warnings = [_clean_term(v)[:200] for v in warnings[:20] if _clean_term(v)]

    out["quality"]["hallucination_risk"] = risk
    out["quality"]["coverage_score"] = coverage_score
    out["quality"]["warnings"] = warnings

    # ── New fields sanitization ─────────────────────────────────────────────
    # ats_readiness
    ats_raw = payload.get("ats_readiness") if isinstance(payload.get("ats_readiness"), dict) else {}
    ats_verdict = str(ats_raw.get("verdict") or "")
    if ats_verdict not in {"Pass", "Borderline", "At Risk"}:
        ats_verdict = ""
    ats_tips_raw = ats_raw.get("tips") if isinstance(ats_raw.get("tips"), list) else []
    out["ats_readiness"] = {
        "verdict":     ats_verdict,
        "score":       max(0, min(100, int(_to_float(ats_raw.get("score"), 0)))),
        "explanation": _clean_term(ats_raw.get("explanation"))[:400],
        "tips":        [_clean_term(t)[:200] for t in ats_tips_raw[:6] if _clean_term(t)],
    }

    # hard_skills_narrative
    hsn = payload.get("hard_skills_narrative")
    out["hard_skills_narrative"] = _clean_term(hsn)[:600] if isinstance(hsn, str) else ""

    # soft_skills_assessment
    ssa_raw = payload.get("soft_skills_assessment") if isinstance(payload.get("soft_skills_assessment"), dict) else {}
    ssa_detected = ssa_raw.get("detected") if isinstance(ssa_raw.get("detected"), list) else []
    ssa_missing  = ssa_raw.get("missing")  if isinstance(ssa_raw.get("missing"),  list) else []
    out["soft_skills_assessment"] = {
        "detected":  [_clean_term(s)[:80] for s in ssa_detected[:10] if _clean_term(s)],
        "missing":   [_clean_term(s)[:80] for s in ssa_missing[:6]   if _clean_term(s)],
        "narrative": _clean_term(ssa_raw.get("narrative"))[:400],
    }

    # top_recommendations
    recs_raw = payload.get("top_recommendations") if isinstance(payload.get("top_recommendations"), list) else []
    sanitized_recs = []
    for rec in recs_raw[:8]:
        if not isinstance(rec, dict):
            continue
        pri = str(rec.get("priority") or "Medium")
        if pri not in {"Critical", "High", "Medium"}:
            pri = "Medium"
        action = _clean_term(rec.get("action"))[:200]
        reason = _clean_term(rec.get("reason"))[:300]
        if action:
            sanitized_recs.append({"priority": pri, "action": action, "reason": reason})
    out["top_recommendations"] = sanitized_recs

    return out



def _extract_context_analysis_groups(context_analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Extract context_validations from context_analysis into labelled skill groups."""
    validations = context_analysis.get("context_validations", []) if isinstance(context_analysis, dict) else []
    groups: Dict[str, List[str]] = {
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
        skill = _clean_term(item.get("skill_name") or item.get("name") or "")
        if not skill:
            continue
        reasoning = _clean_term(item.get("reasoning") or item.get("details") or "")[:200]
        entry = f"{skill}: {reasoning}" if reasoning else skill
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
        "actual_gaps": groups["actual_gaps"][:15],
        "additional_skills": groups["additional_skills"][:10],
        "false_positives": groups["false_positives"][:8],
        "context_summary": _clean_term(context_analysis.get("context_summary", "") if isinstance(context_analysis, dict) else "")[:500],
    }


def _build_prompt_payload(
    run_id: str,
    domain: str,
    jd_text: str,
    resume_text: str,
    jd_skills: List[str],
    resume_skills: List[str],
    missing_skills: List[str],
    partition: Dict[str, Any],
    summary: Dict[str, Any],
    context_analysis: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    context_groups = _extract_context_analysis_groups(context_analysis or {})
    return {
        "run_id": run_id,
        "domain": domain,
        # Full texts passed so LLM has complete signal
        "jd_text": (jd_text or "")[:12000],
        "resume_text": (resume_text or "")[:12000],
        # ── Taxonomy analysis results ──────────────────────────────────────────
        "jd_skills": jd_skills[:250],
        "resume_skills": resume_skills[:350],
        "missing_skills": missing_skills[:150],
        "score_summary": {
            "overall_alignment_score": _to_float(summary.get("overall_alignment_score"), 0.0),
            "exact_match_count": int(_to_float(summary.get("exact_match_count"), 0.0)),
            "semantic_match_count": int(_to_float(summary.get("semantic_match_count"), 0.0)),
            "missing_skills_count": int(_to_float(summary.get("missing_skills_count"), 0.0)),
            "total_jd_skills": int(_to_float(summary.get("total_jd_skills"), 0.0)),
        },
        "taxonomy_partition": {
            "exact_match": partition.get("exact_match", [])[:60],
            "strong_semantic": partition.get("strong_semantic", [])[:40],
            "moderate_semantic": partition.get("moderate_semantic", [])[:30],
            "missing_from_resume": partition.get("missing_from_resume", [])[:40],
        },
        # ── Context analysis results (Groq deep NLU layer) ─────────────────────
        "context_analysis": context_groups,
    }


def enrich_with_groq(
    *,
    run_id: str,
    domain: str,
    jd_text: str,
    resume_text: str,
    jd_skills: List[str],
    resume_skills: List[str],
    bert_results: Dict[str, Any],
    context_analysis: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    model = os.getenv("GROQ_MODEL", DEFAULT_MODEL)
    groq_url = (os.getenv("GROQ_API_URL", GROQ_URL) or GROQ_URL).strip()
    api_key = os.getenv("GROQ_API_KEY", "").strip()

    enabled_env = os.getenv("AI_ENRICHMENT_ENABLED", "true").strip().lower()
    enabled = enabled_env in {"1", "true", "yes", "on"}

    if not enabled:
        return _default_response(run_id=run_id, model=model, status="disabled", reason="AI enrichment disabled by config")
    if not api_key:
        return _default_response(run_id=run_id, model=model, status="disabled", reason="GROQ_API_KEY not configured")

    timeout_sec = _to_float(os.getenv("GROQ_TIMEOUT_SEC", "18"), 18.0)
    timeout_sec = max(4.0, min(60.0, timeout_sec))

    partition = bert_results.get("skill_partition", {}) if isinstance(bert_results.get("skill_partition"), dict) else {}
    summary = bert_results.get("summary", {}) if isinstance(bert_results.get("summary"), dict) else {}
    missing_from_resume = bert_results.get("missing_from_resume", []) if isinstance(bert_results.get("missing_from_resume"), list) else []
    missing_skills = [_clean_term(item.get("skill")) for item in missing_from_resume if isinstance(item, dict)]
    missing_skills = [s for s in missing_skills if s]

    prompt_payload = _build_prompt_payload(
        run_id=run_id,
        domain=domain,
        jd_text=jd_text,
        resume_text=resume_text,
        jd_skills=jd_skills,
        resume_skills=resume_skills,
        missing_skills=missing_skills,
        partition=partition,
        summary=summary,
        context_analysis=context_analysis,
    )

    system_prompt = (
        "You are a senior HR-grade resume analyst and ATS expert. "
        "You receive a comprehensive input that contains: "
        "(1) the full job description text, "
        "(2) the full resume text, "
        "(3) taxonomy skill analysis results (exact matches, semantic matches, missing skills from our rule-based algorithm), and "
        "(4) deep context analysis results (implicit matches, contextually validated skills, and actual skill gaps "
        "identified by NLU analysis of the raw texts). "
        "CRITICAL RULES: "
        "- Use ALL of the above inputs together to generate your analysis — do NOT ignore the context_analysis section. "
        "- Treat context_analysis.implicit_matches and context_analysis.contextually_validated as REAL STRENGTHS even if they were not caught by taxonomy. "
        "- Treat context_analysis.actual_gaps as CONFIRMED MISSING SKILLS in addition to missing_skills list. "
        "- Use the full jd_text and resume_text to find additional evidence for your narrative. "
        "- NEVER fabricate technologies or achievements not present in the resume. "
        "Return ONLY a single valid JSON object with ALL of these top-level keys: "
        "version, run_id, model, created_at, normalization, missing_skill_triage, interview_focus, "
        "report_narrative, ats_readiness, hard_skills_narrative, soft_skills_assessment, "
        "top_recommendations, quality. "
        "No markdown, no explanation, JSON only."
    )

    # Build context_analysis summary for user prompt injection
    ctx = prompt_payload.get("context_analysis", {})
    ctx_section = ""
    if any(ctx.get(k) for k in ["implicit_matches", "contextually_validated", "actual_gaps", "additional_skills"]):
        ctx_section = (
            "\n\nCONTEXT ANALYSIS (deep NLU — treat as high-confidence, PRIORITIZE these over taxonomy alone):\n"
            f"- Implicit Matches (candidate has these skills but expressed differently): {ctx.get('implicit_matches', [])}\n"
            f"- Contextually Validated (confirmed through project/experience context): {ctx.get('contextually_validated', [])}\n"
            f"- Actual Gaps (confirmed missing after NLU analysis): {ctx.get('actual_gaps', [])}\n"
            f"- Additional Skills (in resume but not in JD): {ctx.get('additional_skills', [])}\n"
            f"- Context Summary: {ctx.get('context_summary', '')}\n"
        )

    user_prompt = (
        "Generate a comprehensive AI enrichment JSON for a resume-vs-JD analysis.\n"
        "The input below includes BOTH the taxonomy analysis results AND the deep context analysis results.\n"
        "Use BOTH together to produce the most accurate, evidence-grounded response.\n\n"
        "Constraints:\n"
        "1) missing_skill_triage: Include skills from both 'missing_skills' taxonomy list AND "
           "'context_analysis.actual_gaps'. Each needs: skill, priority (role_critical|important|nice_to_have), "
           "trainability, impact (high|medium|low), confidence (0-1), reason (cite JD evidence), evidence.jd_snippet.\n"
        "2) Include 3-6 interview_focus items; for implicit_match and contextually_validated skills, ask "
           "depth-probing questions that validate real experience behind the implicit signal.\n"
        "3) report_narrative must incorporate both taxonomy AND context analysis insights: "
           "executive_overview(str), strengths(arr 3-5, include implicit matches as strengths), "
           "risk_flags(arr 3-4, based on actual_gaps), onboarding_plan(arr 3), "
           "interview_strategy(str, reference specific skills to probe), final_recommendation(str).\n"
        "4) ats_readiness: verdict('Pass'|'Borderline'|'At Risk'), score(0-100 int based on combined "
           "exact+implicit+contextual matches), explanation (2 sentences using full JD text evidence), "
           "tips(arr 3-5 ATS optimisation actions citing actual missing keywords from JD).\n"
        "5) hard_skills_narrative: 3-5 sentence paragraph referencing exact JD requirements from jd_text, "
           "candidate's actual skills from resume_text, implicit matches, and confirmed gaps.\n"
        "6) soft_skills_assessment: detected(from resume_text), missing(from jd_text), narrative(2-3 sentences).\n"
        "7) top_recommendations: up to 6 items with priority('Critical'|'High'|'Medium'), "
           "action (imperative, specific), reason (cite jd_text or resume_text evidence).\n"
        "8) normalization.mappings: list skill aliases/equivalences found by comparing jd_text and resume_text. "
           "Include context_analysis.implicit_matches as alias mappings with high confidence.\n"
        "9) All confidence values 0..1. quality.coverage_score reflects completeness.\n"
        "10) Output JSON only — no markdown.\n"
        f"{ctx_section}\n"
        f"INPUT:\n{json.dumps(prompt_payload, ensure_ascii=False)}"
    )


    body = {
        "model": model,
        "temperature": 0.1,
        "max_tokens": 1800,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    request_bytes = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "ResumeAnalyzer/1.0",
    }

    raw = ""
    parsed = None
    max_retries = int(max(0, min(3, _to_float(os.getenv("GROQ_MAX_RETRIES", "2"), 2))))

    for attempt in range(max_retries + 1):
        req = urllib.request.Request(
            groq_url,
            data=request_bytes,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
            break
        except urllib.error.HTTPError as err:
            status_code = int(getattr(err, "code", 0) or 0)
            detail = err.read().decode("utf-8", errors="ignore") if hasattr(err, "read") else str(err)
            if attempt < max_retries and _should_retry_http(status_code):
                # Groq 429 rate limits often require a longer backoff
                time.sleep(2.5 * (attempt + 1))
                continue
            reason = _classify_http_error(status_code, detail)
            parsed = _default_response(run_id=run_id, model=model, status="failed", reason=reason)
            break
        except urllib.error.URLError as err:
            if attempt < max_retries:
                time.sleep(2.5 * (attempt + 1))
                continue
            parsed = _default_response(
                run_id=run_id,
                model=model,
                status="failed",
                reason=f"Groq network error: {str(getattr(err, 'reason', err))[:180]}",
            )
            break
        except Exception as err:
            if attempt < max_retries:
                time.sleep(0.7 * (attempt + 1))
                continue
            parsed = _default_response(run_id=run_id, model=model, status="failed", reason=f"Groq request failed: {str(err)[:180]}")
            break

    if parsed is None:
        raw_obj = _parse_json_object(raw)
        if not raw_obj:
            parsed = _default_response(run_id=run_id, model=model, status="failed", reason="Groq returned non-JSON response")
        else:
            try:
                content = raw_obj["choices"][0]["message"]["content"]
            except Exception:
                content = ""
            
            parsed_content = _parse_json_object(content)
            if not parsed_content:
                parsed = _default_response(run_id=run_id, model=model, status="failed", reason="Groq content parsing failed")
            else:
                parsed = parsed_content

    sanitized = _validate_and_sanitize(
        payload=parsed,
        run_id=run_id,
        model=model,
        jd_text=jd_text,
        resume_text=resume_text,
        jd_skills=jd_skills,
        resume_skills=resume_skills,
        missing_skills=missing_skills,
    )

    # Deterministic backfill guarantees meaningful output when the LLM is sparse.
    deterministic_triage = _build_deterministic_triage(missing_skills, jd_text)
    deterministic_focus = _build_deterministic_interview_focus(deterministic_triage)
    deterministic_mappings = _build_deterministic_normalization(partition)
    deterministic_narrative = _build_deterministic_narrative(
        score=_to_float(summary.get("overall_alignment_score"), 0.0),
        exact_count=int(_to_float(summary.get("exact_match_count"), 0.0)),
        semantic_count=int(_to_float(summary.get("semantic_match_count"), 0.0)),
        missing_count=int(_to_float(summary.get("missing_skills_count"), 0.0)),
        total_skills=int(_to_float(summary.get("total_jd_skills"), 0.0)) or max(1, len(jd_skills)),
        domain=domain,
    )

    triage_before = len(sanitized["missing_skill_triage"])
    focus_before = len(sanitized["interview_focus"])
    map_before = len(sanitized["normalization"]["mappings"])

    sanitized["missing_skill_triage"] = _merge_unique_dict_items(
        sanitized["missing_skill_triage"],
        deterministic_triage,
        key_name="skill",
        limit=8,
    )
    sanitized["interview_focus"] = _merge_unique_dict_items(
        sanitized["interview_focus"],
        deterministic_focus,
        key_name="topic",
        limit=6,
    )

    existing_mappings = sanitized["normalization"]["mappings"]
    deduped_mappings = []
    map_keys = set()
    for item in [*existing_mappings, *deterministic_mappings]:
        if not isinstance(item, dict):
            continue
        src = _clean_term(item.get("source_term")).lower()
        dst = _clean_term(item.get("normalized_term")).lower()
        if not src or not dst:
            continue
        key = f"{src}->{dst}"
        if key in map_keys:
            continue
        map_keys.add(key)
        deduped_mappings.append(item)
        if len(deduped_mappings) >= 12:
            break
    sanitized["normalization"]["mappings"] = deduped_mappings

    if len(sanitized["missing_skill_triage"]) > triage_before:
        sanitized["quality"]["warnings"].append("Triage list supplemented with deterministic fallback guidance")
    if len(sanitized["interview_focus"]) > focus_before:
        sanitized["quality"]["warnings"].append("Interview focus supplemented with deterministic fallback prompts")
    if len(sanitized["normalization"]["mappings"]) > map_before:
        sanitized["quality"]["warnings"].append("Normalization mappings supplemented from semantic matching layer")

    narrative = sanitized.get("report_narrative", {})
    for field in ["executive_overview", "interview_strategy", "final_recommendation"]:
        if not _clean_term(narrative.get(field)):
            narrative[field] = deterministic_narrative[field]

    if not isinstance(narrative.get("strengths"), list) or len(narrative.get("strengths", [])) < 2:
        narrative["strengths"] = deterministic_narrative["strengths"]

    if not isinstance(narrative.get("risk_flags"), list) or len(narrative.get("risk_flags", [])) < 2:
        narrative["risk_flags"] = deterministic_narrative["risk_flags"]

    if not isinstance(narrative.get("onboarding_plan"), list) or len(narrative.get("onboarding_plan", [])) < 2:
        narrative["onboarding_plan"] = deterministic_narrative["onboarding_plan"]

    sanitized["report_narrative"] = narrative

    sanitized["quality"]["coverage_score"] = max(
        _to_float(sanitized["quality"].get("coverage_score"), 0.0),
        _compute_coverage_score(
            triage_count=len(sanitized["missing_skill_triage"]),
            interview_count=len(sanitized["interview_focus"]),
            mapping_count=len(sanitized["normalization"]["mappings"]),
            missing_count=len(missing_skills),
            semantic_candidates=len(partition.get("strong_semantic", []) if isinstance(partition.get("strong_semantic"), list) else [])
            + len(partition.get("moderate_semantic", []) if isinstance(partition.get("moderate_semantic"), list) else []),
            narrative_items=sum(
                [
                    1 if _clean_term(sanitized["report_narrative"].get("executive_overview")) else 0,
                    len(sanitized["report_narrative"].get("strengths", [])),
                    len(sanitized["report_narrative"].get("risk_flags", [])),
                    len(sanitized["report_narrative"].get("onboarding_plan", [])),
                    1 if _clean_term(sanitized["report_narrative"].get("interview_strategy")) else 0,
                    1 if _clean_term(sanitized["report_narrative"].get("final_recommendation")) else 0,
                ]
            ),
        ),
    )

    # ── Deterministic fallbacks for new fields ──────────────────────────────
    _score   = _to_float(summary.get("overall_alignment_score"), 0.0)
    _exact   = int(_to_float(summary.get("exact_match_count"),   0.0))
    _sem     = int(_to_float(summary.get("semantic_match_count"), 0.0))
    _miss_n  = int(_to_float(summary.get("missing_skills_count"), 0.0))
    _total   = int(_to_float(summary.get("total_jd_skills"), 0.0)) or max(1, len(jd_skills))

    # ATS readiness — backfill if Groq didn't return a valid verdict
    if not sanitized.get("ats_readiness", {}).get("verdict"):
        sanitized["ats_readiness"] = _build_deterministic_ats_readiness(
            score=_score, missing_count=_miss_n,
            total_skills=_total, exact_count=_exact,
        )

    # Hard skills narrative — backfill if empty
    if not sanitized.get("hard_skills_narrative", "").strip():
        sanitized["hard_skills_narrative"] = _build_deterministic_hard_skills_narrative(
            exact_count=_exact, semantic_count=_sem,
            missing_count=_miss_n, total_skills=_total, domain=domain,
        )

    # Soft skills assessment — backfill if narrative empty
    if not sanitized.get("soft_skills_assessment", {}).get("narrative", "").strip():
        sanitized["soft_skills_assessment"] = _build_deterministic_soft_skills_assessment(
            resume_skills=resume_skills, jd_skills=jd_skills, partition=partition,
        )

    # Top recommendations — backfill if fewer than 2 items
    if len(sanitized.get("top_recommendations", [])) < 2:
        sanitized["top_recommendations"] = _build_deterministic_top_recommendations(
            triage=sanitized["missing_skill_triage"], score=_score,
        )

    # Strengthen quality warnings if little usable enrichment was produced.
    usable_count = len(sanitized["normalization"]["mappings"]) + len(sanitized["missing_skill_triage"]) + len(sanitized["interview_focus"])
    if usable_count == 0:
        sanitized["quality"]["warnings"].append("AI response produced no usable enrichment items after validation")
        sanitized["quality"]["hallucination_risk"] = "high"

    mode = os.getenv("AI_ENRICHMENT_MODE", "shadow").strip().lower()
    if mode not in {"shadow", "active"}:
        mode = "shadow"
    sanitized["mode"] = mode

    return sanitized

