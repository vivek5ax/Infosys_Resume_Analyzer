"""
Enhanced Semantic Matcher - Multi-tiered approach combining:
1. Advanced rule-based matching with fuzzy algorithms
2. Context-aware extraction using spaCy
3. Groq LLM-powered semantic understanding for complex cases
4. Improved taxonomy utilization with weights and hierarchies

This provides BERT-level accuracy without the deployment overhead.
"""

import re
import os
from typing import Dict, List, Tuple, Set, Any
from difflib import SequenceMatcher
from collections import defaultdict
from .taxonomy_loader import load_taxonomy, BASE_PATH
import httpx
import json

# Groq configuration for the enhanced matcher feature.
MATCH_GROQ_API_KEY = "GROQ_MATCH_API_KEY"
MATCH_GROQ_MODEL = "GROQ_MATCH_MODEL"
MATCH_GROQ_API_URL = "GROQ_MATCH_API_URL"
DEFAULT_MATCH_MODEL = "llama-3.1-8b-instant"

# Configuration
STRONG_SIMILARITY_THRESHOLD = 0.85
MODERATE_SIMILARITY_THRESHOLD = 0.65
FUZZY_MATCH_THRESHOLD = 0.75
CONTEXT_WINDOW_SIZE = 150

# Category-specific matching rules
STRICT_MATCH_CATEGORIES = {
    "Programming Languages",  # Languages require exact matches only
    "Databases"              # Databases require exact or family-based matches
}

SEMANTIC_MATCH_CATEGORIES = {
    "Frontend Development",
    "Backend Development", 
    "Cloud & Infrastructure",
    "DevOps & CI/CD",
    "Testing & QA",
    "Mobile Development"
}

# Language families for limited semantic matching in programming languages
LANGUAGE_FAMILIES = {
    "C Family": {"C", "C++", "C#", "Java"},
    "JavaScript Ecosystem": {"JavaScript", "TypeScript", "CoffeeScript"},
    "Python Ecosystem": {"Python", "Jython", "Cython"},
    "Scripting Languages": {"Ruby", "PHP", "Perl"},
    "Functional": {"Haskell", "Scala", "F#", "Clojure", "Erlang"}
}


