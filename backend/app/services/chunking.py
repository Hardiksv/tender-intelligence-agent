import re
from typing import Any


def chunk_document_pages(
    pages: list[dict[str, Any]],
    target_chunk_size: int = 800,
    overlap: int = 150
) -> list[dict[str, Any]]:
    """
    Semantically chunks page-aware document text while preserving page number metadata
    and clause boundaries.
    """
    chunks: list[dict[str, Any]] = []
    chunk_index = 0

    for page_item in pages:
        page_num = page_item["page_number"]
        page_text = page_item["text"]

        if not page_text.strip():
            continue

        paragraphs = re.split(r'\n\s*\n', page_text)
        current_chunk_text = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current_chunk_text) + len(para) <= target_chunk_size:
                current_chunk_text += ("\n\n" + para) if current_chunk_text else para
            else:
                chunks.append({
                    "chunk_text": current_chunk_text,
                    "page_number": page_num,
                    "chunk_index": chunk_index,
                    "chunk_metadata": {
                        "page_number": page_num,
                        "length": len(current_chunk_text)
                    }
                })
                chunk_index += 1

                overlap_text = current_chunk_text[-overlap:] if len(current_chunk_text) > overlap else ""
                current_chunk_text = (overlap_text + "\n\n" + para).strip()

        if current_chunk_text.strip():
            chunks.append({
                "chunk_text": current_chunk_text,
                "page_number": page_num,
                "chunk_index": chunk_index,
                "chunk_metadata": {
                    "page_number": page_num,
                    "length": len(current_chunk_text)
                }
            })
            chunk_index += 1

    return chunks
