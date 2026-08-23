import json
import logging
import sys
from datetime import UTC, datetime, timezone

from app.core.config import settings

logger = logging.getLogger("tender_agent")
logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

formatter = logging.Formatter(
    '[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s'
)
handler.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(handler)


def log_action(
    event_type: str,
    tender_id: str | None = None,
    document_id: str | None = None,
    job_id: str | None = None,
    status: str = "SUCCESS",
    details: dict | None = None,
    extra_meta: dict | None = None
):
    """
    Structured action logging for audit and defense call evaluation.
    """
    log_payload = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event_type": event_type,
        "tender_id": str(tender_id) if tender_id else None,
        "document_id": str(document_id) if document_id else None,
        "job_id": str(job_id) if job_id else None,
        "status": status,
        "details": details or {},
        "extra_meta": extra_meta or {}
    }
    logger.info(f"AGENT_EVENT: {json.dumps(log_payload)}")
    return log_payload
