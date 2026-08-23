import sys
sys.path.insert(0, '.')
from app.db.database import SessionLocal
from app.services.embeddings import generate_embedding
from sqlalchemy import text as sa_text
from app.db.models import DocumentChunk, Tender, Document
from sqlalchemy import select

db = SessionLocal()

query_vector = generate_embedding("What is the minimum annual turnover required?")
print(f"Query vector dimension: {len(query_vector)}")

vector_str = "[" + ",".join(str(float(v)) for v in query_vector) + "]"
cos_dist_sql = f"document_chunks.embedding <=> '{vector_str}'::vector"

try:
    stmt = (
        select(
            DocumentChunk,
            Tender.title,
            Document.file_name,
            sa_text(cos_dist_sql).label("cos_dist")
        )
        .join(Tender, DocumentChunk.tender_id == Tender.id)
        .join(Document, DocumentChunk.document_id == Document.id)
        .order_by(sa_text(cos_dist_sql))
        .limit(3)
    )
    results = db.execute(stmt).all()
    print(f"Got {len(results)} results!")
    for row in results:
        chunk = row[0]
        title = row[1]
        fname = row[2]
        dist = row[3]
        print(f"  [{1-float(dist):.4f}] {title[:40]} | {fname}")
        print(f"    {chunk.chunk_text[:100]}")
except Exception as e:
    import traceback
    print(f"ERROR: {e}")
    traceback.print_exc()

db.close()
