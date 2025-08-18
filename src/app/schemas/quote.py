"""
Quote schema for market data matching Alpaca's API response format
Based on: https://docs.alpaca.markets/reference/stocklatestquotesingle-1
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class QuoteData(BaseModel):
    """Quote data matching Alpaca's API response format"""
    timestamp: datetime = Field(..., description="Quote timestamp")
    ask_exchange: str = Field(..., description="Ask exchange code")
    ask_price: float = Field(..., description="Ask price")
    ask_size: int = Field(..., description="Ask size in round lots")
    bid_exchange: str = Field(..., description="Bid exchange code")
    bid_price: float = Field(..., description="Bid price")
    bid_size: int = Field(..., description="Bid size in round lots")
    conditions: List[str] = Field(..., description="Quote conditions")
    tape: str = Field(..., description="Tape")
    
    # Additional fields from Alpaca's API
    sip_timestamp: Optional[datetime] = Field(None, description="SIP timestamp")
    participant_timestamp: Optional[datetime] = Field(None, description="Participant timestamp")
    trade_id: Optional[int] = Field(None, description="Trade ID")
    quote_id: Optional[int] = Field(None, description="Quote ID")
    
    # Calculated fields
    spread: Optional[float] = Field(None, description="Bid-ask spread")
    spread_pct: Optional[float] = Field(None, description="Bid-ask spread percentage")
    mid_price: Optional[float] = Field(None, description="Mid price between bid and ask")


class Quote(BaseModel):
    """Quote for a symbol matching Alpaca's API response"""
    symbol: str = Field(..., description="Stock symbol")
    quote: QuoteData = Field(..., description="Quote data")
    
    # Additional metadata
    status: str = Field("success", description="Quote status")
    timestamp: datetime = Field(..., description="Response timestamp")


class VolumeAnalysis(BaseModel):
    """Volume analysis data"""
    current_volume: int = Field(..., description="Current volume")
    avg_volume: int = Field(..., description="Average volume")
    volume_ratio: float = Field(..., description="Volume ratio (current/avg)")
    volume_trend: str = Field(..., description="Volume trend indicator")


class BidAskImbalance(BaseModel):
    """Bid-ask imbalance analysis"""
    bid_volume: int = Field(..., description="Bid volume")
    ask_volume: int = Field(..., description="Ask volume")
    imbalance_ratio: float = Field(..., description="Imbalance ratio")
    pressure: str = Field(..., description="Buying/selling pressure")


class PriceMomentum(BaseModel):
    """Price momentum analysis"""
    daily_change: float = Field(..., description="Daily price change")
    momentum_strength: str = Field(..., description="Momentum strength")
    trend_direction: str = Field(..., description="Trend direction")


class MarketIntelligence(BaseModel):
    """Market intelligence data"""
    symbol: str = Field(..., description="Stock symbol")
    timestamp: datetime = Field(..., description="Analysis timestamp")
    current_price: float = Field(..., description="Current price")
    bid_price: float = Field(..., description="Bid price")
    ask_price: float = Field(..., description="Ask price")
    spread: float = Field(..., description="Bid-ask spread")
    spread_pct: float = Field(..., description="Spread percentage")
    volume_analysis: VolumeAnalysis = Field(..., description="Volume analysis")
    bid_ask_imbalance: BidAskImbalance = Field(..., description="Bid-ask imbalance")
    price_momentum: PriceMomentum = Field(..., description="Price momentum")


class ComparativeAnalysis(BaseModel):
    """Comparative analysis data"""
    symbol: str = Field(..., description="Stock symbol")
    timeframe: str = Field(..., description="Analysis timeframe")
    timestamp: datetime = Field(..., description="Analysis timestamp")
    comparison: Dict[str, Any] = Field(..., description="Benchmark comparisons")
    summary: Dict[str, Any] = Field(..., description="Performance summary")


# Daily Change Schema
class DailyChangeResponse(BaseModel):
    """Response model for daily percent change endpoint"""
    symbol: str = Field(..., description="Stock symbol")
    daily_change_percent: float = Field(..., description="Daily percent change vs previous close")
    timestamp: datetime = Field(..., description="Response timestamp")
    previous_close: Optional[float] = Field(None, description="Previous day's closing price")
    current_price: Optional[float] = Field(None, description="Current price")
    change_amount: Optional[float] = Field(None, description="Absolute price change amount")


# Cache Status Schema
class QuotesCacheStatusResponse(BaseModel):
    """Response model for quotes cache status endpoint"""
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
