import os
import spacy
from spacy.matcher import PhraseMatcher
from spacy.util import filter_spans
from collections import Counter
import re
from .taxonomy_loader import load_taxonomy, BASE_PATH

# Global Cache to prevent rebuilding pipelines and matchers
DOMAIN_NLP = {}
DOMAIN_MATCHERS = {}
DOMAIN_MTIME = {}

def get_domain_nlp(domain: str):
    """
    Retrieves or builds the spaCy NLP object and PhraseMatcher for a specific domain.
    Caches the results globally for production-grade thread safety and massive performance gains.
    Auto-invalidates if the taxonomy JSON files are edited.
    """
    domain_clean = re.sub(r'[^a-z0-9_]', '', domain.lower().replace(' ', '_'))
    domain_path = os.path.join(BASE_PATH, f"{domain_clean}.json")
    soft_path = os.path.join(BASE_PATH, "soft_skills.json")
    
    current_mtime = 0
    if os.path.exists(domain_path):
        current_mtime += os.path.getmtime(domain_path)
    if os.path.exists(soft_path):
        current_mtime += os.path.getmtime(soft_path)
        
    if domain in DOMAIN_NLP and DOMAIN_MTIME.get(domain) == current_mtime:
        return DOMAIN_NLP[domain], DOMAIN_MATCHERS[domain]
        
    print(f"[NLP] Building new NLP pipeline and PhraseMatcher for domain: {domain}")
    
    # Disable unnecessary components for severe speed boost
    nlp = spacy.load("en_core_web_sm", disable=["ner", "parser"])
    
    # Use PhraseMatcher mapped to the LOWER attribute to cleanly handle casing
    matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
    
    # Load standardized canonical taxonomy
    taxonomy_data = load_taxonomy(domain)
    skills_flat = taxonomy_data["skills_flat"]
    aliases_map = taxonomy_data["aliases_map"]
    
    # Build token-based patterns to avoid substring matches (e.g., 'R' matching 'aRe')
    for norm_name, skill_info in skills_flat.items():
        is_soft = "soft_skills" in skill_info["source_domains"]
        label = "SOFT_SKILL" if is_soft else (skill_info["categories"][0] if skill_info["categories"] else "TECHNICAL_SKILL")
        
        # Primary Token Sequence (Uses nlp.make_doc to create safe token boundaries)
        doc_pattern = nlp.make_doc(skill_info["display"].lower())
        matcher.add(label, [doc_pattern])
        
    for alias_norm, canonical_norm in aliases_map.items():
        if canonical_norm in skills_flat:
            skill_info = skills_flat[canonical_norm]
            is_soft = "soft_skills" in skill_info["source_domains"]
            label = "SOFT_SKILL" if is_soft else (skill_info["categories"][0] if skill_info["categories"] else "TECHNICAL_SKILL")
            
            doc_pattern = nlp.make_doc(alias_norm)
            matcher.add(label, [doc_pattern])

    # Cache locally
    DOMAIN_NLP[domain] = nlp
    DOMAIN_MATCHERS[domain] = matcher
    DOMAIN_MTIME[domain] = current_mtime
    
    return nlp, matcher


def sanitize_resume_text(text: str) -> str:
    """
    Strips trailing JD skill lists or 'Expected Skill Extraction' blocks from resume text 
    if the document is contaminated (e.g. from previous analyzer runs).
    """
    leakage_markers = [
        "expected skill extraction",
        "jd skills detected",
        "extracted jd skills",
        "resume analyzer results"
    ]
    
    lower_text = text.lower()
    for marker in leakage_markers:
        if marker in lower_text:
            split_index = lower_text.index(marker)
            return text[:split_index]
            
    return text


def extract_skills(text: str, domain: str = "software"):
    """
    Extracts technical and soft skills from text using a highly optimized PhraseMatcher.
    Features:
    - O(1) Cached Pipelines
    - Exact Token Matching (No substring bugs)
    - Canonical Alias Processing
    - Overlap Prevention
    - Frequency Analysis
    """
    if not text:
        return {
            "domain": domain,
            "technical_skills": [], 
            "soft_skills": [], 
            "categorized_skills": {},
            "skill_counts": {},
            "total_detected": 0
        }
    
    nlp, matcher = get_domain_nlp(domain)
    
    # Process text using the slim cached NLP
    clean_text = sanitize_resume_text(text)
    doc = nlp(clean_text)
    matches = matcher(doc)
    
    # Convert matcher output to Span objects to utilize filter_spans (solves overlapping)
    spans = [doc[start:end] for match_id, start, end in matches]
    filtered_spans = filter_spans(spans)
    
    # We also need the original labels that PhraseMatcher dropped when we made Spans
    # So we quickly re-correlate by span boundaries
    span_to_label = {}
    for match_id, start, end in matches:
        span_to_label[(start, end)] = nlp.vocab.strings[match_id]
        
    taxonomy_data = load_taxonomy(domain)
    skills_flat = taxonomy_data["skills_flat"]
    aliases_map = taxonomy_data["aliases_map"]
    
    technical_skills = set()
    soft_skills = set()
    categorized_skills = {}
    skill_frequency = []
    
    for span in filtered_spans:
        label = span_to_label.get((span.start, span.end))
        if not label:
            continue
            
        # Match using lowercase to respect PhraseMatcher config
        matched_text = span.text.lower()
        
        # Canonical Alias Flow mapping
        canon_norm = aliases_map.get(matched_text, matched_text)
        skill_info = skills_flat.get(canon_norm, {})
        display_name = skill_info.get("display", span.text) # Clean proper capitalized output
        
        skill_frequency.append(display_name)
        
        if label == "SOFT_SKILL":
            soft_skills.add(display_name)
        else:
            technical_skills.add(display_name)
            
            # Smart Metadata categorization processing
            target_categories = skill_info.get("categories", [label])
            for cat in target_categories:
                if cat not in categorized_skills:
                    categorized_skills[cat] = set()
                categorized_skills[cat].add(display_name)
                
    # Calculate global frequency correctly mapped onto canonical keys
    counts = dict(Counter(skill_frequency))
            
    return {
        "domain": domain,
        "technical_skills": sorted(list(technical_skills)),
        "soft_skills": sorted(list(soft_skills)),
        "categorized_skills": {cat: sorted(list(skills)) for cat, skills in categorized_skills.items()},
        "skill_counts": counts,
        "total_detected": len(counts)
    }
