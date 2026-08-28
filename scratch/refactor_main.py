import sys
import os

filepath = r'backend/app/main.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

import re

# Remove data_raw_dir checks
new_lifespan = """@asynccontextmanager
async def lifespan(app: FastAPI):
    \"\"\"Lifespan context manager for startup and shutdown.\"\"\"
    logger.info("Tender Intelligence API started.")
    try:
        from app.db.database import SessionLocal
        from app.db.models import Tender, Document
        db = SessionLocal()
        tender_count = db.query(Tender).filter(Tender.is_active == True).count()
        doc_count = db.query(Document).count()
        
        logger.info(f"STARTUP DB HEALTH CHECK: {tender_count} Active Tenders, {doc_count} DB Documents")
        db.close()
        
        from app.core.config import settings
        if settings.DISCOVERY_ENABLED:
            logger.info("Starting background tender discovery scheduler...")
            from scripts.discover_tenders import start_discovery_scheduler
            start_discovery_scheduler(interval_minutes=60)
            
    except Exception as e:
        logger.error(f"STARTUP DB HEALTH CHECK FAILED: {e}")
    yield
    logger.info("Tender Intelligence API stopped.")"""

content = re.sub(r'@asynccontextmanager.*?logger\.info\("Tender Intelligence API stopped."\)', new_lifespan, content, flags=re.DOTALL)

# In api/discover
new_discover = """@app.post("/api/discover", tags=["Discovery"])
async def trigger_discovery_api():
    \"\"\"Trigger the tender discovery cycle manually (synchronous for serverless).\"\"\"
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    from scripts.discover_tenders import run_discovery_cycle, CESLTenderSource
    
    try:
        sources = [CESLTenderSource()]
        # Pass empty string since data_raw_dir is no longer used
        run_discovery_cycle(sources, "")
        return {"status": "success", "message": "Discovery cycle completed"}
    except Exception as e:
        logger.error(f"Discovery API failed: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})"""

content = re.sub(r'@app\.post\("/api/discover", tags=\["Discovery"\]\).*?return JSONResponse.*?\}', new_discover, content, flags=re.DOTALL)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated backend/app/main.py")
