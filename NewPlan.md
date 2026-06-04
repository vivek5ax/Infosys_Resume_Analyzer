# Resume Analyzer v2 Architecture

## Groq GPT-OSS-120B Based Skill Extraction & Matching System

---

# 1. Objective

The goal of this upgrade is to replace the existing semantic matching system based on:

* Sentence Transformers
* BERT Embeddings
* Cosine Similarity
* SequenceMatcher

with a Groq-powered reasoning architecture using:

* openai/gpt-oss-120b
* Existing Skill Taxonomies
* Canonical Skill Mapping
* Skill Relationship Graphs

while maintaining or improving matching accuracy.

---

# 2. Problems With Current Approach

Current Semantic Matching:

```text
Resume Skills
       ↓
Sentence Embeddings
       ↓
Cosine Similarity
       ↓
Threshold Classification
```

Issues:

### Problem 1: No Real Understanding

Example:

JD:
FastAPI

Resume:
Flask

Sentence Transformers may produce a similarity score.

However, the model cannot explain:

* Why they are related
* Whether they belong to the same technology family
* Whether they satisfy hiring requirements

---

### Problem 2: Infrastructure Overhead

Requires:

* torch
* sentence-transformers
* local model downloads
* high memory usage
* slower deployment

---

### Problem 3: Static Similarity Scores

Example:

```text
FastAPI ↔ Flask = 0.76
```

But why?

No explanation is available.

---

# 3. New System Architecture

```text
Resume + JD Upload
          │
          ▼
Document Parsing
          │
          ▼
Text Preprocessing
          │
          ▼
GPT-OSS Skill Extraction
          │
          ▼
Taxonomy Canonicalization
          │
          ▼
Exact Matching
          │
          ▼
Taxonomy Semantic Matching
          │
          ▼
GPT Verification Layer
          │
          ▼
Skill Classification
          │
          ▼
ATS Scoring
          │
          ▼
HR Analysis & Reporting
```

---

# 4. Stage 1 – Document Parsing

No major changes.

Continue using:

* pdfplumber
* python-docx
* OCR fallback

Output:

```python
resume_text
jd_text
```

---

# 5. Stage 2 – GPT Skill Extraction

Current System:

```text
PhraseMatcher
```

New System:

```text
GPT-OSS-120B
```

---

## Resume Skill Extraction Prompt

Prompt:

```text
Extract all technical skills from this resume.

Rules:

1. Extract only actual skills.
2. Ignore responsibilities.
3. Ignore generic words.
4. Ignore soft skills.
5. Return JSON only.

Categories:

Programming Languages
Frontend
Backend
Databases
Cloud
DevOps
AI/ML
Data Engineering
Testing
Automation
Tools
Security
Mobile Development
Data Visualization
```

Output:

```json
{
  "skills": [
    {
      "name": "Python",
      "category": "Programming Languages"
    },
    {
      "name": "FastAPI",
      "category": "Backend"
    },
    {
      "name": "PostgreSQL",
      "category": "Databases"
    }
  ]
}
```

---

# 6. Stage 3 – Taxonomy Canonicalization

Purpose:

Convert aliases into canonical skill names.

Example:

Resume:

```text
Python3
Fast API
MS SQL
```

Canonical Output:

```text
Python
FastAPI
Microsoft SQL Server
```

---

## Taxonomy Structure Upgrade

Current:

```json
{
  "Backend Development": [
    "FastAPI",
    "Flask",
    "Django"
  ]
}
```

Recommended:

```json
{
  "FastAPI": {
    "aliases": [
      "Fast API"
    ],
    "category": "Backend Framework",
    "parent": "Python Backend",
    "related": [
      "Flask",
      "Django",
      "REST API"
    ]
  }
}
```

---

# 7. Stage 4 – Exact Matching

First matching layer.

Rule:

```python
if jd_skill == resume_skill:
    exact_match
```

Example:

JD:

```text
Python
```

Resume:

```text
Python
```

Result:

```text
Exact Match
```

No LLM required.

---

# 8. Stage 5 – Taxonomy Semantic Matching

This replaces most BERT functionality.

---

## Relationship Graph

Example:

```json
{
  "FastAPI": {
    "related": [
      "Flask",
      "Django",
      "REST API"
    ]
  }
}
```

If:

```text
JD = FastAPI
Resume = Flask
```

Result:

