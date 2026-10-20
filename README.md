# Tender Intelligence Agent

A production-grade AI platform that automatically discovers, ingests, screens, and answers questions about public bus operations procurement tenders (Gross Cost Contracts).

---

## What It Does

1. **Discovers** tenders automatically from public government portals ([CESL Convergence](https://www.convergence.co.in/tender))
2. **Ingests** PDFs through a full AI pipeline: parse -> extract -> chunk -> embed -> store
3. **Screens** each tender with a deterministic GO / REVIEW / NO-GO engine against company eligibility criteria
4. **Answers** questions via a Grounded RAG chat with exact page-level citations from the source PDFs

---

## Architecture

```
React + Vite (Frontend)
        |
FastAPI (Python Backend)
        |
Pipeline: PyMuPDF -> LiteLLM (Gemini) -> Semantic Chunking -> Jina Embeddings
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
EMBEDDING_MODEL=jina-embeddings-v5-omni-small
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

1. Open the dashboard — it starts clean and connects to the live database
2. Click **Run Discovery** to scrape active tenders from public government portals
3. The system downloads PDFs, runs structured AI extraction and deterministic screening
4. Click any tender to view its GO/NO-GO verdict with rule-based criteria evaluations
5. Use the **RAG Chat** to ask clause-level questions with exact source citations

---

## Core Pipeline

### 1. Discovery
- Scrapes the CESL Convergence portal for active tenders
- SHA-256 hash deduplication prevents duplicate ingestion
- Direct database updates when submission deadlines change on the portal

### 2. Ingestion & Extraction
- **PyMuPDF** extracts text with page provenance
- **OCR fallback** (OCR.space API) handles image-only pages
- **LiteLLM + Gemini** extracts structured schema (fleet size, turnover, EMD, deadlines)
- Automatic monetary normalization to INR

### 3. Chunking & Embeddings
- Page-aware semantic chunking
- **Jina AI** generates 768-dimensional dense vectors
- Stored in PostgreSQL with `pgvector` HNSW index (cosine similarity)

### 4. Screening Engine
- 100% deterministic Python evaluation — no LLM hallucinations in eligibility decisions
- Strict precedence: `NO-GO > REVIEW > GO`
- Checks fleet size, annual turnover, experience, contract value, and state geography

### 5. Grounded RAG Chat
- Hybrid routing: SQL for temporal/date queries, pgvector for clause retrieval
- Anti-hallucination guardrail: refuses to answer when evidence is absent
- Verifiable citations with source document name and page number

---

## Running Tests

Install development dependencies:
```bash
cd backend
pip install -r requirements-dev.txt
```

Run test suite:
```bash
python -m pytest tests/ -o pythonpath=. -v
```

**Automated Test Suite (51/51 Tests Passing):**
- `test_api.py` — Health checks, dynamic cost tracking, concurrent ingestion lock
- `test_chunking.py` — Page awareness, vector dimensionality checks
- `test_discovery_date_parsing.py` — IST timezone (+05:30) validation, direct deadline updates
- `test_discovery_parser.py` — CESL HTML table parsing against real fixture
- `test_embedding_migration.py` — Embedding dimension verification and pgvector DB insertion
- `test_extraction.py` — Currency normalization, metric standardization, schema validation
- `test_llm_truncation.py` — Truncation recovery and reasoning tag validation
- `test_migrated_logic.py` — PDF parser validation, zero-hallucination vector checks, screening
- `test_pdf_parser.py` — Multi-page extraction, SHA-256 idempotency, OCR fallback
- `test_pipeline_orchestration.py` — Full pipeline loop, heuristic fallbacks, DB idempotency
- `test_rag_pipeline.py` — Query routing, prompt templates, grounded citations
- `test_screening.py` — Deterministic evaluation, precedence rules, geographic matching

---

## Public Tender Sources

Official public tenders processed by the platform:
- [CESL Convergence Portal](https://www.convergence.co.in/tender) — Notice Inviting Tenders (NIT) for electric bus fleet operations

---

## License

This project is licensed under the [MIT License](LICENSE).
