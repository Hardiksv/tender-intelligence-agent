from contextlib import asynccontextmanager

import uvicorn
from fastapi import BackgroundTasks, Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from app.api import chat, ingestion, profile, screening, tenders
from app.core.config import settings
from app.core.exceptions import (
    ConcurrentIngestionException,
    EmbeddingDimensionMismatchException,
    LanguageUnsupportedException,
    TenderAgentException,
)
from app.core.logging import log_action, logger
from app.db.database import get_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown."""
    logger.info("Tender Intelligence API started.")
    try:
        import os
        from app.db.database import SessionLocal
        from app.db.models import Tender, Document
        db = SessionLocal()
        tender_count = db.query(Tender).count()
        doc_count = db.query(Document).count()
        
        data_raw_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "raw")
        source_docs = len([f for f in os.listdir(data_raw_dir) if f.endswith(".pdf")]) if os.path.exists(data_raw_dir) else 0
        
        logger.info(f"STARTUP DB HEALTH CHECK: {tender_count} Tenders, {doc_count} DB Documents, {source_docs} Source PDFs in data/raw/")
        db.close()
    except Exception as e:
        logger.error(f"STARTUP DB HEALTH CHECK FAILED: {e}")
    yield
    logger.info("Tender Intelligence API stopped.")

app = FastAPI(
    title="Tender Intelligence Agent API",
    description="Production-grade AI pipeline for public Bus Operations tender analysis, screening, and RAG Q&A",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=r".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ConcurrentIngestionException)
async def concurrent_ingestion_handler(request: Request, exc: ConcurrentIngestionException):
    log_action("INGESTION_REJECTED_CONCURRENT", status="REJECTED", details={"message": exc.message})
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": exc.message, "error_code": "CONCURRENT_INGESTION_RUNNING"}
    )


@app.exception_handler(EmbeddingDimensionMismatchException)
async def embedding_mismatch_handler(request: Request, exc: EmbeddingDimensionMismatchException):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": exc.message, "error_code": "EMBEDDING_DIMENSION_MISMATCH"}
    )


@app.exception_handler(LanguageUnsupportedException)
async def language_unsupported_handler(request: Request, exc: LanguageUnsupportedException):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.message, "error_code": "LANGUAGE_UNSUPPORTED"}
    )


@app.exception_handler(TenderAgentException)
async def tender_agent_exception_handler(request: Request, exc: TenderAgentException):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": exc.message, "details": exc.details}
    )


app.include_router(tenders.router)
app.include_router(screening.router)
app.include_router(profile.router)
app.include_router(chat.router)
app.include_router(ingestion.router)

@app.get("/", tags=["Root"])
@app.get("/api", tags=["Root"])
@app.get("/api/", tags=["Root"])
async def root_index():
    """Root status endpoint."""
    return {
        "status": "online",
        "app": "Tender Intelligence Agent API",
        "version": "1.0.0",
        "docs_url": "/docs",
        "api_docs_url": "/api/docs",
        "health_url": "/health",
        "api_health_url": "/api/health"
    }

@app.get("/health", tags=["Health"])
@app.get("/api/health", tags=["Health"])
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "app": "Tender Intelligence Agent",
        "version": "1.0.0",
        "timezone": settings.TIMEZONE
    }

@app.get("/api/docs", include_in_schema=False)
async def api_docs():
    return get_swagger_ui_html(
        openapi_url="/api/openapi.json",
        title="Tender Intelligence Agent - API Docs"
    )

@app.get("/api/openapi.json", include_in_schema=False)
async def api_openapi():
    return JSONResponse(get_openapi(title=app.title, version=app.version, routes=app.routes))

@app.get("/tenders", tags=["Tenders Alias"])
async def list_tenders_alias(db = Depends(get_db)):
    return await tenders.list_tenders(db=db)

@app.post("/ask", tags=["RAG Alias"])
async def ask_alias(req: chat.ChatRequest, db = Depends(get_db)):
    return await chat.chat_qna(req, db=db)

@app.post("/search", tags=["Search Alias"])
async def search_alias(req: chat.ChatRequest, db = Depends(get_db)):
    return await chat.chat_qna(req, db=db)

@app.post("/ingest", tags=["Ingestion Alias"])
async def ingest_alias(background_tasks: BackgroundTasks, db = Depends(get_db)):
    return await ingestion.trigger_ingestion_run(background_tasks, db=db)

@app.post("/api/discover", tags=["Discovery"])
async def trigger_discovery_api():
    """Trigger the tender discovery cycle manually (synchronous for serverless)."""
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    from scripts.discover_tenders import run_discovery_cycle, CESLTenderSource
    
    try:
        sources = [CESLTenderSource()]
        data_raw_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "raw")
        run_discovery_cycle(sources, data_raw_dir)
        return {"status": "success", "message": "Discovery cycle completed"}
    except Exception as e:
        logger.error(f"Discovery API failed: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@app.get("/api/debug-routing", tags=["Debug"])
async def debug_routing(request: Request):
    """Debug endpoint to inspect exact ASGI path and headers received from Vercel."""
    return {
        "url_path": request.url.path,
        "scope_path": request.scope.get("path"),
        "scope_raw_path": request.scope.get("raw_path", b"").decode("utf-8", errors="replace"),
        "query_string": request.scope.get("query_string", b"").decode("utf-8", errors="replace"),
        "headers": {k.decode("utf-8", errors="replace"): v.decode("utf-8", errors="replace") for k, v in request.scope.get("headers", [])}
    }

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
