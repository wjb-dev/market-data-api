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
    ratio: float = Field(..., description="Volume ratio (current/avg)")
    momentum: str = Field(..., description="Volume momentum indicator")
    strength: str = Field(..., description="Volume strength indicator")


class BidAskImbalance(BaseModel):
    """Bid-ask imbalance analysis"""
    imbalance: str = Field(..., description="Imbalance type")
    bid_ratio: float = Field(..., description="Bid ratio")
    ask_ratio: float = Field(..., description="Ask ratio")
    sentiment: str = Field(..., description="Buying/selling pressure")
    total_size: int = Field(..., description="Total bid + ask size")


class PriceMomentum(BaseModel):
    """Price momentum analysis"""
    momentum: str = Field(..., description="Price momentum")
    change_pct: float = Field(..., description="Price change percentage")
    intraday: str = Field(..., description="Intraday sentiment")
    intraday_change: float = Field(..., description="Intraday change percentage")
    current_price: float = Field(..., description="Current price")
    prev_price: float = Field(..., description="Previous price")
    open_price: float = Field(..., description="Open price")


class Sentiment(BaseModel):
    """Sentiment analysis data"""
    overall: str = Field(..., description="Overall sentiment")
    score: int = Field(..., description="Sentiment score")
    factors: List[str] = Field(..., description="Sentiment factors")
    confidence: str = Field(..., description="Confidence level")


class MarketIntelligence(BaseModel):
    """Market intelligence data"""
    symbol: str = Field(..., description="Stock symbol")
    timestamp: datetime = Field(..., description="Analysis timestamp")
    current_price: float = Field(..., description="Current price")
    bid_price: float = Field(..., description="Bid price")
    ask_price: float = Field(..., description="Ask price")
    spread: float = Field(..., description="Bid-ask spread")
    spread_pct: float = Field(..., description="Spread percentage")
    volume_analysis: Optional[VolumeAnalysis] = Field(None, description="Volume analysis")
    market_imbalance: Optional[BidAskImbalance] = Field(None, description="Bid-ask imbalance")
    price_momentum: Optional[PriceMomentum] = Field(None, description="Price momentum")
    sentiment: Sentiment = Field(..., description="Overall sentiment")


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


class QuotesCacheStatusResponse(BaseModel):
    """Response model for cache status endpoint"""
    cache_name: str = Field(..., description="Cache name")
    cache_size: int = Field(..., description="Number of items in memory cache")
    ttl_seconds: float = Field(..., description="Cache TTL in seconds")
    total_requests: int = Field(..., description="Total cache requests")
    cache_hits: int = Field(..., description="Total cache hits")
    cache_misses: int = Field(..., description="Total cache misses")
    hit_rate_percent: float = Field(..., description="Cache hit rate percentage")
    redis_hits: int = Field(..., description="Redis cache hits")
    memory_hits: int = Field(..., description="Memory cache hits")
    redis_errors: int = Field(..., description="Redis errors count")
    status: str = Field(..., description="Cache status")
