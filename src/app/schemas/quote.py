"""
Quote schema for market data matching Alpaca's API response format
Based on: https://docs.alpaca.markets/reference/stocklatestquotesingle-1
"""

from datetime import datetime
from typing import List, Optional
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
