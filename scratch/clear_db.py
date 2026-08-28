import sys
import os

sys.path.append(os.path.join(os.path.abspath(''), 'backend'))
sys.path.append(os.path.abspath(''))

from app.db.database import SessionLocal, engine
from app.db.models import Base, Tender, Document, DocumentChunk, ScreeningResult, TenderEligibility, IngestionJob

def clear_all_data():
    db = SessionLocal()
    try:
        print("Deleting DocumentChunks...")
        db.query(DocumentChunk).delete()
        print("Deleting Documents...")
        db.query(Document).delete()
        print("Deleting ScreeningResults...")
        db.query(ScreeningResult).delete()
        print("Deleting TenderEligibility...")
        db.query(TenderEligibility).delete()
        print("Deleting Tenders...")
        db.query(Tender).delete()
        print("Deleting IngestionJobs...")
        db.query(IngestionJob).delete()
        db.commit()
        print("Successfully cleared all data from DB.")
    except Exception as e:
        db.rollback()
        print(f"Error clearing data: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    clear_all_data()
