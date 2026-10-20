# Tender Intelligence Agent

A production-grade AI platform that automatically discovers, ingests, screens, and answers questions about public bus operations procurement tenders (Gross Cost Contracts).

---

## What It Does

1. **Discovers** tenders automatically from public government portals (CESL Convergence)
2. **Ingests** PDFs through a full AI pipeline: parse → extract → chunk → embed → store
3. **Screens** each tender with a deterministic GO / REVIEW / NO-GO engine against company eligibility criteria
4. **Answers** questions via a Grounded RAG chat with exact page-level citations from the source PDFs

---

## Architecture

```
React + Vite (Frontend)
        |
FastAPI (Python Backend)
        |
Pipeline: PyMuPDF → LiteLLM (Gemini) → Semantic Chunking → Jina Embeddings
        |
PostgreSQL + pgvector (Neon DB)
        |
Deterministic Screening Engine + Hybrid RAG (SQL + Vector Search)
```

---

## Quick Start (Local Development)

### Prerequisites

- Python 3.11+
- Node.js 20+
- A [Google AI Studio](https://aistudio.google.com) API key (Gemini)
- A [Jina AI](https://jina.ai) API key (embeddings)
- PostgreSQL 16+ with pgvector extension (or use Neon DB free tier)

### 1. Clone & Configure

```bash
git clone https://github.com/Hardiksv/tender-intelligence-agen.git
cd tender-intelligence-agent

# Copy environment template
cp .env.example .env
```

Open `.env` and fill in your credentials:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/tender_db
LLM_API_KEY=your_gemini_api_key_here
LLM_MODEL=gemini/gemini-flash-latest
EMBEDDING_API_KEY=your_jina_api_key_here
```

### 2. Run with Docker (Recommended)

```bash
docker compose up --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| Swagger Docs | http://localhost:8000/docs |

### 3. Run Without Docker

**Terminal 1 — Backend:**

```bash
cd backend
pip install -r requirements.txt
alembic upgrade head
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 — Frontend:**

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 in your browser.

---

## Live Demo

| Service | URL |
|---|---|
| Frontend | https://tender-intelligence-agen.vercel.app |
| Backend API | https://tender-backend-pi.vercel.app |
| Swagger Docs | https://tender-backend-pi.vercel.app/docs |
| Health Check | https://tender-backend-pi.vercel.app/health |

---

## How to Use

1. Open the dashboard — it starts empty
2. Click **Run Discovery** to scrape live tenders from the CESL portal
3. The system downloads PDFs, runs the full AI pipeline, and shows results on the dashboard
4. Click any tender to see its GO/NO-GO verdict with reasoning
5. Use the **RAG Chat** to ask questions like:
   - "What is the EMD amount?"
   - "What are the fleet eligibility criteria?"
   - "What is the submission deadline?"

---

## Core Pipeline

### 1. Discovery
- Scrapes the CESL Convergence portal for active bus operations tenders
- Downloads PDFs to `data/raw/`
- SHA-256 hash deduplication prevents re-processing the same document

### 2. Ingestion & Extraction
- **PyMuPDF** extracts text with page-level tracking
- **OCR fallback** (OCR.space API) handles scanned image pages
- **LiteLLM + Gemini** extracts structured data: title, authority, city, deadline, EMD, fleet requirements, turnover criteria
- Monetary values normalized to INR (handles lakhs, crores)

### 3. Chunking & Embeddings
- Page-aware semantic chunking (~1000 chars, 200 char overlap)
- **Jina AI** generates 768-dimensional embeddings
- Stored in PostgreSQL with `pgvector` HNSW index (cosine similarity)

### 4. Screening Engine
- 100% deterministic Python logic — no LLM in the decision path
- Precedence: `NO-GO > REVIEW > GO`
  - Any mandatory criterion failure → **NO-GO**
  - All mandatory pass + ambiguous clauses → **REVIEW**
  - All criteria pass → **GO**
- Checks: fleet size, annual turnover, experience years, past contract value, geography

### 5. RAG Chat
- Hybrid routing: SQL for deadline/date questions, pgvector for clause questions
- Anti-hallucination guardrail: refuses to answer when evidence is missing
- Every answer cites the exact document filename and page number

---

## Running Tests

```bash
cd backend
python -m pytest tests/ -o pythonpath=. -v
```

**Test Coverage:**
- `test_pdf_parser.py` — PDF extraction, SHA-256 hashing, language guardrails
- `test_extraction.py` — Currency normalization, schema validation
- `test_screening.py` — Deterministic screening and NO-GO precedence
- `test_chunking.py` — Page-aware chunking, vector dimensions
- `test_embedding_migration.py` — Embedding generation and DB insertion
- `test_pipeline_orchestration.py` — Full ingestion loop, fallback handling, idempotency
- `test_emd_and_deadline_catalog.py` — EMD breakdown, deadline extraction
- `test_rag_pipeline.py` — Query routing, anti-hallucination guardrail, citations
- `test_api.py` — Health check, concurrent ingestion rejection

---

## Deployment

Both frontend and backend are deployed on Vercel with automatic CD from the `main` branch on GitHub.

**Key production config (`backend/vercel.json`):**
- `maxDuration: 60` — allows heavy PDF processing within Vercel's serverless limits

**Database:** Neon DB (PostgreSQL + pgvector, serverless)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, Tailwind CSS |
| Backend | FastAPI, Python 3.11, SQLAlchemy |
| LLM | Google Gemini via LiteLLM |
| Embeddings | Jina AI (768-dim) |
| Database | PostgreSQL 16 + pgvector |
| Migrations | Alembic |
| Testing | pytest, Playwright E2E |
| Deployment | Vercel (frontend + backend), Neon DB |
| CI | GitHub Actions |
