"""
Candle schema for market data bars
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class Candle(BaseModel):
    """Market data candle/bar"""
    timestamp: datetime = Field(..., description="Open time (UTC)")
    open: float = Field(..., description="Open price")
    high: float = Field(..., description="High price")
    low: float = Field(..., description="Low price")
    close: float = Field(..., description="Close price")
    volume: float = Field(..., description="Volume")
    vwap: Optional[float] = Field(None, description="Volume weighted average price")
    changePercent: float = Field(..., description="Price change percentage")
