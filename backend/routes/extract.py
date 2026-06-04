from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Body, Depends
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any, List
from datetime import datetime
from bson.objectid import ObjectId
import asyncio
import os
from services.validator import validate_file
from services.parser import parse_text
from services.preprocessor import generate_versions, save_data, update_session_metadata
from services.analyzer import extract_skills
from services.taxonomy_analyzer import analyze_semantic_matching
from services.ai_enrichment import enrich_with_groq
from services.evidence_layer_builder import build_evidence_layer_payload
from services.hr_decision_layer import build_hr_decision_layer
from services.candidate_decision_layer import build_candidate_decision_layer
from services.pdf_generator import generate_formal_pdf
from database import get_database
from auth_utils import verify_token
from auth_models import AnalysisHistory

router = APIRouter()
security = HTTPBearer(auto_error=False)  # Make bearer token optional


async def get_current_user_optional(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user from bearer token (optional)"""
    if not credentials:
        return None
    
    try:
        token = credentials.credentials
        payload = verify_token(token)
        
        if not payload:
            return None
        
        return payload.get("sub")  # Returns user_id
    except Exception as e:
        # If token verification fails, return None (optional auth)
        print(f"Optional auth verification failed: {str(e)}")
        return None


def _display_resume_name(filename: str) -> str:
    base = os.path.splitext(filename or "Resume")[0].strip()
    return base or "Resume"

@router.post("/extract")
async def extract_content(
    resume: UploadFile = File(...),
    job_description_file: UploadFile = File(None),
    job_description_text: str = Form(None),
    domain: str = Form("software"),
    user_id: str = Depends(get_current_user_optional)
):
    # Match frontend validation logic
    await validate_file(resume)
    if not job_description_file and not job_description_text:
        raise HTTPException(status_code=400, detail="Please provide either a Job Description file or text.")
    if job_description_file:
        await validate_file(job_description_file)

    # Extract Raw Text
    resume_raw = await parse_text(resume)
    jd_raw = job_description_text
    if job_description_file:
        jd_raw = await parse_text(job_description_file)

    # Preprocessing: Generate Multiple Text Versions
    resume_versions = generate_versions(resume_raw)
    jd_versions = generate_versions(jd_raw)
    
    # 1. spaCy-based extraction (Keyword-like / NER) with Domain Awareness
    # SPA-CY NEEDS VERSION B (Light Clean)
    resume_skills = extract_skills(resume_versions["light_clean_text"], domain=domain)
    jd_skills = extract_skills(jd_versions["light_clean_text"], domain=domain)

    # 2. BERT-based semantic analysis with Domain Awareness
    jd_flat_skills = jd_skills.get("technical_skills", []) + jd_skills.get("soft_skills", [])
    resume_flat_skills = resume_skills.get("technical_skills", []) + resume_skills.get("soft_skills", [])

    bert_results = await analyze_semantic_matching(
        jd_flat_skills, 
        resume_flat_skills,
        resume_versions["raw_text"], 
        domain=domain,
        threshold=0.50,
        jd_text=jd_versions["raw_text"]
    )

    # Save Data (Persistence)
    resume_name = resume.filename
    jd_name = job_description_file.filename if job_description_file else "Manual Input"

    try:
        ai_enrichment = await asyncio.to_thread(
            enrich_with_groq,
            run_id="pending",
            domain=domain,
            jd_text=jd_versions["raw_text"],
            resume_text=resume_versions["raw_text"],
            jd_skills=jd_flat_skills,
            resume_skills=resume_flat_skills,
            bert_results=bert_results,
        )
    except Exception as ai_err:
        ai_enrichment = {
            "status": "failed",
            "version": "1.0.0",
            "run_id": "pending",
            "model": "llama-3.3-70b-versatile",
            "created_at": None,
            "normalization": {"mappings": [], "unmapped_terms": []},
            "missing_skill_triage": [],
            "interview_focus": [],
            "quality": {
                "hallucination_risk": "high",
                "coverage_score": 0.0,
                "warnings": [f"AI enrichment runtime error: {str(ai_err)[:180]}"],
                "used_inputs": {
                    "jd_chars": len(jd_versions["raw_text"] or ""),
                    "resume_chars": len(resume_versions["raw_text"] or ""),
                    "jd_skill_count": len(jd_flat_skills),
                    "resume_skill_count": len(resume_flat_skills),
                    "missing_skill_count": len(bert_results.get("missing_from_resume", []) or []),
                },
            },
        }
    
    # Pass version dictionaries to save_data
    session_id = save_data(resume_versions, jd_versions, resume_name, jd_name, resume_skills, jd_skills, bert_results)

    if ai_enrichment.get("run_id") == "pending":
        ai_enrichment["run_id"] = session_id

    evidence_layer = build_evidence_layer_payload(
        session_id=session_id,
        domain=domain,
        bert_results=bert_results,
        ai_enrichment=ai_enrichment,
        jd_text=jd_versions["raw_text"],
        resume_text=resume_versions["raw_text"],
        persona="hr",
    )
    
    # Build HR Decision Layer - Simplified, decision-ready analytics
    hr_decision = build_hr_decision_layer(
        bert_results=bert_results,
        ai_enrichment=ai_enrichment,
        jd_text=jd_versions["raw_text"],
        resume_text=resume_versions["raw_text"],
        domain=domain,
    )
    
    # Build Candidate Decision Layer - Career development & gap closure roadmap
    candidate_decision = build_candidate_decision_layer(
        bert_results=bert_results,
        ai_enrichment=ai_enrichment,
        jd_text=jd_versions["raw_text"],
        resume_text=resume_versions["raw_text"],
        domain=domain,
    )

    update_session_metadata(
        session_id,
        {
            "ai_enrichment": ai_enrichment,
            "evidence_layer": evidence_layer,
            "hr_decision_layer": hr_decision,
            "candidate_decision_layer": candidate_decision,
        },
    )
    
    # Build the response object
    response = {
        "status": "success",
        "session_id": session_id,
        "resume_text": resume_raw,
        "job_description_text": jd_raw,
        "resume_filename": resume_name,
        "jd_filename": jd_name,
        "resume_skills": resume_skills,
        "jd_skills": jd_skills,
        "bert_results": bert_results,
        "ai_enrichment": ai_enrichment,
        "evidence_layer": evidence_layer,
        "hr_decision_layer": hr_decision,
        "candidate_decision_layer": candidate_decision,
    }
    
    # Database logging disabled by design (auth & database disconnected)
    return response

@router.post("/export-pdf")
async def export_pdf(payload: Dict[str, Any] = Body(...)):
    """
    Receives JSON data from the frontend and generates a PDF using fpdf2 & Matplotlib.
    Returns the PDF as a streaming response with native PDF rendering and embedded charts.
    """
    try:
        pdf_buffer = generate_formal_pdf(payload)
        
        headers = {
            'Content-Disposition': 'attachment; filename="Resume_Analysis_Report.pdf"'
        }
        
        return StreamingResponse(
            pdf_buffer, 
            media_type="application/pdf", 
            headers=headers
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error generating PDF: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")


@router.post("/extract-multi-resume")
async def extract_multi_resume_content(
    resumes: List[UploadFile] = File(...),
    job_description_file: UploadFile = File(...),
    domain: str = Form("software"),
):
    if not resumes:
        raise HTTPException(status_code=400, detail="Please upload at least one resume file.")
    if len(resumes) > 10:
        raise HTTPException(status_code=400, detail="You can upload up to 10 resumes at a time.")

    await validate_file(job_description_file)
    for resume_file in resumes:
        await validate_file(resume_file)

    jd_raw = await parse_text(job_description_file)
    jd_versions = generate_versions(jd_raw)
    jd_skills = extract_skills(jd_versions["light_clean_text"], domain=domain)
    jd_flat_skills = jd_skills.get("technical_skills", []) + jd_skills.get("soft_skills", [])

    rankings = []
    for resume_file in resumes:
        resume_raw = await parse_text(resume_file)
        resume_versions = generate_versions(resume_raw)
        resume_skills = extract_skills(resume_versions["light_clean_text"], domain=domain)
        resume_flat_skills = resume_skills.get("technical_skills", []) + resume_skills.get("soft_skills", [])

        bert_results = await analyze_semantic_matching(
            jd_flat_skills,
            resume_flat_skills,
            resume_versions["raw_text"],
            domain=domain,
            threshold=0.50,
            jd_text=jd_versions["raw_text"],
        )

        summary = bert_results.get("summary", {}) if isinstance(bert_results, dict) else {}
        partition = bert_results.get("skill_partition", {}) if isinstance(bert_results, dict) else {}

        exact = partition.get("exact_match", []) if isinstance(partition.get("exact_match"), list) else []
        strong_semantic = partition.get("strong_semantic", []) if isinstance(partition.get("strong_semantic"), list) else []
        moderate_semantic = partition.get("moderate_semantic", []) if isinstance(partition.get("moderate_semantic"), list) else []
        missing = bert_results.get("missing_from_resume", []) if isinstance(bert_results.get("missing_from_resume"), list) else []

        strong_skills = list(exact)
        for item in strong_semantic + moderate_semantic:
            if isinstance(item, dict):
                skill_name = str(item.get("similar_to") or item.get("skill") or "").strip()
                if skill_name and skill_name.lower() not in {s.lower() for s in strong_skills}:
                    strong_skills.append(skill_name)

        missing_skills = []
        for item in missing:
            if isinstance(item, dict):
                skill_name = str(item.get("skill") or "").strip()
            else:
                skill_name = str(item).strip()
            if skill_name and skill_name.lower() not in {s.lower() for s in missing_skills}:
                missing_skills.append(skill_name)

        rankings.append({
            "resume_filename": resume_file.filename,
            "resume_name": _display_resume_name(resume_file.filename),
            "match_percentage": round(float(summary.get("overall_alignment_score", 0.0) or 0.0), 1),
            "exact_matches": int(summary.get("exact_match_count", 0) or 0),
            "semantic_matches": int(summary.get("semantic_match_count", 0) or 0),
            "missing_count": int(summary.get("missing_skills_count", 0) or 0),
            "strong_skills": strong_skills[:8],
            "missing_skills": missing_skills[:8],
            "resume_detected_skills": int(summary.get("resume_detected_skills", 0) or 0),
        })

    rankings.sort(
        key=lambda row: (
            -float(row.get("match_percentage", 0)),
            -int(row.get("exact_matches", 0)),
            -int(row.get("semantic_matches", 0)),
            int(row.get("missing_count", 0)),
            str(row.get("resume_name", "")).lower(),
        )
    )

    for idx, row in enumerate(rankings, start=1):
        row["rank"] = idx

    return {
        "status": "success",
        "domain": domain,
        "jd_filename": job_description_file.filename,
        "jd_skill_count": len(jd_flat_skills),
        "resume_count": len(rankings),
        "rankings": rankings,
    }