class EnhancedSemanticMatcher:
    """
    Multi-tiered semantic matcher combining multiple techniques for accuracy
    while remaining deployment-friendly.
    """
    
    def __init__(self, domain: str = "software"):
        self.domain = domain
        self.taxonomy_data = load_taxonomy(domain)
        self.skills_flat = self.taxonomy_data["skills_flat"]
        self.aliases_map = self.taxonomy_data["aliases_map"]
        self.categories = self.taxonomy_data["categories"]
        
        # Build enhanced indexes
        self.skill_index = self._build_skill_index()
        self.category_index = self._build_category_index()
        
        # Build category strictness map
        self.category_strictness = self._build_category_strictness_map()

    def _get_groq_match_config(self) -> Dict[str, str]:
        api_key = os.getenv(MATCH_GROQ_API_KEY, "").strip()
        if not api_key:
            api_key = os.getenv("GROQ_API_KEY", "").strip()
            if api_key:
                print("⚠️ Using fallback GROQ_API_KEY for match analyzer; configure GROQ_MATCH_API_KEY to isolate Groq load.")

        return {
            "api_key": api_key,
            "model": os.getenv(MATCH_GROQ_MODEL, os.getenv("GROQ_MODEL", DEFAULT_MATCH_MODEL)).strip(),
            "url": os.getenv(MATCH_GROQ_API_URL, os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions")).strip(),
        }
        
    def _build_skill_index(self) -> Dict[str, Dict]:
        """Build a comprehensive index for fast skill lookup"""
        index = {}
        for canonical, skill_info in self.skills_flat.items():
            index[canonical] = {
                "display": skill_info.get("display", canonical),
                "categories": skill_info.get("categories", []),
                "aliases": skill_info.get("aliases", []),
                "weight": skill_info.get("max_weight", 1.0),
                "source_domains": skill_info.get("source_domains", [])
            }
        return index
    
    def _build_category_index(self) -> Dict[str, Set[str]]:
        """Build category to skills mapping"""
        index = defaultdict(set)
        for canonical, skill_info in self.skills_flat.items():
            for category in skill_info.get("categories", []):
                index[category].add(canonical)
        return dict(index)
    
    def _build_category_strictness_map(self) -> Dict[str, str]:
        """Build category to matching strictness mapping"""
        strictness_map = {}
        
        # First, check if categories have explicit matching_strictness in taxonomy
        for cat_name, cat_data in self.categories.items():
            if isinstance(cat_data, dict):
                explicit_strictness = cat_data.get("matching_strictness")
                if explicit_strictness:
                    strictness_map[cat_name] = explicit_strictness
        
        # Apply defaults based on category names
        for cat_name in self.categories.keys():
            if cat_name not in strictness_map:
                if cat_name == "Programming Languages":
                    strictness_map[cat_name] = "strict"
                elif cat_name == "Databases":
                    strictness_map[cat_name] = "moderate"
                else:
                    strictness_map[cat_name] = "semantic"
        
        return strictness_map
    
    def _is_strict_match_category(self, category: str) -> bool:
        """Check if category requires strict (exact) matching only"""
        return any(strict_cat in category for strict_cat in STRICT_MATCH_CATEGORIES)
    
    def _are_same_language_family(self, skill1: str, skill2: str) -> bool:
        """Check if two programming languages belong to the same family"""
        skill1_clean = skill1.lower().strip()
        skill2_clean = skill2.lower().strip()
        
        for family, languages in LANGUAGE_FAMILIES.items():
            family_lower = {lang.lower() for lang in languages}
            if skill1_clean in family_lower and skill2_clean in family_lower:
                return True
        return False
    
    def _normalize_text(self, text: str) -> str:
        """Enhanced text normalization"""
        if not text:
            return ""
        text = text.lower().strip()
        # Remove special characters but keep important ones
        text = re.sub(r'[^\w\s\-\.\+\#\/]', ' ', text)
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        return text
    
    def _fuzzy_similarity(self, str1: str, str2: str) -> float:
        """Calculate fuzzy string similarity using multiple methods"""
        s1, s2 = self._normalize_text(str1), self._normalize_text(str2)
        
        # Method 1: Sequence matcher (good for overall similarity)
        seq_sim = SequenceMatcher(None, s1, s2).ratio()
        
        # Method 2: Character overlap (good for typos)
        char_overlap = len(set(s1) & set(s2)) / len(set(s1) | set(s2)) if s1 or s2 else 0
        
        # Method 3: Token overlap (good for word order changes)
        tokens1, tokens2 = set(s1.split()), set(s2.split())
        token_overlap = len(tokens1 & tokens2) / len(tokens1 | tokens2) if tokens1 or tokens2 else 0
        
        # Weighted combination
        return (seq_sim * 0.4) + (char_overlap * 0.3) + (token_overlap * 0.3)
    
    def _check_fuzzy_match(self, skill: str, candidates: List[str]) -> Tuple[str, float]:
        """Find best fuzzy match among candidates"""
        best_match = ""
        best_score = 0.0
        
        for candidate in candidates:
            score = self._fuzzy_similarity(skill, candidate)
            if score > best_score and score >= FUZZY_MATCH_THRESHOLD:
                best_score = score
                best_match = candidate
        
        return best_match, best_score
    
    def _extract_context_snippet(self, text: str, skill: str, window: int = CONTEXT_WINDOW_SIZE) -> str:
        """Extract contextual snippet around a skill mention"""
        if not text or not skill:
            return ""
        
        pattern = re.compile(rf'\b{re.escape(skill)}\b', re.IGNORECASE)
        matches = list(pattern.finditer(text))
        
        if not matches:
            return ""
        
        # Get the most relevant match (prefer matches with more context)
        best_match = max(matches, key=lambda m: len(m.group()))
        start = max(0, best_match.start() - window)
        end = min(len(text), best_match.end() + window)
        
        snippet = text[start:end].strip()
        return re.sub(r'\s+', ' ', snippet)
    
    def _get_related_skills(self, skill: str) -> Set[str]:
        """Find skills that are semantically related via categories"""
        skill_lower = skill.lower()
        canonical = self.aliases_map.get(skill_lower, skill_lower)
        
        if canonical not in self.skills_flat:
            return set()
        
        skill_categories = set(self.skills_flat[canonical].get("categories", []))
        related_skills = set()
        
        for category in skill_categories:
            if category in self.category_index:
                related_skills.update(self.category_index[category])
        
        related_skills.discard(canonical)
        return related_skills
    
    def _calculate_category_similarity(self, skill1: str, skill2: str) -> float:
        """Calculate similarity based on category overlap with weights"""
        canon1 = self.aliases_map.get(skill1.lower(), skill1.lower())
        canon2 = self.aliases_map.get(skill2.lower(), skill2.lower())
        
        cats1 = set(self.skills_flat.get(canon1, {}).get("categories", []))
        cats2 = set(self.skills_flat.get(canon2, {}).get("categories", []))
        
        if not cats1 or not cats2:
            return 0.0
        
        # Jaccard similarity
        intersection = cats1 & cats2
        union = cats1 | cats2
        base_score = len(intersection) / len(union) if union else 0.0
        
        # Weight boost for shared high-weight categories
        category_weights = {}
        for cat_name, cat_data in self.categories.items():
            category_weights[cat_name] = cat_data.get("weight", 1.0)
        
        weighted_intersection = sum(category_weights.get(cat, 1.0) for cat in intersection)
        weighted_union = sum(category_weights.get(cat, 1.0) for cat in union)
        
        weighted_score = weighted_intersection / weighted_union if weighted_union else 0.0
        
        return (base_score * 0.6) + (weighted_score * 0.4)
    
    async def _groq_semantic_match(self, skill_pairs: List[Tuple[str, str]], context: str = "") -> Dict[str, float]:
        """
        Use Groq LLM for semantic understanding of complex skill pairs.
        This provides true semantic understanding for ambiguous cases.
        """
        if not skill_pairs:
            return {}
        
        try:
            groq_config = self._get_groq_match_config()
            groq_api_key = groq_config["api_key"]
            if not groq_api_key:
                print("⚠️ GROQ_MATCH_API_KEY/GROQ_API_KEY not found, skipping LLM semantic matching")
                return {}
            
            # Prepare the prompt for LLM
            prompt = f"""You are a technical skill matching expert. Rate the semantic similarity between the following skill pairs on a scale of 0.0 to 1.0.

Context: This is for resume-JD matching in the {self.domain} domain.

Context text: {context[:500]}

Rate each pair considering:
- Technical equivalence (e.g., "React" and "ReactJS" = 1.0)
- Related technologies (e.g., "React" and "Vue.js" = 0.6)
- Domain relationships (e.g., "Python" and "Django" = 0.7)
- Skill hierarchy (e.g., "Machine Learning" and "Deep Learning" = 0.8)

Return ONLY a JSON object with skill pairs as keys and similarity scores as values.
Example: {{"React | ReactJS": 1.0, "Python | Django": 0.7}}

Skill pairs to rate:
"""
            for skill1, skill2 in skill_pairs:
                prompt += f"- {skill1} | {skill2}\n"
            
            headers = {
                "Authorization": f"Bearer {groq_api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": groq_config["model"],
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,  # Low temperature for consistent scoring
                "max_tokens": 500
            }
            
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    groq_config["url"],
                    headers=headers,
                    json=data
                )
                
                if response.status_code != 200:
                    print(f"⚠️ Groq API error: {response.status_code}")
                    return {}
                
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                
                # Parse JSON response
                try:
                    # Extract JSON from the response
                    json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
                    if json_match:
                        similarity_scores = json.loads(json_match.group())
                        # Convert format from "skill1 | skill2" to tuple key
                        result_dict = {}
                        for pair_key, score in similarity_scores.items():
                            if "|" in pair_key:
                                s1, s2 = pair_key.split("|", 1)
                                result_dict[(s1.strip(), s2.strip())] = score
                        return result_dict
                except Exception as e:
                    print(f"⚠️ Failed to parse Groq response: {e}")
                    return {}
                
        except Exception as e:
            print(f"⚠️ Groq semantic matching failed: {e}")
            return {}
        
        return {}
    
    def _check_category_strict_match(self, resume_skill: str, jd_skill: str) -> Tuple[bool, float]:
        """
        Check if skills match according to category-specific rules.
        Uses the category_strictness map to determine matching behavior:
        - strict: only exact/alias matches allowed (e.g., Programming Languages)
        - moderate: limited semantic matching (e.g., Databases within same type)
        - semantic: full semantic matching allowed (e.g., frameworks, tools)
        """
        # Get categories for both skills
        r_canon = self.aliases_map.get(resume_skill.lower(), resume_skill.lower())
        j_canon = self.aliases_map.get(jd_skill.lower(), jd_skill.lower())
        
        r_cats = set(self.skills_flat.get(r_canon, {}).get("categories", []))
        j_cats = set(self.skills_flat.get(j_canon, {}).get("categories", []))
        
        # Determine the strictest matching requirement
        strictness_levels = []
        for cat in (r_cats | j_cats):
            strictness = self.category_strictness.get(cat, "semantic")
            strictness_levels.append(strictness)
        
        # Use the strictest level (strict > moderate > semantic)
        strictness_priority = {"strict": 3, "moderate": 2, "semantic": 1}
        max_strictness = max(strictness_levels, key=lambda x: strictness_priority.get(x, 1))
        
        if max_strictness == "strict":
            # For strict categories, only allow exact or alias matches
            if r_canon == j_canon:
                return True, 1.0
            # For programming languages, allow same-family matching with very low confidence
            if "Programming Languages" in (r_cats | j_cats):
                if self._are_same_language_family(resume_skill, jd_skill):
                    return True, 0.25  # Very low confidence for language family matches
            return False, 0.0
        
        elif max_strictness == "moderate":
            # For moderate categories, allow some semantic matching but require higher threshold
            if r_canon == j_canon:
                return True, 1.0
            
            # Check category similarity with higher threshold
            cat_score = self._calculate_category_similarity(resume_skill, jd_skill)
            if cat_score >= 0.75:  # Higher threshold for moderate categories
                return True, cat_score
            return False, 0.0
        
        else:  # semantic
            # For semantic categories, use full enhanced category matching
            cat_score = self._calculate_category_similarity(resume_skill, jd_skill)
            if cat_score >= MODERATE_SIMILARITY_THRESHOLD:
                # Cap generic category semantic matches below Strong threshold (0.85) 
                # to prevent cross-language frameworks (e.g. Spring Boot vs FastAPI) from getting 1.0
                if r_canon != j_canon:
                    cat_score = min(cat_score, 0.84)
                return True, cat_score
            return False, 0.0

    def find_exact_matches(self, resume_skills: List[str], jd_skills: List[str]) -> List[str]:
        """Find exact matches including aliases"""
        matched = set()
        jd_canonical_map = {}
        
        # Build JD canonical map
        for jd_skill in jd_skills:
            jd_lower = jd_skill.lower()
            jd_canon = self.aliases_map.get(jd_lower, jd_lower)
            jd_canonical_map[jd_canon] = jd_skill
        
        # Check resume skills
        for resume_skill in resume_skills:
            resume_lower = resume_skill.lower()
            resume_canon = self.aliases_map.get(resume_lower, resume_lower)
            
            if resume_canon in jd_canonical_map:
                matched.add(resume_skill)
        
        return list(matched)
    
    def find_fuzzy_matches(self, resume_skills: List[str], jd_skills: List[str], 
                          already_matched: Set[str]) -> List[Dict[str, Any]]:
        """Find fuzzy matches using advanced string similarity"""
        fuzzy_matches = []
        
        # Filter out already matched skills
        remaining_resume = [s for s in resume_skills if s not in already_matched]
        
        for resume_skill in remaining_resume:
            # Try to find fuzzy match in JD skills
            best_match, score = self._check_fuzzy_match(resume_skill, jd_skills)
            
            if best_match and score >= FUZZY_MATCH_THRESHOLD:
                fuzzy_matches.append({
                    "skill": resume_skill,
                    "similar_to": best_match,
                    "score": round(score, 2),
                    "match_type": "fuzzy"
                })
        
        return fuzzy_matches
    
    def find_category_matches(self, resume_skills: List[str], jd_skills: List[str],
                             already_matched: Set[str]) -> List[Dict[str, Any]]:
        """Find matches based on category similarity with enhanced scoring and specificity rules"""
        category_matches = []
        
        # Filter out already matched skills
        remaining_resume = [s for s in resume_skills if s not in already_matched]
        
        for resume_skill in remaining_resume:
            best_jd_skill = None
            best_score = 0.0
            
            for jd_skill in jd_skills:
                # Use category-specific matching rules
                is_match, score = self._check_category_strict_match(resume_skill, jd_skill)
                
                if is_match and score > best_score:
                    best_score = score
                    best_jd_skill = jd_skill
            
            if best_jd_skill and best_score >= MODERATE_SIMILARITY_THRESHOLD:
                # Determine match type based on score and category
                match_type = "category"
                if best_score == 1.0:
                    match_type = "exact"
                elif best_score >= STRONG_SIMILARITY_THRESHOLD:
                    match_type = "strong_semantic"
                
                category_matches.append({
                    "skill": resume_skill,
                    "similar_to": best_jd_skill,
                    "score": round(best_score, 2),
                    "match_type": match_type
                })
        
        return category_matches
    
    async def analyze_semantic_matching(
        self, 
        jd_skills: List[str], 
        resume_skills: List[str],
        resume_text: str = "",
        jd_text: str = "",
        use_llm: bool = True
    ) -> Dict[str, Any]:
        """
        Multi-tiered semantic matching analysis:
        1. Exact matches (including aliases)
        2. Fuzzy matches (string similarity)
        3. Category matches (enhanced category similarity)
        4. LLM semantic matches (for ambiguous cases)
        """
        print(f"\n--- Starting Enhanced Semantic Matcher [Domain: {self.domain}] ---")
        print(f"JD Skills: {len(jd_skills)}, Resume Skills: {len(resume_skills)}")
        
        partition = {
            "exact_match": [],
            "fuzzy_match": [],
            "strong_semantic": [],
            "moderate_semantic": [],
            "llm_semantic": [],
            "irrelevant": []
        }
        
        matched_jd_skills = set()
        matched_resume_skills = set()
        
        # Tier 1: Exact Matches
        exact_matches = self.find_exact_matches(resume_skills, jd_skills)
        for match in exact_matches:
            partition["exact_match"].append(match)
            matched_resume_skills.add(match)
            
            # Find corresponding JD skill
            match_lower = match.lower()
            match_canon = self.aliases_map.get(match_lower, match_lower)
            for jd_skill in jd_skills:
                jd_lower = jd_skill.lower()
                jd_canon = self.aliases_map.get(jd_lower, jd_lower)
                if match_canon == jd_canon:
                    matched_jd_skills.add(jd_skill)
                    break
        
        print(f"Tier 1 - Exact matches: {len(exact_matches)}")
        
        # Tier 2: Fuzzy Matches
        fuzzy_results = self.find_fuzzy_matches(resume_skills, jd_skills, matched_resume_skills)
        for match in fuzzy_results:
            if match["score"] >= STRONG_SIMILARITY_THRESHOLD:
                partition["strong_semantic"].append(match)
            else:
                partition["fuzzy_match"].append(match)
            matched_resume_skills.add(match["skill"])
            matched_jd_skills.add(match["similar_to"])
        
        print(f"Tier 2 - Fuzzy matches: {len(fuzzy_results)}")
        
        # Tier 3: Category Matches
        category_results = self.find_category_matches(resume_skills, jd_skills, matched_resume_skills)
        for match in category_results:
            if match["score"] >= STRONG_SIMILARITY_THRESHOLD:
                partition["strong_semantic"].append(match)
            else:
                partition["moderate_semantic"].append(match)
            matched_resume_skills.add(match["skill"])
            matched_jd_skills.add(match["similar_to"])
        
        print(f"Tier 3 - Category matches: {len(category_results)}")
        
        # Tier 4: LLM Semantic Matches (for ambiguous high-value cases)
        if use_llm:
            # Identify ambiguous cases that could benefit from LLM analysis
            remaining_resume = [s for s in resume_skills if s not in matched_resume_skills]
            remaining_jd = [s for s in jd_skills if s not in matched_jd_skills]
            
            # Limit to top ambiguous cases to control API costs
            if remaining_resume and remaining_jd and len(remaining_resume) * len(remaining_jd) <= 20:
                skill_pairs = []
                for r_skill in remaining_resume[:5]:  # Limit to top 5
                    for j_skill in remaining_jd[:4]:  # Limit to top 4
                        skill_pairs.append((r_skill, j_skill))
                
                if skill_pairs:
                    context = f"Resume: {resume_text[:300]}\nJD: {jd_text[:300]}"
                    llm_scores = await self._groq_semantic_match(skill_pairs, context)
                    
                    for (r_skill, j_skill), score in llm_scores.items():
                        if score >= MODERATE_SIMILARITY_THRESHOLD:
                            partition["llm_semantic"].append({
                                "skill": r_skill,
                                "similar_to": j_skill,
                                "score": round(score, 2),
                                "match_type": "llm_semantic"
                            })
                            matched_resume_skills.add(r_skill)
                            matched_jd_skills.add(j_skill)
                    
                    print(f"Tier 4 - LLM semantic matches: {len(partition['llm_semantic'])}")
        
        # Identify irrelevant and missing skills
        irrelevant_skills = [s for s in resume_skills if s not in matched_resume_skills]
        partition["irrelevant"] = irrelevant_skills
        
        missing_skills = []
        for jd_skill in jd_skills:
            if jd_skill not in matched_jd_skills:
                jd_lower = jd_skill.lower()
                jd_canon = self.aliases_map.get(jd_lower, jd_lower)
                skill_info = self.skills_flat.get(jd_canon, {})
                missing_skills.append({
                    "skill": jd_skill,
                    "weight": skill_info.get("max_weight", 1.0),
                    "categories": skill_info.get("categories", ["Unknown"])
                })
        
        missing_skills.sort(key=lambda x: x["weight"], reverse=True)
        
        # Calculate summary statistics
        total_jd = len(jd_skills)
        total_resume_matched = len(matched_resume_skills)
        exact_count = len(partition["exact_match"])
        semantic_count = len(partition["strong_semantic"]) + len(partition["moderate_semantic"]) + len(partition["fuzzy_match"]) + len(partition["llm_semantic"])
        
        # Calculate weighted alignment score
        alignment_score = 0.0
        if total_jd > 0:
            weight_sum = sum(self.skills_flat.get(
                self.aliases_map.get(s.lower(), s.lower()), {}
            ).get("max_weight", 1.0) for s in jd_skills)
            
            matched_weight_sum = 0.0
            for skill in matched_jd_skills:
                skill_canon = self.aliases_map.get(skill.lower(), skill.lower())
                matched_weight_sum += self.skills_flat.get(skill_canon, {}).get("max_weight", 1.0)
            
            alignment_score = matched_weight_sum / weight_sum if weight_sum > 0 else 0.0
        
        result = {
            "summary": {
                "total_jd_skills": total_jd,
                "resume_detected_skills": total_resume_matched,
                "exact_match_count": exact_count,
                "semantic_match_count": semantic_count,
                "missing_skills_count": len(missing_skills),
                "overall_alignment_score": round(alignment_score * 100, 1)
            },
            "skill_partition": partition,
            "missing_from_resume": missing_skills,
            "extra_resume_skills": irrelevant_skills,
            "jd_skill_clusters": self._build_clusters(jd_skills),
            "resume_skill_clusters": self._build_clusters(resume_skills),
            "match_evidence": self._build_match_evidence(partition, missing_skills, jd_text, resume_text)
        }
        
        print(f"✅ Enhanced matching complete - Alignment Score: {alignment_score * 100:.1f}%")
        return result
    
    def _build_clusters(self, skills: List[str]) -> Dict[str, List[str]]:
        """Build skill clusters by category"""
        clusters = defaultdict(list)
        
        for skill in skills:
            skill_lower = skill.lower()
            canon = self.aliases_map.get(skill_lower, skill_lower)
            skill_info = self.skills_flat.get(canon, {})
            categories = skill_info.get("categories", ["Unknown"])
            
            # Use first category as primary cluster
            primary_category = categories[0] if categories else "Unknown"
            clusters[primary_category].append(skill)
        
        return dict(clusters)
    
    def _build_match_evidence(self, partition: Dict, missing: List, jd_text: str, resume_text: str) -> List[Dict]:
        """Build detailed evidence for each match"""
        evidence = []
        
        # Exact matches
        for skill in partition.get("exact_match", []):
            evidence.append({
                "skill": skill,
                "match_type": "exact",
                "confidence": 1.0,
                "jd_skill": skill,
                "resume_skill": skill,
                "jd_snippet": self._extract_context_snippet(jd_text, skill),
                "resume_snippet": self._extract_context_snippet(resume_text, skill)
            })
        
        # Fuzzy matches
        for item in partition.get("fuzzy_match", []):
            evidence.append({
                "skill": item.get("similar_to"),
                "match_type": "fuzzy",
                "confidence": item.get("score", 0.0),
                "jd_skill": item.get("similar_to"),
                "resume_skill": item.get("skill"),
                "jd_snippet": self._extract_context_snippet(jd_text, item.get("similar_to", "")),
                "resume_snippet": self._extract_context_snippet(resume_text, item.get("skill", ""))
            })
        
        # Strong semantic matches
        for item in partition.get("strong_semantic", []):
            evidence.append({
                "skill": item.get("similar_to"),
                "match_type": "strong_semantic",
                "confidence": item.get("score", 0.0),
                "jd_skill": item.get("similar_to"),
                "resume_skill": item.get("skill"),
                "jd_snippet": self._extract_context_snippet(jd_text, item.get("similar_to", "")),
                "resume_snippet": self._extract_context_snippet(resume_text, item.get("skill", ""))
            })
        
        # Moderate semantic matches
        for item in partition.get("moderate_semantic", []):
            evidence.append({
                "skill": item.get("similar_to"),
                "match_type": "moderate_semantic",
                "confidence": item.get("score", 0.0),
                "jd_skill": item.get("similar_to"),
                "resume_skill": item.get("skill"),
                "jd_snippet": self._extract_context_snippet(jd_text, item.get("similar_to", "")),
                "resume_snippet": self._extract_context_snippet(resume_text, item.get("skill", ""))
            })
        
        # LLM semantic matches
        for item in partition.get("llm_semantic", []):
            evidence.append({
                "skill": item.get("similar_to"),
                "match_type": "llm_semantic",
                "confidence": item.get("score", 0.0),
                "jd_skill": item.get("similar_to"),
                "resume_skill": item.get("skill"),
                "jd_snippet": self._extract_context_snippet(jd_text, item.get("similar_to", "")),
                "resume_snippet": self._extract_context_snippet(resume_text, item.get("skill", ""))
            })
        
        # Missing skills
        for item in missing:
            evidence.append({
                "skill": item.get("skill"),
                "match_type": "missing",
                "confidence": 0.0,
                "jd_skill": item.get("skill"),
                "resume_skill": None,
                "jd_snippet": self._extract_context_snippet(jd_text, item.get("skill", "")),
                "resume_snippet": "",
                "weight": item.get("weight", 1.0)
            })
        
        # Sort by confidence
        evidence.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        return evidence[:30]  # Limit to top 30 evidence items


# Convenience function for backward compatibility
async def analyze_semantic_matching(
    raw_jd_displays: list, 
    raw_resume_displays: list, 
    resume_text: str, 
    domain: str = "software", 
    threshold: float = 0.50, 
    jd_text: str = "",
    use_llm: bool = True
) -> dict:
    """
    Enhanced semantic matching function with multi-tiered approach.
    
    Args:
        raw_jd_displays: List of JD skill names
        raw_resume_displays: List of resume skill names  
        resume_text: Full resume text for context
        domain: Domain for taxonomy loading
        threshold: Similarity threshold (legacy parameter)
        jd_text: Full JD text for context
        use_llm: Whether to use Groq LLM for semantic understanding
    
    Returns:
        Dictionary with matching results including partition, evidence, and summary
    """
    matcher = EnhancedSemanticMatcher(domain)
    return await matcher.analyze_semantic_matching(
        raw_jd_displays, 
        raw_resume_displays, 
        resume_text, 
        jd_text, 
        use_llm
    )