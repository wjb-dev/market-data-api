from pydantic import BaseModel
from typing import Dict, Any

class HealthResponse(BaseModel):
    service: str
    status: str
    version: str
    services: Dict[str, Any]

    class Config:
        json_schema_extra = {
            "example": {
                "service": "market-data-api",
                "status": "ok",
                "version": "0.1.0",
                "services": {
                    
                    "redis": "ok"
                }
            }
        }
