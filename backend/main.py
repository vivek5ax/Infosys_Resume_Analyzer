from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import extract
from routes import chat
from routes import auth
from database import connect_to_mongo, close_mongo_connection
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Resume Analyzer API")

# Configure CORS
frontend_origin_raw = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

def _normalize_origins(raw):
    origins = []
    for origin in raw.split(","):
        o = origin.strip()
        if not o:
            continue
        # if user provided a wildcard, return it immediately
        if o == "*":
            return ["*"]
        # remove trailing slash to avoid exact-match mismatches
        o = o.rstrip("/")
        origins.append(o)

    # ensure common local dev origins are present
    for default_origin in ("http://localhost:5173", "http://127.0.0.1:5173"):
        if default_origin not in origins:
            origins.append(default_origin)

    # deduplicate while preserving order
    seen = set()
    deduped = []
    for o in origins:
        if o not in seen:
            seen.add(o)
            deduped.append(o)
    return deduped

frontend_origins = _normalize_origins(frontend_origin_raw)

# If caller used wildcard allow_origins must be ['*'] and credentials must be False
allow_credentials = True
if frontend_origins == ["*"]:
    allow_credentials = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routes
app.include_router(extract.router)
app.include_router(chat.router)

@app.get("/")
def read_root():
    return {"message": "Resume Analyzer API is running"}

#uvicorn main:app --reload

#.\venv\Scripts\python.exe -c "import uvicorn; uvicorn.run('main:app', host='127.0.0.1', port=8000, reload=True)"

#  .\venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000

#.\venv\Scripts\activate
#uvicorn main:app --reload