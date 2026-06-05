import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List

DEFAULT_MODEL = "llama-3.1-8b-instant"
DEFAULT_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_TIMEOUT_SEC = 18.0
DEFAULT_MAX_RETRIES = 2

MATCH_API_KEY_ENV = "GROQ_MATCH_API_KEY"
FALLBACK_API_KEY_ENV = "GROQ_API_KEY"
MODEL_ENV = "GROQ_MATCH_MODEL"
URL_ENV = "GROQ_MATCH_API_URL"
TIMEOUT_ENV = "GROQ_TIMEOUT_SEC"
RETRIES_ENV = "GROQ_MAX_RETRIES"
ENABLED_ENV = "GROQ_MATCH_ENABLED"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_float(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return fallback


def _normalize_text(text: str) -> str:
    value = str(text or "").strip()
    value = re.sub(r"\s+", " ", value)
    return value


def truncate_smart(text: str, limit: int = 3000) -> str:
    if not text:
        return ""
    text = _normalize_text(text)
    if len(text) <= limit:
        return text

    prefix_len = int(limit * 0.55)
    suffix_len = limit - prefix_len - 5
    prefix = text[:prefix_len].rsplit(".", 1)[0].strip()
    suffix = text[-suffix_len:].split(".", 1)[-1].strip()

    if not prefix:
        prefix = text[:prefix_len].strip()
    if not suffix:
        suffix = text[-suffix_len:].strip()

    return f"{prefix} ... {suffix}"


def _default_response(run_id: str, status: str, reason: str = "") -> Dict[str, Any]:
    return {
        "status": status,
        "run_id": run_id,
        "model": os.getenv(MODEL_ENV, os.getenv("GROQ_MODEL", DEFAULT_MODEL)).strip(),
        "created_at": _now_iso(),
        "reason": reason,
        "context_validations": [],
        "summary": {},
        "warnings": [reason] if reason else [],
    }


def _classify_http_error(status_code: int, detail: str) -> str:
    text = (detail or "").lower()
    if "error code: 1010" in text:
        return "Groq access denied (Cloudflare 1010). This is usually a network/IP policy block."
    if status_code == 401 or "invalid api key" in text:
        return "Groq authentication failed (401). Verify GROQ_MATCH_API_KEY or GROQ_API_KEY."
    if status_code == 429:
        return "Groq rate limit reached (429). Retry after a short delay."
    if status_code in {500, 502, 503, 504}:
        return f"Groq service temporarily unavailable ({status_code})."
    compact = re.sub(r"\s+", " ", detail or "")[:180]
    return f"Groq HTTP error ({status_code}): {compact}" if compact else f"Groq HTTP error ({status_code})"


def _parse_json_object(payload: str) -> Dict[str, Any]:
    if not payload:
        return {}

    try:
        return json.loads(payload)
    except Exception:
        pass

    match = re.search(r"\{(?:[^{}]|(?R))*\}", payload, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass

    return {}


def _build_prompt(run_id: str, domain: str, jd_text: str, resume_text: str, partition: Dict[str, Any], missing_from_resume: List[Any], extra_resume_skills: List[Any], summary: Dict[str, Any]) -> Dict[str, Any]:
    short_resume = truncate_smart(resume_text, 2600)
    short_jd = truncate_smart(jd_text, 2600)

    system_prompt = (
        "You are an expert resume vs job description context validation assistant. "
        "Use ONLY the provided text, match partitions, and summary data. "
        "Do not hallucinate or invent new skills. Output a single JSON object only. "
        "No markdown, no extra commentary."
    )

    payload = {
        "run_id": run_id,
        "domain": domain,
        "summary": summary,
        "skill_partition": partition,
        "missing_from_resume": missing_from_resume,
        "skills_to_be_categorized": extra_resume_skills,
        "job_description_text": short_jd,
        "resume_text": short_resume,
    }

    user_prompt = (
        "Validate the JD/resume match context for semantic and missing skills. "
        "Return a JSON object with the following top-level keys: context_validations, context_summary, status, run_id, model. "
        "INSTRUCTIONS:\n"
        "1. IGNORE Exact Matches. Do not return them.\n"
        "2. Analyze 'missing_from_resume' skills: Read the resume text to see if the candidate describes doing this implicitly. EXTREMELY IMPORTANT: Only classify as 'Implicit Match' if the candidate explicitly describes the exact underlying concept (e.g. 'NLP' implies 'LLMs'). DO NOT make conceptual leaps across entirely different tech stacks (e.g. 'Spring Boot' DOES NOT imply 'Machine Learning' or 'Docker'). If there is no direct evidence, classify as 'Actual Gap'.\n"
        "3. Validate 'strong_semantic' and 'moderate_semantic' matches: Read the JD and Resume contexts. Are they talking about the same thing? If yes, classify as 'Contextually Validated'. If they are completely different contexts or stacks (e.g. Java vs Python), classify as 'False Positive'.\n"
        "4. Analyze 'skills_to_be_categorized' (found in resume but unmapped). Check if they implicitly match any JD requirement strictly without hallucinations. If yes, classify as 'Implicit Match'. If they are genuinely new but valuable to the role, classify as 'Additional Skill'. If irrelevant, classify as 'False Positive'.\n"
        "5. Scan the raw 'job_description_text'. Are there any critical skills explicitly demanded in the JD that were NOT listed in the partitions or 'missing_from_resume'? If yes, extract them. Check the resume: if strictly present, classify as 'Implicit Match' or 'Contextually Validated'; if missing, classify as 'Actual Gap'.\n"
        "context_validations should be an array of objects. Each object must have these keys:\n"
        "- 'skill_name': The name of the skill.\n"
        "- 'analysis_type': Must be 'Implicit Match', 'Actual Gap', 'Contextually Validated', 'False Positive', or 'Additional Skill'.\n"
        "- 'jd_context': The exact sentence/snippet from the Job Description demanding the skill (leave empty if Additional Skill).\n"
        "- 'resume_context': The exact sentence/snippet from the Resume supporting it (leave empty if Actual Gap).\n"
        "- 'reasoning': A brief explanation of why this match is valid or what the candidate is lacking.\n"
        "Also include a short 'context_summary' sentence summarizing the hidden skills found, false positives identified, and additional skills discovered. "
        "Only include items that can be supported from the input data."
        f"\n\nINPUT:\n{json.dumps(payload, ensure_ascii=False)}"
    )

    return {
        "model": os.getenv(MODEL_ENV, os.getenv("GROQ_MODEL", DEFAULT_MODEL)).strip(),
        "temperature": 0.0,
        "max_tokens": 1200,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }


def _get_api_config() -> Dict[str, Any]:
    api_key = os.getenv(MATCH_API_KEY_ENV, "").strip()
    if not api_key:
        api_key = os.getenv(FALLBACK_API_KEY_ENV, "").strip()

    enabled = os.getenv(ENABLED_ENV, "true").strip().lower() in {"1", "true", "yes", "on"}
    return {
        "enabled": enabled,
        "api_key": api_key,
        "model": os.getenv(MODEL_ENV, os.getenv("GROQ_MODEL", DEFAULT_MODEL)).strip(),
        "url": os.getenv(URL_ENV, os.getenv("GROQ_API_URL", DEFAULT_URL)).strip(),
        "timeout": max(4.0, min(60.0, _to_float(os.getenv(TIMEOUT_ENV, DEFAULT_TIMEOUT_SEC), DEFAULT_TIMEOUT_SEC))),
        "retries": int(max(0, min(3, _to_float(os.getenv(RETRIES_ENV, DEFAULT_MAX_RETRIES), DEFAULT_MAX_RETRIES)))),
    }


def master_skill_analysis(
    *,
    run_id: str,
    domain: str,
    jd_text: str,
    resume_text: str,
    partition: Dict[str, Any],
    missing_from_resume: List[Any],
    extra_resume_skills: List[Any],
    summary: Dict[str, Any],
) -> Dict[str, Any]:
    config = _get_api_config()
    if not config["enabled"]:
        return _default_response(run_id=run_id, status="disabled", reason="GROQ_MATCH_ENABLED is false")
    if not config["api_key"]:
        return _default_response(run_id=run_id, status="disabled", reason="GROQ_MATCH_API_KEY and GROQ_API_KEY are not configured")

    request_body = _build_prompt(run_id, domain, jd_text, resume_text, partition, missing_from_resume, extra_resume_skills, summary)
    request_bytes = json.dumps(request_body, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {config['api_key']}",
        "User-Agent": "ResumeAnalyzer/1.0",
    }

    raw_response = ""
    for attempt in range(config["retries"] + 1):
        req = urllib.request.Request(
            config["url"],
            data=request_bytes,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=config["timeout"]) as resp:
                raw_response = resp.read().decode("utf-8", errors="ignore")
            break
        except urllib.error.HTTPError as err:
            status_code = int(getattr(err, "code", 0) or 0)
            detail = err.read().decode("utf-8", errors="ignore") if hasattr(err, "read") else str(err)
            if attempt < config["retries"] and status_code in {408, 425, 429, 500, 502, 503, 504}:
                time.sleep(0.7 * (attempt + 1))
                continue
            reason = _classify_http_error(status_code, detail)
            return _default_response(run_id=run_id, status="failed", reason=reason)
        except urllib.error.URLError as err:
            if attempt < config["retries"]:
                time.sleep(0.7 * (attempt + 1))
                continue
            return _default_response(run_id=run_id, status="failed", reason=f"Groq network error: {str(getattr(err, 'reason', err))[:180]}")
        except Exception as err:
            if attempt < config["retries"]:
                time.sleep(0.7 * (attempt + 1))
                continue
            return _default_response(run_id=run_id, status="failed", reason=f"Groq request failed: {str(err)[:180]}")

    raw_obj = _parse_json_object(raw_response)
    if not raw_obj:
        return _default_response(run_id=run_id, status="failed", reason="Groq returned non-JSON response")

    try:
        parsed = _parse_json_object(raw_obj.get("choices", [])[0].get("message", {}).get("content", ""))
    except Exception:
        parsed = {}

    if not isinstance(parsed, dict):
        return _default_response(run_id=run_id, status="failed", reason="Groq content parsing failed")

    result = {
        "status": parsed.get("status", "ok"),
        "run_id": run_id,
        "model": config["model"],
        "created_at": _now_iso(),
        "reason": parsed.get("reason", ""),
        "context_validations": parsed.get("context_validations", []),
        "context_summary": parsed.get("context_summary", ""),
        "summary": parsed.get("summary", {}),
        "warnings": parsed.get("warnings", []),
    }

    if not isinstance(result["context_validations"], list):
        result["context_validations"] = []
    if not isinstance(result["summary"], dict):
        result["summary"] = {}
    if not isinstance(result["warnings"], list):
        result["warnings"] = []

    return result
