from __future__ import annotations
from datetime import datetime
from typing import List, Literal, Optional, Set
from pydantic import BaseModel, Field

Side = Literal["support", "resistance"]

class SRLevel(BaseModel):
    price: float
    side: Side
    touches: int = 0
    strength: float = Field(..., ge=0.0, le=1.0, description="0..1 composite score")
    firstSeen: Optional[datetime] = None
    lastSeen: Optional[datetime] = None
    sources: List[int] = Field(default_factory=None, description="Window sizes (days) that detected this level")

class SRResponse(BaseModel):
    symbol: str
    windows: List[int]
    atr14: dict[int, float]
    levels: List[SRLevel]
