from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field


# =========================
# Enums
# =========================
class Timeframe(StrEnum):
    m1 = "1m"
    m5 = "5m"
    m15 = "15m"
    h1 = "1h"
    h4 = "4h"
    d1 = "1D"
    w1 = "1W"
    m1c = "1M"


class Regime(StrEnum):
    risk_on = "risk_on"
    risk_off = "risk_off"
    mixed = "mixed"


# =========================
# Error / Health
# =========================
class Error(BaseModel):
    error: str
    message: str
    details: Optional[Dict[str, object]] = None


class ServiceHealth(BaseModel):
    status: StrEnum | str = Field(default="ok", description="ok | degraded | down")
    latencyMs: Optional[int] = None
    lastChecked: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: Optional[Dict[str, object]] = None


# =========================
# Quote / Technicals
# =========================
class PriceQuote(BaseModel):
    symbol: str
    last: float
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    prevClose: Optional[float] = None
    volume: Optional[float] = None
    change: Optional[float] = None
    changePercent: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    currency: Optional[str] = "USD"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MACD(BaseModel):
    macd: Optional[float] = None
    signal: Optional[float] = None
    hist: Optional[float] = None


class MovingAverages(BaseModel):
    sma50: Optional[float] = None
    sma200: Optional[float] = None
    ema20: Optional[float] = None
    ema50: Optional[float] = None


class Levels(BaseModel):
    support: Optional[List[float]] = None
    resistance: Optional[List[float]] = None


class TechnicalIndicators(BaseModel):
    rsi: Optional[float] = None
    macd: Optional[MACD] = None
    ma: Optional[MovingAverages] = None
    levels: Optional[Levels] = None
    atr: Optional[float] = None
    meta: Optional[Dict[str, object]] = None  # e.g., {"timeframe":"1D","asOf":"..."}


# =========================
# Indices / Rates / Overview
# =========================
class IndexQuote(BaseModel):
    last: float
    changePercent: Optional[float] = None


BondYields = Dict[str, float]  # e.g., {"US02Y": 4.55, "US10Y": 4.18}


class Breadth(BaseModel):
    advancers: Optional[int] = None
    decliners: Optional[int] = None


class MarketOverview(BaseModel):
    indices: Optional[Dict[str, IndexQuote]] = None
    vix: Optional[float] = None
    rates: Optional[BondYields] = None
    breadth: Optional[Breadth] = None
    regime: Optional[Regime] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
