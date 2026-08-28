import re
import os

filepath = r'backend/app/agent/pipeline.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Remove CATALOG dict
content = re.sub(r'CATALOG = \{.*?\n\}\n', '', content, flags=re.DOTALL)

# 2. Modify run_ingestion_pipeline
old_func_start = """        pdf_files = custom_pdf_paths if custom_pdf_paths else []
        if not custom_pdf_paths:
            pdf_files = glob.glob(os.path.join(SEED_DATA_DIR, "*.pdf"))
        
        job.total_documents = len(pdf_files)
        db.commit()

        for pdf_path in pdf_files:
            file_name = os.path.basename(pdf_path)
            job.current_document = file_name
            db.commit()

            meta = None
            if custom_meta and file_name in custom_meta:
                meta = custom_meta[file_name]
            
            if not meta:
                meta = CATALOG.get(file_name)

            if not meta:
                logger.warning(f"File {file_name} not in catalog. Skipping.")
                job.failed_documents += 1
                db.commit()
                continue"""

new_func_start = """        pdf_files = custom_pdf_paths if custom_pdf_paths else []
        
        job.total_documents = len(pdf_files)
        db.commit()

        for pdf_path in pdf_files:
            file_name = os.path.basename(pdf_path)
            job.current_document = file_name
            db.commit()

            meta = None
            if custom_meta and file_name in custom_meta:
                meta = custom_meta[file_name]

            if not meta:
                logger.warning(f"File {file_name} has no provided metadata. Skipping.")
                job.failed_documents += 1
                db.commit()
                continue"""

content = content.replace(old_func_start, new_func_start)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated pipeline.py")
