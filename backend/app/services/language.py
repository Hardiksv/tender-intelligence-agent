
from langdetect import DetectorFactory, detect

from app.core.logging import log_action, logger

DetectorFactory.seed = 0


def detect_document_language(full_text: str) -> tuple[bool, str]:
    """
    Detects predominant document language.
    Returns (is_english: bool, detected_lang_code: str).
    """
    if not full_text or len(full_text.strip()) < 20:
        return True, "en"

    try:
        detected_lang = detect(full_text)
        is_english = detected_lang.lower() == "en"

        if not is_english:
            log_action(
                "LANGUAGE_UNSUPPORTED",
                status="FLAGGED",
                details={
                    "detected_language": detected_lang,
                    "reason": f"Document is written in '{detected_lang}', expected English ('en')."
                }
            )
        return is_english, detected_lang
    except Exception as e:
        logger.warning(f"Language detection failed, assuming English: {e}")
        return True, "en"
