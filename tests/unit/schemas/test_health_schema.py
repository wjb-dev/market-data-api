from src.app.schemas.health import HealthResponse

def test_health_response_model():
    data = {"service":"market-data-api","status":"ok","version":"0.1.0"}
    model = HealthResponse(**data)
    assert model.service == "market-data-api"
    assert model.status == "ok"
    assert model.version == "0.1.0"
