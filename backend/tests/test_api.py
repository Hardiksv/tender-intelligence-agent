import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.cost_tracking import calculate_llm_cost
from app.core.exceptions import ConcurrentIngestionException

client = TestClient(app)


def test_health_check_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["timezone"] == "Asia/Kolkata"


def test_cost_tracking_dynamic_pricing():
    usage = {
        "prompt_tokens": 10000,
        "completion_tokens": 2000,
        "total_tokens": 12000,
        "is_estimated": False
    }
    cost_info = calculate_llm_cost(usage)

    assert cost_info["cost_usd"] == 0.008
    assert cost_info["prompt_tokens"] == 10000
    assert cost_info["completion_tokens"] == 2000
    assert "Verified Gemini 2.5 Flash Rates" in cost_info["pricing_source"]


def test_concurrent_ingestion_rejection_logic():
    """
    Verifies that launching concurrent ingestion raises HTTP 409 Conflict exception.
    """
    from unittest.mock import MagicMock
    from app.db.models import IngestionJob, IngestionStatusEnum

    mock_db = MagicMock()
    mock_active_job = IngestionJob(
        id="job-active-123",
        status=IngestionStatusEnum.RUNNING
    )
    mock_db.query().filter().first.return_value = mock_active_job

    with pytest.raises(ConcurrentIngestionException) as exc_info:
        from app.api.ingestion import trigger_ingestion_run
        import asyncio
        asyncio.run(trigger_ingestion_run(background_tasks=MagicMock(), db=mock_db))

    assert "already currently running" in str(exc_info.value)
