import pytest
from fastapi.responses import JSONResponse
from src.app.api.v1.routers.health import healthz


@pytest.mark.asyncio
async def test_healthz_return_value(monkeypatch):
    mock_response = {"service": "market-data-api", "status": "ok", "version": "1.0.0"}

    monkeypatch.setattr("src.app.api.v1.routers.health.get_health", lambda: mock_response)

    response = await healthz()
    assert isinstance(response, JSONResponse)
    assert response.status_code == 200

    payload = response.body.decode()
    expected_content = '{"service":"market-data-api","status":"ok","version":"1.0.0"}'
    assert payload == expected_content
    