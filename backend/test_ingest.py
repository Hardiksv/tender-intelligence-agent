import sys
from app.db.database import SessionLocal
from app.agent.pipeline import run_ingestion_pipeline
from app.db.models import IngestionJob, IngestionStatusEnum
import uuid

db = SessionLocal()
j = IngestionJob(id=uuid.uuid4(), status=IngestionStatusEnum.PENDING)
db.add(j)
db.commit()

print(f"Starting job {j.id}")
print("Setup successful!")
