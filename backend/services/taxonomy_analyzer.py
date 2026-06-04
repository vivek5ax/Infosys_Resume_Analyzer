import re
import asyncio
import os
from .taxonomy_loader import load_taxonomy
from .enhanced_matcher import EnhancedSemanticMatcher

# Tunable thresholds logic (kept for compatibility with frontend UI expectations)
STRONG_SIMILARITY_THRESHOLD = 0.85
MODERATE_SIMILARITY_THRESHOLD = 0.60

# Feature flag for using enhanced matcher vs legacy zero-ML
USE_ENHANCED_MATCHER = os.getenv("USE_ENHANCED_MATCHER", "true").lower() == "true"
USE_LLM_SEMANTIC = os.getenv("USE_LLM_SEMANTIC", "true").lower() == "true"

def _normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()

def _extract_snippet(text: str, needle: str, radius: int = 100) -> str:
    source = text or ""
    if not source.strip() or not needle:
        return ""

    pattern = re.compile(rf"\b{re.escape(needle)}\b", re.IGNORECASE)
    match = pattern.search(source)
    if not match:
        return ""

    start = max(0, match.start() - radius)
    end = min(len(source), match.end() + radius)
    snippet = source[start:end]
    return _normalize_spaces(snippet)

def _build_match_evidence(partition: dict, missing: list, jd_text: str, resume_text: str, limit: int = 24) -> list:
    evidence = []

    for skill in partition.get("exact_match", []):
        evidence.append({
            "skill": skill,
            "match_type": "exact",
            "confidence": 1.0,
            "jd_skill": skill,
            "resume_skill": skill,
            "jd_snippet": _extract_snippet(jd_text, skill),
            "resume_snippet": _extract_snippet(resume_text, skill),
        })

    for item in partition.get("strong_semantic", []):
        evidence.append({
            "skill": item.get("similar_to"),
            "match_type": "strong_semantic",
            "confidence": float(item.get("score", 0.0)),
            "jd_skill": item.get("similar_to"),
            "resume_skill": item.get("skill"),
            "jd_snippet": _extract_snippet(jd_text, item.get("similar_to", "")),
            "resume_snippet": _extract_snippet(resume_text, item.get("skill", "")),
        })

    for item in partition.get("moderate_semantic", []):
        evidence.append({
            "skill": item.get("similar_to"),
            "match_type": "moderate_semantic",
            "confidence": float(item.get("score", 0.0)),
            "jd_skill": item.get("similar_to"),
            "resume_skill": item.get("skill"),
            "jd_snippet": _extract_snippet(jd_text, item.get("similar_to", "")),
            "resume_snippet": _extract_snippet(resume_text, item.get("skill", "")),
        })

    for item in missing:
        evidence.append({
            "skill": item.get("skill"),
            "match_type": "missing",
            "confidence": 0.0,
            "jd_skill": item.get("skill"),
            "resume_skill": None,
            "jd_snippet": _extract_snippet(jd_text, item.get("skill", "")),
            "resume_snippet": "",
            "weight": item.get("weight", 1.0),
        })

    evidence.sort(key=lambda item: item.get("confidence", 0), reverse=True)
    return evidence[:limit]

async def analyze_semantic_matching(raw_jd_displays: list, raw_resume_displays: list, resume_text: str, domain: str = "software", threshold: float = 0.50, jd_text: str = ""):
    """
    Enhanced Semantic Matcher with multi-tiered approach.
    Uses the enhanced matcher if enabled, otherwise falls back to legacy zero-ML approach.
    """
    if USE_ENHANCED_MATCHER:
        print(f"\n--- Using Enhanced Semantic Matcher [Domain: {domain}] ---")
        matcher = EnhancedSemanticMatcher(domain)
        return await matcher.analyze_semantic_matching(
            raw_jd_displays, 
            raw_resume_displays, 
            resume_text, 
            jd_text, 
            use_llm=USE_LLM_SEMANTIC
        )
    else:
        print(f"\n--- Using Legacy Zero-ML Matcher [Domain: {domain}] ---")
        return await _legacy_analyze_semantic_matching(
            raw_jd_displays, raw_resume_displays, resume_text, domain, threshold, jd_text
        )

