import asyncio
import os
from sqlalchemy import text
from app.db.database import SessionLocal
from app.db.models import Tender, Document, DocumentChunk

def reset_db():
    db = SessionLocal()
    
    # Let's count existing tenders
    tenders = db.query(Tender).all()
    print(f"Found {len(tenders)} existing tenders.")
    
    # Delete them all so we get a fresh seed
    db.query(DocumentChunk).delete()
    db.query(Document).delete()
    db.query(Tender).delete()
    
    db.commit()
    print("Database wiped. Ready for fresh ingestion.")
    db.close()

if __name__ == "__main__":
    reset_db()
