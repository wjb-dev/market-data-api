"""
Candle schema for market data bars
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field

# Import SRResponse for the levels endpoint
from .levels import SRResponse


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


# Technical Indicators Schemas
class SMAIndicator(BaseModel):
    """Simple Moving Average indicator"""
    timestamp: datetime = Field(..., description="Timestamp for the indicator value")
    value: float = Field(..., description="SMA value")
    period: int = Field(..., description="Period used for calculation")


class EMAIndicator(BaseModel):
    """Exponential Moving Average indicator"""
    timestamp: datetime = Field(..., description="Timestamp for the indicator value")
    value: float = Field(..., description="EMA value")
    period: int = Field(..., description="Period used for calculation")


class RSIIndicator(BaseModel):
    """Relative Strength Index indicator"""
    timestamp: datetime = Field(..., description="Timestamp for the indicator value")
    value: float = Field(..., description="RSI value (0-100)")
    period: int = Field(..., description="Period used for calculation")


class MACDIndicator(BaseModel):
    """Moving Average Convergence Divergence indicator"""
    timestamp: datetime = Field(..., description="Timestamp for the indicator value")
    macd: float = Field(..., description="MACD line value")
    signal: float = Field(..., description="Signal line value")
    histogram: float = Field(..., description="MACD histogram value")
    fast_period: int = Field(..., description="Fast EMA period")
    slow_period: int = Field(..., description="Slow EMA period")
    signal_period: int = Field(..., description="Signal line period")


class BollingerBandsIndicator(BaseModel):
    """Bollinger Bands indicator"""
    timestamp: datetime = Field(..., description="Timestamp for the indicator value")
    upper: float = Field(..., description="Upper band value")
    middle: float = Field(..., description="Middle band (SMA) value")
    lower: float = Field(..., description="Lower band value")
    period: int = Field(..., description="Period used for calculation")
    std_dev: float = Field(..., description="Standard deviation multiplier")


class ATRIndicator(BaseModel):
    """Average True Range indicator"""
    timestamp: datetime = Field(..., description="Timestamp for the indicator value")
    value: float = Field(..., description="ATR value")
    period: int = Field(..., description="Period used for calculation")


class TechnicalIndicatorsResponse(BaseModel):
    """Response model for technical indicators endpoint"""
    symbol: str = Field(..., description="Stock symbol")
    period: int = Field(..., description="Period used for calculations")
    days: int = Field(..., description="Number of days analyzed")
    timestamp: datetime = Field(..., description="Analysis timestamp")
    indicators: Dict[str, Any] = Field(..., description="Calculated indicators")
    sma: Optional[List[SMAIndicator]] = Field(None, description="Simple Moving Average values")
    ema: Optional[List[EMAIndicator]] = Field(None, description="Exponential Moving Average values")
    rsi: Optional[List[RSIIndicator]] = Field(None, description="Relative Strength Index values")
    macd: Optional[List[MACDIndicator]] = Field(None, description="MACD values")
    bbands: Optional[List[BollingerBandsIndicator]] = Field(None, description="Bollinger Bands values")
    atr: Optional[List[ATRIndicator]] = Field(None, description="Average True Range values")


# Candlestick Patterns Schemas
class CandlestickPattern(BaseModel):
    """Individual candlestick pattern detection"""
    timestamp: datetime = Field(..., description="When the pattern occurred")
    position: int = Field(..., description="Position in the data series")
    confidence: float = Field(..., description="Pattern confidence level (0-1)")
    type: Optional[str] = Field(None, description="Pattern type (for engulfing patterns)")


class CandlestickPatternsResponse(BaseModel):
    """Response model for candlestick patterns endpoint"""
    symbol: str = Field(..., description="Stock symbol")
    days: int = Field(..., description="Number of days analyzed")
    timestamp: datetime = Field(..., description="Analysis timestamp")
    patterns: Dict[str, List[CandlestickPattern]] = Field(..., description="Detected patterns by type")
    doji: Optional[List[CandlestickPattern]] = Field(None, description="Doji patterns detected")
    hammer: Optional[List[CandlestickPattern]] = Field(None, description="Hammer patterns detected")
    engulfing: Optional[List[CandlestickPattern]] = Field(None, description="Engulfing patterns detected")


# Pivot Points Schemas
class PivotLevels(BaseModel):
    """Pivot point levels for a specific timeframe"""
    timestamp: datetime = Field(..., description="Timestamp for the pivot calculation")
    pivot: float = Field(..., description="Central pivot point")
    r1: float = Field(..., description="Resistance level 1")
    r2: float = Field(..., description="Resistance level 2")
    r3: float = Field(..., description="Resistance level 3")
    s1: float = Field(..., description="Support level 1")
    s2: float = Field(..., description="Support level 2")
    s3: float = Field(..., description="Support level 3")
    high: float = Field(..., description="High price used in calculation")
    low: float = Field(..., description="Low price used in calculation")
    close: float = Field(..., description="Close price used in calculation")


class PivotPointsResponse(BaseModel):
    """Response model for pivot points endpoint"""
    symbol: str = Field(..., description="Stock symbol")
    timeframe: str = Field(..., description="Timeframe used (daily, weekly, monthly)")
    method: str = Field(..., description="Calculation method used")
    periods: int = Field(..., description="Number of periods calculated")
    timestamp: datetime = Field(..., description="Analysis timestamp")
    pivots: List[PivotLevels] = Field(..., description="Pivot point levels")


class MultiTimeframePivotsResponse(BaseModel):
    """Response model for multi-timeframe pivot points endpoint"""
    symbol: str = Field(..., description="Stock symbol")
    methods: List[str] = Field(..., description="Methods used for calculation")
    timestamp: datetime = Field(..., description="Analysis timestamp")
    daily: Optional[Dict[str, List[PivotLevels]]] = Field(None, description="Daily pivot points by method")
    weekly: Optional[Dict[str, List[PivotLevels]]] = Field(None, description="Weekly pivot points by method")
    monthly: Optional[Dict[str, List[PivotLevels]]] = Field(None, description="Monthly pivot points by method")


# Cache Status Schema
class CacheStatusResponse(BaseModel):
    """Response model for cache status endpoint"""
    cache_name: str = Field(..., description="Name of the cache")
    cache_size: int = Field(..., description="Current cache size in memory")
    ttl_seconds: int = Field(..., description="Time-to-live in seconds")
    total_requests: int = Field(..., description="Total requests processed")
    cache_hits: int = Field(..., description="Number of cache hits")
    cache_misses: int = Field(..., description="Number of cache misses")
    hit_rate_percent: float = Field(..., description="Cache hit rate percentage")
    redis_hits: int = Field(..., description="Number of Redis cache hits")
    memory_hits: int = Field(..., description="Number of memory cache hits")
    redis_errors: int = Field(..., description="Number of Redis errors")
    status: str = Field(..., description="Cache status")
