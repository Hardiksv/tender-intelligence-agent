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
    logger.info("Tender Intelligence API started.")
    try:
        from app.db.database import SessionLocal
        from app.db.models import Document, Tender
        db = SessionLocal()
        tender_count = db.query(Tender).filter(Tender.is_active == True).count()
        doc_count = db.query(Document).count()
        logger.info(f"Startup check: {tender_count} active tenders, {doc_count} documents.")
        db.close()
        if settings.DISCOVERY_ENABLED:
            from app.services.discover_tenders import start_discovery_scheduler
            start_discovery_scheduler(interval_minutes=60)
    except Exception as e:
        logger.error(f"Startup DB check failed: {e}")
    yield
    logger.info("Tender Intelligence API stopped.")


app = FastAPI(
    title="Tender Intelligence Agent API",
    description="Production-grade AI pipeline for public Bus Operations tender analysis, screening, and RAG Q&A",
    version="1.0.0",
    lifespan=lifespan
)

# Secure CORS: specify allowed origins rather than wildcard with credentials
allowed_origins = [settings.FRONTEND_ORIGIN]
for origin in [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://tender-intelligence-agen.vercel.app"
]:
    if origin not in allowed_origins:
        allowed_origins.append(origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
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


@app.get("/health", tags=["Health"])
@app.get("/api/health", tags=["Health"])
async def health_check():
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
async def list_tenders_alias(db=Depends(get_db)):
    return await tenders.list_tenders(db=db)


@app.post("/ask", tags=["RAG Alias"])
async def ask_alias(req: chat.ChatRequest, db=Depends(get_db)):
    return await chat.chat_qna(req, db=db)


@app.post("/search", tags=["Search Alias"])
async def search_alias(req: chat.ChatRequest, db=Depends(get_db)):
    return await chat.chat_qna(req, db=db)


@app.post("/ingest", tags=["Ingestion Alias"])
async def ingest_alias(background_tasks: BackgroundTasks, db=Depends(get_db)):
    return await ingestion.trigger_ingestion_run(background_tasks, db=db)


@app.api_route("/api/discover", methods=["GET", "POST"], tags=["Discovery"])
async def trigger_discovery_api(
    background_tasks: BackgroundTasks,
    db=Depends(get_db)
):
    from app.db.models import IngestionJob, IngestionStatusEnum
    from app.services.discover_tenders import run_discovery_and_ingest_job

    try:
        active_job = db.query(IngestionJob).filter(IngestionJob.status == IngestionStatusEnum.RUNNING).first()
        if active_job:
            return JSONResponse(
                status_code=409,
                content={"detail": f"An ingestion or discovery job (ID: {active_job.id}) is already currently running."}
            )
    except Exception as e:
        logger.warning(f"Error querying active ingestion job: {e}")

    job = IngestionJob(
        status=IngestionStatusEnum.PENDING,
        total_documents=0,
        completed_documents=0,
        failed_documents=0
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    background_tasks.add_task(run_discovery_and_ingest_job, str(job.id))
    return {"job_id": str(job.id), "status": "PENDING"}


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
