import argparse
import json
from pathlib import Path
from statistics import mean

from services.analyzer import extract_skills
from services.taxonomy_analyzer import analyze_semantic_matching
from services.preprocessor import generate_versions


def load_metadata(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def get_domain(metadata: dict) -> str:
    return metadata.get("resume_skills", {}).get("domain") or metadata.get("jd_skills", {}).get("domain") or "software"


def reanalyze(metadata: dict) -> dict:
    domain = get_domain(metadata)

    resume_raw = metadata.get("resume_versions", {}).get("raw_text", "")
    jd_raw = metadata.get("jd_versions", {}).get("raw_text", "")

    resume_versions = generate_versions(resume_raw)
    jd_versions = generate_versions(jd_raw)

    resume_skills = extract_skills(resume_versions["light_clean_text"], domain=domain)
    jd_skills = extract_skills(jd_versions["light_clean_text"], domain=domain)

    jd_flat_skills = jd_skills.get("technical_skills", []) + jd_skills.get("soft_skills", [])
    resume_flat_skills = resume_skills.get("technical_skills", []) + resume_skills.get("soft_skills", [])

    bert_results = analyze_semantic_matching(
        jd_flat_skills,
        resume_flat_skills,
        resume_versions["raw_text"],
        domain=domain,
        threshold=0.50,
        jd_text=jd_versions["raw_text"],
    )

    return {
        "domain": domain,
        "resume_skills": resume_skills,
        "jd_skills": jd_skills,
        "bert_results": bert_results,
    }


def summary_or_default(metadata: dict) -> dict:
    return metadata.get("bert_results", {}).get("summary", {
        "total_jd_skills": 0,
        "resume_detected_skills": 0,
        "exact_match_count": 0,
        "semantic_match_count": 0,
        "missing_skills_count": 0,
        "overall_alignment_score": 0.0,
    })


def delta(old: dict, new: dict) -> dict:
    keys = [
        "total_jd_skills",
        "resume_detected_skills",
        "exact_match_count",
        "semantic_match_count",
        "missing_skills_count",
        "overall_alignment_score",
    ]
    out = {}
    for key in keys:
        out[key] = round(float(new.get(key, 0)) - float(old.get(key, 0)), 3)
    return out


def derive_rates(summary: dict) -> dict:
    total = float(summary.get("total_jd_skills", 0) or 0)
    exact = float(summary.get("exact_match_count", 0) or 0)
    semantic = float(summary.get("semantic_match_count", 0) or 0)
    missing = float(summary.get("missing_skills_count", 0) or 0)

    if total <= 0:
        return {
            "coverage_rate": 0.0,
            "exact_rate": 0.0,
            "semantic_rate": 0.0,
            "missing_rate": 0.0,
        }

    return {
        "coverage_rate": round(((exact + semantic) / total) * 100, 3),
        "exact_rate": round((exact / total) * 100, 3),
        "semantic_rate": round((semantic / total) * 100, 3),
        "missing_rate": round((missing / total) * 100, 3),
    }


def run(sessions_dir: Path, domain_filter: str | None, limit: int | None):
    session_dirs = sorted([p for p in sessions_dir.iterdir() if p.is_dir() and p.name.startswith("ext_")])
    if limit:
        session_dirs = session_dirs[:limit]

    rows = []
    failures = []

    for session_dir in session_dirs:
        metadata_path = session_dir / "metadata.json"
        if not metadata_path.exists():
            continue

        try:
            metadata = load_metadata(metadata_path)
            domain = get_domain(metadata)
            if domain_filter and domain != domain_filter:
                continue

            reevaluated = reanalyze(metadata)

            old_summary = summary_or_default(metadata)
            new_summary = reevaluated["bert_results"].get("summary", {})
            old_rates = derive_rates(old_summary)
            new_rates = derive_rates(new_summary)

            row = {
                "session_id": metadata.get("session_id", session_dir.name),
                "domain": domain,
                "old_summary": old_summary,
                "new_summary": new_summary,
                "delta": delta(old_summary, new_summary),
                "old_rates": old_rates,
                "new_rates": new_rates,
                "rate_delta": {
                    "coverage_rate": round(new_rates["coverage_rate"] - old_rates["coverage_rate"], 3),
                    "exact_rate": round(new_rates["exact_rate"] - old_rates["exact_rate"], 3),
                    "semantic_rate": round(new_rates["semantic_rate"] - old_rates["semantic_rate"], 3),
                    "missing_rate": round(new_rates["missing_rate"] - old_rates["missing_rate"], 3),
                },
            }
            rows.append(row)
        except Exception as ex:
            failures.append({"session_id": session_dir.name, "error": str(ex)})

    aggregate = {}
    if rows:
        for key in rows[0]["delta"].keys():
            aggregate[f"avg_delta_{key}"] = round(mean(r["delta"][key] for r in rows), 3)
        for key in rows[0]["rate_delta"].keys():
            aggregate[f"avg_rate_delta_{key}"] = round(mean(r["rate_delta"][key] for r in rows), 3)

    return {
        "sessions_evaluated": len(rows),
        "sessions_failed": len(failures),
        "aggregate": aggregate,
        "results": rows,
        "failures": failures,
    }


def main():
    parser = argparse.ArgumentParser(description="Re-evaluate saved sessions and compare old/new semantic summaries.")
    parser.add_argument("--sessions-dir", default="backend/data/sessions", help="Path to sessions folder")
    parser.add_argument("--output", default="backend/data/session_re_evaluation_report.json", help="Output JSON report path")
    parser.add_argument("--domain", default=None, help="Optional domain filter (e.g. software)")
    parser.add_argument("--limit", type=int, default=None, help="Optional max number of sessions to process")

    args = parser.parse_args()

    sessions_dir = Path(args.sessions_dir)
    output_path = Path(args.output)

    report = run(sessions_dir, args.domain, args.limit)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"Sessions evaluated: {report['sessions_evaluated']}")
    print(f"Sessions failed: {report['sessions_failed']}")
    if report["aggregate"]:
        print("Average delta summary:")
        for k, v in report["aggregate"].items():
            print(f" - {k}: {v}")
    print(f"Report saved to: {output_path}")


if __name__ == "__main__":
    main()
