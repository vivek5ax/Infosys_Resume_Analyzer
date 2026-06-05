# Resume Analyzer Execution Flow

This document details the exact sequence of how resumes and job descriptions (JDs) are processed, analyzed, enriched by AI, and finally displayed in the frontend interface.

---

## 1. Document Ingestion & Parsing Layer
*File: `backend/routes/extract.py` -> `backend/services/parser.py`*

**Inputs:**
- Resume file (PDF, DOCX)
- Job Description (File or Text)
- Domain selection (e.g., `software`, `marketing`)

**Process:**
1. Text is extracted using PyMuPDF / docx2txt.
2. The `preprocessor.py` creates 3 versions of the text:
   - **Raw Text:** Original unmodified text.
   - **Light Clean Text:** Newlines stripped, basic spacing normalized (Used for fast entity extraction).
   - **Full Clean Text:** Lowercased, special characters removed.

---

## 2. Taxonomy Skill Extraction Layer (Deterministic)
*File: `backend/services/analyzer.py`*

**Inputs:**
- Light Clean Text of Resume and JD
- Domain selection

**Process:**
1. Loads the domain taxonomy JSON (e.g., `software.json`).
2. Configures a highly optimized `spaCy PhraseMatcher` with exact tokens.
3. Scans the text for technical and soft skills.
4. Uses **Canonical Alias Mapping** (e.g., "React.js" and "ReactJS" both map to the standard "React").

**Outputs:**
- `resume_skills`: Technical and soft skills found in the resume.
- `jd_skills`: Technical and soft skills found in the JD.

---

## 3. Taxonomy Matching Layer (Algorithmic / Zero-ML)
*File: `backend/services/taxonomy_analyzer.py`*

**Inputs:**
- Flat lists of `jd_skills` and `resume_skills`
- Raw Resume Text (for fallback checking)

**Process:**
1. **Exact Matching:** Checks if a JD skill's canonical name perfectly matches a Resume skill.
2. **Semantic Matching:** If an exact match fails, it checks if a JD skill and Resume skill share the same *taxonomy categories* (e.g., both are "Frontend Frameworks"). Calculates a Jaccard similarity score.
3. **Fallback Scan:** Runs a raw regex scan over the resume text for any missing JD skills just in case the NLP matcher missed them due to formatting.

**Outputs (`bert_results` / Taxonomy Results):**
- `exact_match`: Array of skills.
- `semantic_match`: Array of mapped skills (e.g. `Vue` -> `React`).
- `missing_from_resume`: JD skills not found.
- `extra_resume_skills`: Resume skills not requested in JD.
- `overall_alignment_score`: Percentage fit.

---

## 4. Context Analysis Layer (Deep NLU)
*File: `backend/services/context_analyzer.py`*

**Inputs:**
- Full JD Text and Resume Text
- Taxonomy Results (Exact, Semantic, Missing)

**Groq API Call 1 (`master_skill_analysis`):**
- **System Prompt:** Instructs the LLM to act as a senior technical recruiter validating the algorithmic results against the actual context in the text.
- **Output (JSON):**
  - `implicit_matches`: Skills candidate has through experience but didn't explicitly name (Green).
  - `contextually_validated`: Exact matches that are proven by real projects, not just keywords (Green).
  - `actual_gaps`: Confirmed missing skills after reading between the lines (Red).
  - `additional_skills`: Strong skills the candidate has that the JD didn't ask for, but are highly valuable (Purple).

---

## 5. AI Enrichment & Decision Layer
*File: `backend/services/ai_enrichment.py` & Decision Builders*

**Inputs:**
- Taxonomy Results
- Context Analysis Results (Implicit, Validated, Gaps)
- Full Text Snippets

**Groq API Call 2 (`enrich_with_groq`):**
- **System Prompt:** Synthesizes all data into actionable HR and Candidate insights. Treats Contextual findings as high-confidence truths.
- **Output (JSON):**
  - **HR Data:** `missing_skill_triage` (critical vs trainable), `interview_focus`.
  - **Candidate Data:** `candidate_narrative`, `candidate_action_plan`, `role_fit_assessment`.

The deterministic services (`hr_decision_layer.py` and `candidate_decision_layer.py`) wrap this AI data into clean, structured schemas with risk percentages and confidence scores.

---

## 6. Chatbot Context Injection Layer
*File: `backend/services/chat_context.py` & `chatbot_groq.py`*

**Inputs:**
- The Chatbot is an independent Groq agent.
- When the user asks a question, the backend packages:
  1. Resume Text & JD Text
  2. Taxonomy `key_findings`
  3. `context_analysis_findings`

**Process:**
The chatbot system prompt explicitly prevents hallucination by forcing the LLM to only use the provided taxonomy arrays and context analysis arrays to answer user questions, citing its evidence.

---

## 7. Frontend UI Display Mapping
*File: `frontend/src/App.jsx`*

How these outputs map to the UI tabs:

1. **Document Overview:**
   - Displays raw parsed text. Highlights extracted taxonomy terms.
2. **Skill Matching:**
   - Displays strictly the **Taxonomy Matching** results (Exact, Semantic, Missing).
3. **Context Analysis Evidence:**
   - Displays strictly the **Context Analysis Layer** results.
   - Organized into color-coded cards (Match = Green, Partial = Yellow, Missing = Red, Additional = Purple).
4. **Evidence Layer (View Mode):**
   - Consumes the **AI Enrichment Layer** schemas.
   - **HR View:** Renders Risk Assessment, Hiring Readiness, and Triage Priority.
   - **Candidate View:** Renders Action Plan, Readiness Score, and Gap Closure Roadmap.
5. **AI Playground Chatbot:**
   - Connects to the **Chatbot Context Injection Layer** for conversational Q&A based on the analyzed session.
