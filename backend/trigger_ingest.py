import asyncio
import os
import sys

from app.db.database import SessionLocal
from app.db.models import IngestionJob, IngestionStatusEnum
from app.agent.pipeline import run_ingestion_pipeline

def trigger():
    db = SessionLocal()
    job = IngestionJob(status=IngestionStatusEnum.PENDING)
    db.add(job)
    db.commit()
    db.refresh(job)
    job_id = str(job.id)
    db.close()
    
    print(f"Triggering ingestion job {job_id}")
    run_ingestion_pipeline(job_id)
    print("Ingestion finished.")

if __name__ == "__main__":
    trigger()