async def _legacy_analyze_semantic_matching(raw_jd_displays: list, raw_resume_displays: list, resume_text: str, domain: str = "software", threshold: float = 0.50, jd_text: str = ""):
    """
    Lightning-fast, Zero-ML, Algorithmic Semantic Matcher using Taxonomy Categories.
    (Legacy version for backward compatibility)
    """
    print(f"\n--- Starting Algorithmic Taxonomy Matcher [Domain: {domain}] ---")
    
    taxonomy_data = load_taxonomy(domain)
    skills_flat = taxonomy_data["skills_flat"]
    aliases_map = taxonomy_data["aliases_map"]
    
    jd_skills = [s for s in raw_jd_displays]
    resume_skills = [s for s in raw_resume_displays]
    
    partition = {
        "exact_match": [],
        "strong_semantic": [],
        "moderate_semantic": [],
        "irrelevant": []
    }
    
    missing_from_resume = []
    
    if len(jd_skills) == 0:
        partition["irrelevant"] = raw_resume_displays
        return {
             "summary": {
                "total_jd_skills": 0,
                "resume_detected_skills": len(resume_skills),
                "exact_match_count": 0,
                "semantic_match_count": 0,
                "missing_skills_count": 0,
                "overall_alignment_score": 0.0
            },
            "skill_partition": partition,
            "missing_from_resume": [],
            "extra_resume_skills": raw_resume_displays,
            "jd_skill_clusters": {},
            "resume_skill_clusters": {},
            "match_evidence": []
        }

    # Prepare canonical mappings for JD skills
    jd_canonical_map = {}
    for j_display in jd_skills:
        j_lower = j_display.lower()
        j_canon = aliases_map.get(j_lower, j_lower)
        jd_canonical_map[j_canon] = j_display
    
    # 1. Map Resume Skills
    for r_display in resume_skills:
        r_lower = r_display.lower()
        r_canon = aliases_map.get(r_lower, r_lower)
        
        # Check Exact Matches (including aliases)
        if r_canon in jd_canonical_map:
            # We map it to the exact text requested by JD
            partition["exact_match"].append(r_display)
            continue
            
        # Check Semantic Matches (Shared Categories)
        r_cats = skills_flat.get(r_canon, {}).get("categories", [])
        
        best_match_j_display = None
        best_match_score = 0.0
        
        for j_canon, j_display in jd_canonical_map.items():
            j_cats = skills_flat.get(j_canon, {}).get("categories", [])
            shared_cats = set(r_cats).intersection(set(j_cats))
            
            if shared_cats:
                # Calculate simple Jaccard similarity of categories as confidence score
                score = len(shared_cats) / len(set(r_cats).union(set(j_cats)))
                # Scale up to strong/moderate bounds
                mapped_score = 0.65 + (score * 0.25)
                
                if mapped_score > best_match_score:
                    best_match_score = mapped_score
                    best_match_j_display = j_display
        
        if best_match_j_display:
            if best_match_score >= STRONG_SIMILARITY_THRESHOLD:
                partition["strong_semantic"].append({
                    "skill": r_display,
                    "similar_to": best_match_j_display,
                    "score": round(best_match_score, 2)
                })
            else:
                partition["moderate_semantic"].append({
                    "skill": r_display,
                    "similar_to": best_match_j_display,
                    "score": round(best_match_score, 2)
                })
        else:
            partition["irrelevant"].append(r_display)

    # 2. Check Raw Text Fallback for Exact Matches (in case OCR missed standard extraction)
    matched_jd_lowered = set([s.lower() for s in partition["exact_match"]])
    for d in partition["strong_semantic"]:
        matched_jd_lowered.add(d["similar_to"].lower())
    for d in partition["moderate_semantic"]:
        matched_jd_lowered.add(d["similar_to"].lower())

    missing_candidates = [display for display in raw_jd_displays if display.lower() not in matched_jd_lowered]
    
    for candidate in missing_candidates:
        candidate_lower = candidate.lower()
        candidate_canon = aliases_map.get(candidate_lower, candidate_lower)
        skill_info = skills_flat.get(candidate_canon, {})
        canonical_display = skill_info.get("display", candidate).lower()
        
        has_exact = False
        if len(canonical_display) <= 3:
            if re.search(rf'\b{re.escape(canonical_display)}\b', resume_text.lower()):
                has_exact = True
        else:
            if canonical_display in resume_text.lower():
                has_exact = True
        
        if has_exact:
            partition["exact_match"].append(candidate)
            matched_jd_lowered.add(candidate_lower)

    # 3. Compute Missing Skills
    for j_display in raw_jd_displays:
        if j_display.lower() not in matched_jd_lowered:
            j_lower = j_display.lower()
            j_canon = aliases_map.get(j_lower, j_lower)
            info = skills_flat.get(j_canon, {})
            missing_from_resume.append({
                "skill": j_display,
                "weight": info.get("max_weight", 1.0),
                "categories": info.get("categories", ["Unknown"])
            })
            
    missing_from_resume.sort(key=lambda x: x["weight"], reverse=True)
    
    def rebuild_clusters(skill_displays):
        clusters = {}
        for display in skill_displays:
            d_lower = display.lower()
            d_canon = aliases_map.get(d_lower, d_lower)
            cats = skills_flat.get(d_canon, {}).get("categories", ["Unknown"])
            for c in cats:
                if c not in clusters: clusters[c] = []
                clusters[c].append(display)
        return clusters
        
    jd_clusters = rebuild_clusters(raw_jd_displays)
    resume_clusters = rebuild_clusters(raw_resume_displays)
    
    # 4. Calculate Final Alignment Score
    total_weight = sum([skills_flat.get(aliases_map.get(s.lower(), s.lower()), {}).get("max_weight", 1.0) for s in raw_jd_displays])
    
    if total_weight > 0:
        matched_jd_weight = 0.0
        counted = set()

        for match in partition["exact_match"]:
            key = aliases_map.get(match.lower(), match.lower())
            if key not in counted:
                matched_jd_weight += skills_flat.get(key, {}).get("max_weight", 1.0)
                counted.add(key)

        for strong in partition["strong_semantic"]:
            key = aliases_map.get(strong["similar_to"].lower(), strong["similar_to"].lower())
            if key not in counted:
                matched_jd_weight += skills_flat.get(key, {}).get("max_weight", 1.0) * 0.8
                counted.add(key)

        for mod in partition["moderate_semantic"]:
            key = aliases_map.get(mod["similar_to"].lower(), mod["similar_to"].lower())
            if key not in counted:
                matched_jd_weight += skills_flat.get(key, {}).get("max_weight", 1.0) * 0.5
                counted.add(key)

        overall_score = round((matched_jd_weight / total_weight) * 100, 1)
    else:
        overall_score = 0.0

    evidence_items = _build_match_evidence(partition, missing_from_resume, jd_text, resume_text)

    # Clean duplicates in exact match
    partition["exact_match"] = list(set(partition["exact_match"]))

    return {
         "summary": {
            "total_jd_skills": len(raw_jd_displays),
            "resume_detected_skills": len(raw_resume_displays),
            "exact_match_count": len(partition["exact_match"]),
            "semantic_match_count": len(partition["strong_semantic"]) + len(partition["moderate_semantic"]),
            "missing_skills_count": len(missing_from_resume),
            "overall_alignment_score": overall_score
        },
        "skill_partition": partition,
        "missing_from_resume": missing_from_resume,
        "extra_resume_skills": partition["irrelevant"],
        "jd_skill_clusters": jd_clusters,
        "resume_skill_clusters": resume_clusters,
        "match_evidence": evidence_items
    }
