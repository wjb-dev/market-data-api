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
    description="""
    Lightweight health check endpoint consumed by container orchestrators to verify container liveness and readiness.
    
    **Purpose:**
    - **Liveness Probe:** Determines if the container is running and responsive
    - **Readiness Probe:** Verifies the container is ready to receive traffic
    - **Startup Probe:** Checks if the container has successfully started
    
    **Orchestrator Integration:**
    - **Kubernetes:** Liveness and readiness probe configuration
    - **Docker Swarm:** Health check for service discovery
    - **Nomad:** Service health monitoring
    - **ECS:** Target group health checks
    
    **Health Check Behavior:**
    - **Response Time:** <5ms for basic health checks
    - **Memory Usage:** Minimal impact on container resources
    - **Dependencies:** No external service dependencies
    - **Status Codes:** 200 (healthy), 503 (unhealthy)
    
    **Configuration Example:**
    ```yaml
    # Kubernetes liveness probe
    livenessProbe:
      httpGet:
        path: /healthz
        port: 8000
      initialDelaySeconds: 30
      periodSeconds: 10
      timeoutSeconds: 5
      failureThreshold: 3
    ```
    
    **Use Cases:**
    - Container orchestration health monitoring
    - Load balancer health checks
    - Auto-scaling decisions
    - Service mesh health verification
    """,
    responses={
        200: {
            "description": "Container is alive and ready",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "timestamp": "2025-08-16T00:30:00Z",
                        "version": "1.0.0",
                        "uptime": "24h 0m 0s",
                        "checks": {
                            "api": "healthy",
                            "memory": "healthy",
                            "disk": "healthy"
                        }
                    }
                }
            },
            "headers": {
                "X-Health-Check": {"description": "Health check identifier", "schema": {"type": "string"}},
                "X-Container-Id": {"description": "Container identifier", "schema": {"type": "string"}},
                "X-Uptime": {"description": "Container uptime", "schema": {"type": "string"}}
            }
        },
        503: {
            "description": "Container is not ready",
            "content": {
                "application/json": {
                    "example": {
                        "status": "unhealthy",
                        "timestamp": "2025-08-16T00:30:00Z",
                        "version": "1.0.0",
                        "uptime": "0h 0m 30s",
                        "checks": {
                            "api": "starting",
                            "memory": "healthy",
                            "disk": "healthy"
                        },
                        "issues": ["API service is still starting up"]
                    }
                }
            }
        }
    },
    tags=["Health"],
    openapi_extra={
        "x-kubernetes": {
            "livenessProbe": {
                "httpGet": {"path": "/healthz", "port": 8000},
                "initialDelaySeconds": 30,
                "periodSeconds": 10,
                "timeoutSeconds": 5,
                "failureThreshold": 3
            },
            "readinessProbe": {
                "httpGet": {"path": "/healthz", "port": 8000},
                "initialDelaySeconds": 5,
                "periodSeconds": 5,
                "timeoutSeconds": 3,
                "failureThreshold": 1
            }
        }
    }
)
async def healthz() -> JSONResponse:
    payload = get_health()
    return JSONResponse(payload)