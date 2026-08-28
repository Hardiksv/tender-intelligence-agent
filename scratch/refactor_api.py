import sys
import os

filepath = r'backend/app/api/tenders.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

import re

# 1. Update format_tender_response to include is_active
content = re.sub(
    r'document_hash=t.document_hash,(\s+)created_at',
    r'document_hash=t.document_hash,\1is_active=t.is_active,\1created_at',
    content
)

# 2. In get_tenders, filter by is_active==True
content = re.sub(
    r'query = db.query\(Tender\)',
    r'query = db.query(Tender).filter(Tender.is_active == True)',
    content
)

# 3. Remove CATALOG fallback from get_tender_by_id
get_tender_by_id_new = """@router.get("/{tender_id}", response_model=TenderResponse)
async def get_tender_by_id(tender_id: str, db: Session = Depends(get_db)):
    t = None
    try:
        t = db.query(Tender).filter(Tender.id == tender_id).first()
    except Exception as e:
        logger.warning(f"Database lookup failed for tender {tender_id}: {e}")
        t = None

    if t:
        try:
            return format_tender_response(t)
        except Exception as e:
            logger.warning(f"Failed formatting database tender {tender_id}: {e}")
            raise HTTPException(status_code=500, detail="Error formatting tender")

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tender {tender_id} not found.")"""

content = re.sub(r'@router.get\("/\{tender_id\}", response_model=TenderResponse\).*?raise HTTPException\(status_code=status.HTTP_404_NOT_FOUND.*?not found."\)', get_tender_by_id_new, content, flags=re.DOTALL)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated backend/app/api/tenders.py")
