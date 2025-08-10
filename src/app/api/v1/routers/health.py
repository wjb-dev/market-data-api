from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from src.app.schemas.health import HealthResponse
from src.app.services.health import get_health

router = APIRouter(tags=["Health"], prefix="")

@router.get(
    "/healthz",
    summary="Liveness probe",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    description=(
        "Endpoint consumed by orchestrators (K8s, Nomad, …) "
        "to verify that the container is **alive and ready**."
    ),
)
async def healthz() -> JSONResponse:
    payload = get_health()
    return JSONResponse(payload)