```text
Strong Semantic Match
```

without calling GPT.

---

Another example:

```text
JD = React
Resume = Angular
```

Same category:

```text
Frontend Framework
```

Result:

```text
Strong Semantic Match
```

---

# 9. Stage 6 – GPT Verification Layer

Used only for uncertain matches.

Purpose:

Replace cosine similarity reasoning.

---

Example:

JD:

```text
LangChain
```

Resume:

```text
Prompt Engineering
```

Taxonomy cannot confidently classify.

Send to GPT:

```text
Classify relationship.

JD Skill:
LangChain

Resume Skill:
Prompt Engineering

Categories:

EXACT_MATCH
STRONG_SEMANTIC
WEAK_SEMANTIC
NO_MATCH

Return JSON only.
```

Response:

```json
{
  "classification": "WEAK_SEMANTIC",
  "confidence": 0.74,
  "reason": "Prompt engineering is commonly used while developing LangChain applications but does not directly represent LangChain experience."
}
```

---

# 10. New Matching Categories

Current:

```text
Exact
Strong
Moderate
Missing
```

Recommended:

```text
Exact Match
Strong Semantic Match
Weak Semantic Match
Missing Skill
Extra Resume Skill
```

---

# 11. JD Skill Importance Detection

New Feature.

During JD extraction:

GPT should classify every skill.

---

Categories:

```text
Required
Preferred
Optional
```

Example:

```json
{
  "skill": "Docker",
  "importance": "Required"
}
```

---

# 12. ATS Scoring System

Current:

```text
Matched Skills / Total Skills
```

Not realistic.

---

Recommended:

Weighted scoring.

Skill Importance:

```text
Required = 5 points
Preferred = 3 points
Optional = 1 point
```

Match Types:

```text
Exact Match = 100%
Strong Semantic = 80%
Weak Semantic = 50%
Missing = 0%
```

---

Example:

```text
Docker (Required)
```

Points:

```text
5 × 100%
```

---

Example:

```text
FastAPI ↔ Flask
```

Points:

```text
5 × 80%
```

---

Final ATS Score:

```text
Earned Points / Total Points
```

---

# 13. Skill Evidence Layer

Every match should include proof.

Example:

```json
{
  "jd_skill": "FastAPI",
  "resume_skill": "Flask",
  "classification": "Strong Semantic",
  "reason": "Both are Python backend frameworks.",
  "jd_evidence": "Experience with FastAPI APIs",
  "resume_evidence": "Developed REST APIs using Flask"
}
```

This improves transparency.

---

# 14. Recommended API Flow

```text
/extract
    │
    ├── Parse Resume
    ├── Parse JD
    ├── GPT Skill Extraction
    ├── Canonical Mapping
    ├── Exact Matching
    ├── Taxonomy Matching
    ├── GPT Verification
    ├── ATS Score
    ├── AI Analysis
    └── JSON Response
```

---

# 15. Recommended Groq Usage Strategy

DO NOT send:

```text
Every JD Skill
vs
Every Resume Skill
```

to GPT.

That becomes expensive.

---

Instead:

Step 1

```text
Exact Matching
```

Step 2

```text
Taxonomy Matching
```

Step 3

Only unresolved skills:

```text
GPT Verification
```

---

Expected reduction:

```text
80–95% fewer LLM calls
```

while maintaining high semantic accuracy.

---

# 16. Expected Accuracy

Current BERT System:

```text
85–90%
```

Expected Hybrid System:

```text
90–95%
```

because:

* Exact matches remain deterministic.
* Taxonomy captures domain knowledge.
* GPT performs reasoning on ambiguous relationships.
* ATS scoring becomes context aware.
* Missing skills become more accurately identified.

---

# Final Recommendation

Keep:

* Existing Taxonomy Files
* PhraseMatcher
* PDF Parsing
* OCR
* Visualization Layer
* PDF Reports

Replace:

* Sentence Transformers
* BERT Embeddings
* Cosine Similarity
* SequenceMatcher Context Scoring

Add:

* GPT-OSS-120B Skill Extraction
* Canonical Skill Mapping
* Skill Relationship Graph
* GPT Verification Layer
* Weighted ATS Scoring
* Skill Importance Detection

This architecture provides a scalable, explainable, and production-ready resume analysis system powered by Groq while preserving and improving the semantic matching quality previously achieved using sentence transformers.
