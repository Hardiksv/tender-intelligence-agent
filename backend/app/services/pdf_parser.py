import hashlib
import os
from typing import Any

import pymupdf

from app.core.exceptions import ParsingException
from app.core.logging import log_action, logger
from app.services.language import detect_document_language

_PDF_MAGIC = b"%PDF-"


def _validate_is_real_pdf(file_path: str, file_bytes: bytes) -> None:
    """Guards against non-PDF content (HTML error pages, etc.) saved with a .pdf extension."""
    header = file_bytes[:1024].lstrip(b"\xef\xbb\xbf")
    if not header.startswith(_PDF_MAGIC):
        snippet = file_bytes[:120].decode("utf-8", errors="replace").strip().replace("\n", " ")
        raise ParsingException(
            f"'{os.path.basename(file_path)}' does not have a valid PDF header (%PDF-). "
            f"This usually means a scraper saved an HTML/error page with a .pdf extension. "
            f"First bytes: {snippet!r}"
        )


def parse_pdf_document(file_path: str) -> dict[str, Any]:
    """
    Parses a PDF document into page-aware text chunks, computes SHA-256 document hash,
    and runs language detection.
    """
    if not os.path.exists(file_path):
        raise ParsingException(f"File not found at path: {file_path}")

    try:
        with open(file_path, "rb") as f:
            file_bytes = f.read()
            doc_hash = hashlib.sha256(file_bytes).hexdigest()

        _validate_is_real_pdf(file_path, file_bytes)

        doc = pymupdf.open(file_path)
        page_count = len(doc)
        pages_data: list[dict[str, Any]] = []
        full_text_parts: list[str] = []

        for page_idx in range(page_count):
            page = doc.load_page(page_idx)
            page_text = page.get_text("text") or ""
            
            # OCR fallback for scanned pages
            if len(page_text.strip()) < 50 and page_idx < 15:
                logger.info(f"Page {page_idx + 1} has very little text. Attempting OCR...")
                try:
                    import easyocr
                    import numpy as np
                    reader = easyocr.Reader(['en'], gpu=False, verbose=False)
                    pix = page.get_pixmap()
                    img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
                    # Convert to RGB if needed
                    if pix.n == 4:
                        import cv2
                        img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2RGB)
                    elif pix.n == 1:
                        import cv2
                        img_array = cv2.cvtColor(img_array, cv2.COLOR_GRAY2RGB)
                        
                    result = reader.readtext(img_array, detail=0)
                    ocr_text = " ".join(result)
                    page_text += "\n" + ocr_text
                    logger.info(f"OCR extracted {len(ocr_text)} chars from page {page_idx + 1}")
                except ImportError:
                    logger.info(f"EasyOCR not installed (Vercel limits). Falling back to Cloud OCR API for page {page_idx + 1}...")
                    import requests
                    pix = page.get_pixmap()
                    img_bytes = pix.tobytes("png")
                    res = requests.post(
                        'https://api.ocr.space/parse/image',
                        data={'apikey': os.environ.get('OCR_SPACE_API_KEY', ''), 'language': 'eng', 'scale': 'true'},
                        files={'file': ('page.png', img_bytes)},
                        timeout=15
                    )
                    if res.status_code == 200:
                        parsed = res.json()
                        if not parsed.get("IsErroredOnProcessing"):
                            ocr_text = " ".join([r.get("ParsedText", "") for r in parsed.get("ParsedResults", [])])
                            page_text += "\n" + ocr_text
                            logger.info(f"Cloud OCR extracted {len(ocr_text)} chars from page {page_idx + 1}")
                except Exception as ocr_err:
                    logger.warning(f"OCR failed for page {page_idx + 1}: {ocr_err}")

            page_number = page_idx + 1

            pages_data.append({
                "page_number": page_number,
                "text": page_text.strip()
            })
            full_text_parts.append(page_text.strip())

        doc.close()
        full_text = "\n\n".join(full_text_parts)

        is_english, detected_lang = detect_document_language(full_text)

        result = {
            "file_name": os.path.basename(file_path),
            "file_path": file_path,
            "document_hash": doc_hash,
            "page_count": page_count,
            "pages": pages_data,
            "full_text": full_text,
            "detected_language": detected_lang,
            "is_english": is_english
        }

        log_action(
            "PDF_PARSED",
            status="SUCCESS",
            details={
                "file_name": os.path.basename(file_path),
                "page_count": page_count,
                "document_hash": doc_hash[:12],
                "detected_language": detected_lang
            }
        )

        return result

    except ParsingException:
        raise
    except Exception as e:
        logger.error(f"Error parsing PDF file {file_path}: {e!s}")
        raise ParsingException(f"Failed to parse PDF document: {e!s}")
