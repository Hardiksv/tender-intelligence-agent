import sys
sys.path.insert(0, '.')
from app.db.database import SessionLocal
from app.services.retrieval import retrieve_relevant_context

db = SessionLocal()
results = retrieve_relevant_context(db, 'What is the minimum annual turnover required?', top_k=3)
print(f'Got {len(results)} results')
for r in results:
    score = r["similarity_score"]
    title = r["tender_title"][:40]
    text = r["text"][:80]
    print(f'  score={score} title={title}')
    print(f'  text={text}')
db.close()
