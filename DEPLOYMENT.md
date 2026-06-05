# Deployment Guide

This project is split into two deployable parts:

- `backend/` — Python FastAPI backend
- `frontend/` — React/Vite frontend

The recommended deployment setup is:

- Backend on Render
- Frontend on Vercel

---

## 1. Preparation

### 1.1. Confirm repository structure

The repository should look like this:

- `backend/`
  - `main.py`
  - `requirements.txt`
  - `.env.example`
  - `render.yaml`
- `frontend/`
  - `package.json`
  - `.env.example`
  - `vercel.json`

### 1.2. Update `.gitignore`

The repository already includes a `.gitignore` configured for:

- Python cache, virtual environments, and build artifacts
- Node/Vite artifacts
- `.env` and local environment files
- Render/Vercel local files

Ensure any additional local files or secrets are also excluded.

### 1.3. Prepare environment variable examples

- `backend/.env.example` contains backend env var templates
- `frontend/.env.example` contains frontend env var templates

Do not commit actual `.env` files or secret values.

---

## 2. Backend deployment on Render

### 2.1. Render service configuration

Render is configured using `render.yaml` in the repository root.
The backend service is defined as:

- `type: web`
- `runtime: python`
- `rootDir: backend`
- `buildCommand: pip install -r requirements.txt && python -m spacy download en_core_web_sm`
- `startCommand: uvicorn main:app --host 0.0.0.0 --port $PORT`
- `healthCheckPath: /`

### 2.2. Create the Render service

1. Log in to Render.
2. Create a new Web Service.
3. Connect your Git repository.
4. Render should detect `render.yaml` and configure the service.

### 2.3. Set backend environment variables

In Render, configure the following environment variables:

- `MONGODB_URI` — your MongoDB connection string
- `DATABASE_NAME` — e.g. `resume_analyzer`
- `JWT_SECRET_KEY` — strong secret for JWT signing
- `JWT_ALGORITHM` — default `HS256`
- `ACCESS_TOKEN_EXPIRE_MINUTES` — default `120`
- `BCRYPT_ROUNDS` — default `12`
- `FRONTEND_ORIGIN` — your deployed frontend URL, e.g. `https://<project>.vercel.app`
- `GROQ_API_KEY` — if you use Groq AI enrichment
- `GROQ_MATCH_API_KEY` — if you use the enhanced semantic matcher Groq feature
- `GROQ_MODEL`, `GROQ_MATCH_MODEL`, `GROQ_FALLBACK_MODEL`, `AI_ENRICHMENT_ENABLED`, etc. as needed

### 2.4. Deploy

- Trigger the initial deploy.
- Confirm the backend health check passes.
- Verify the backend root endpoint responds at `/`.

---

## 3. Frontend deployment on Vercel

### 3.1. Vercel project configuration

The frontend already includes `frontend/vercel.json`:

- `buildCommand: npm run build`
- `outputDirectory: dist`

### 3.2. Create the Vercel project

1. Log in to Vercel.
2. Create a new project and point it to the repository.
3. Set the root directory to `frontend` if Vercel does not detect it automatically.
4. Confirm the build command and output directory.

### 3.3. Configure frontend environment variables

In Vercel environment variables, set:

- `VITE_API_BASE_URL=https://<your-render-backend-url>`

This ensures the frontend calls the deployed backend.

### 3.4. Deploy

- Deploy the frontend.
- Confirm the Vercel deployment succeeds.
- Verify the frontend loads and connects to the backend.

---

## 4. Common deployment notes

### 4.1. CORS

The backend reads `FRONTEND_ORIGIN` in `backend/main.py` and allows that origin via CORS.
Set this to your frontend URL, for example:

```
FRONTEND_ORIGIN=https://your-frontend.vercel.app
```

### 4.2. Backend API base URL

The frontend uses `VITE_API_BASE_URL` in `frontend/.env.example`:

```env
VITE_API_BASE_URL=https://your-backend-service.onrender.com
```

If the backend URL changes, update Vercel env vars and redeploy.

### 4.3. Environment variables and secrets

Never commit real secrets to Git.
Use `.env.example` files to document required values, and keep actual `.env` files local only.

### 4.4. Local development

#### Backend

From the root:

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

#### Frontend

From the root:

```bash
cd frontend
npm install
npm run dev
```

#### Local API URL

Use `backend/.env` or `frontend/.env` to point the frontend to:

```env
VITE_API_BASE_URL=http://localhost:8000
```

---

## 5. Optional: root deployment documentation

If you want, you can also add a root `README.md` or keep this `DEPLOYMENT.md` as the deployment reference for the project.

---

## 6. Troubleshooting

- If Vercel build fails, check `frontend/package.json` dependencies and `vite.config.js`.
- If Render fails, inspect logs for missing Python packages or environment variable errors.
- If the frontend cannot call the backend, verify `VITE_API_BASE_URL` and `FRONTEND_ORIGIN` are correct.
