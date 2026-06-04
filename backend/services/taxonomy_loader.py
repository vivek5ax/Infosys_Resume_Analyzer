import json
import os
import logging
import re

logger = logging.getLogger(__name__)

BASE_PATH = os.path.join(os.path.dirname(__file__), "..", "taxonomies")


def normalize_skill(skill: str) -> str:
    """
    Normalizes a skill string for comparison (stage 3).
    Lowercases, strips, collapses spaces, preserves tech punctuation (+ # . / -)
    """
    norm = skill.lower()
    norm = re.sub(r'[^a-z0-9\s.\+#/\-]', ' ', norm)
    return ' '.join(norm.split())


def validate_category(cat_name: str, cat_data: dict):
    """
    Stage 2 Validation: Validates a category block's schema.
    """
    if not isinstance(cat_data, dict):
        raise ValueError(f"Category '{cat_name}' must be a dictionary.")
    
    if "weight" not in cat_data or not isinstance(cat_data["weight"], (int, float)) or cat_data["weight"] <= 0:
        raise ValueError(f"Category '{cat_name}' must have a positive numeric 'weight'.")
    
    if "skills" not in cat_data or not isinstance(cat_data["skills"], list) or len(cat_data["skills"]) == 0:
        raise ValueError(f"Category '{cat_name}' must have a non-empty list of 'skills'.")


def load_json_safely(filepath: str, is_required: bool = True):
    """
    Stage 1 Loading: Safe and secure JSON loading parsing.
    """
    if not os.path.exists(filepath):
        if is_required:
            logger.error(f"Required taxonomy file missing: {filepath}")
            raise FileNotFoundError(f"Missing taxonomy file: {filepath}")
        else:
            logger.warning(f"Optional taxonomy file missing: {filepath}")
            return None
            
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Corrupted JSON in {filepath}: {str(e)}")
        raise ValueError(f"Corrupted JSON in taxonomy file {filepath}: {str(e)}")


def load_taxonomy(domain: str) -> dict:
    """
    Loads and compiles the domain and soft skill taxonomies into a high-performance 
    structured dictionary suitable for ATS-style mapping.
    """
    # Security: Sanitize domain input to alphanumeric & underscores
    domain_clean = re.sub(r'[^a-z0-9_]', '', domain.lower().replace(' ', '_'))
    
    domain_file = f"{domain_clean}.json"
    domain_path = os.path.join(BASE_PATH, domain_file)
    soft_path = os.path.join(BASE_PATH, "soft_skills.json")

    # 1. Load Data safely
    domain_data = load_json_safely(domain_path, is_required=True)
    soft_data = load_json_safely(soft_path, is_required=False)

    merged_categories = {}
    skills_flat = {}
    aliases_map = {}
    
    # Safe meta block access
    domain_meta = domain_data.get("_meta", {"domain": domain_clean, "version": "unknown"}) if domain_data else {}
    
    # Internal Pipeline 
    def process_taxonomy(data: dict, source_name: str):
        if not data: 
            return
            
        categories = data.get("categories", data) # Fallback to raw data if missing 'categories' wrapper
        
        for cat_name, cat_data in categories.items():
            if cat_name == "_meta": 
                continue
            
            # Stage 2: Schema Validation
            validate_category(cat_name, cat_data)
            weight = float(cat_data["weight"])
            
            # Stage 5: Safe Merging Without Implicit Overwriting
            if cat_name not in merged_categories:
                merged_categories[cat_name] = {"weight": weight, "skills": []}
            else:
                logger.warning(f"Category collision detected for '{cat_name}'. Safely appending skills.")
                merged_categories[cat_name]["weight"] = max(merged_categories[cat_name]["weight"], weight)
                
            for skill_item in cat_data["skills"]:
                # Stage 5: Handle advanced dictionary vs simple string format
                if isinstance(skill_item, dict):
                    display_name = skill_item.get("name")
                    aliases = skill_item.get("aliases", [])
                    skill_type = skill_item.get("type", "unknown")
                    importance = skill_item.get("importance", "normal")
                else:
                    display_name = str(skill_item)
                    aliases = []
                    skill_type = "unknown"
                    importance = "normal"
                    
                # Stage 3: Normalization 
                norm_name = normalize_skill(display_name)
                
                # Stage 4: Deduplication and Building Global Registry (skills_flat)
                if norm_name not in skills_flat:
                    skills_flat[norm_name] = {
                        "display": display_name,
                        "categories": set(),
                        "max_weight": weight,
                        "source_domains": set(),
                        "type": skill_type,
                        "importance": importance
                    }
                
                # Expand specific attributes per Category references safely
                skills_flat[norm_name]["categories"].add(cat_name)
                skills_flat[norm_name]["source_domains"].add(source_name)
                skills_flat[norm_name]["max_weight"] = max(skills_flat[norm_name]["max_weight"], weight)
                
                # Map incoming aliases to the normalized canonical name directly
                for alias in aliases:
                    norm_alias = normalize_skill(alias)
                    if norm_alias in aliases_map and aliases_map[norm_alias] != norm_name:
                        continue
                    aliases_map[norm_alias] = norm_name
                    
                # Append to merged category for simple UI representation if not already explicitly present
                existing_skill_names = [s.get("name") if isinstance(s, dict) else s for s in merged_categories[cat_name]["skills"]]
                if display_name not in existing_skill_names:
                     merged_categories[cat_name]["skills"].append(skill_item)

    # Process all sources
    process_taxonomy(domain_data, domain_meta.get("domain", domain_clean))
    process_taxonomy(soft_data, "soft_skills")
    
    # Prepare serializable sets to json-compliant lists
    for skill_info in skills_flat.values():
        skill_info["categories"] = sorted(list(skill_info["categories"]))
        skill_info["source_domains"] = sorted(list(skill_info["source_domains"]))

    return {
        "meta": {
            "domain": domain_meta.get("domain", domain_clean),
            "version": domain_meta.get("version", "1.0"),
            "total_categories": len(merged_categories),
            "total_unique_skills": len(skills_flat)
        },
        "categories": merged_categories,
        "skills_flat": skills_flat,
        "aliases_map": aliases_map
    }
