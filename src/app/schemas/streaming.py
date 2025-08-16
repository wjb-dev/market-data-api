"""
Streaming schemas integrated with existing PriceQuote model
"""

from datetime import datetime, timezone
from typing import List, Optional, Union, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field

from src.app.schemas.quote import Quote


class MessageType(str, Enum):
    """WebSocket message types from Alpaca"""
    TRADE = "t"
    QUOTE = "q"
    MINUTE_BAR = "b"
    DAILY_BAR = "d"
    UPDATED_BAR = "u"
    CORRECTION = "c"
    CANCEL_ERROR = "x"
    LULD = "l"
    STATUS = "s"
    IMBALANCE = "i"
    SUCCESS = "success"
    ERROR = "error"
    SUBSCRIPTION = "subscription"


class BaseStockMessage(BaseModel):
    """Base class for all stock market messages"""
    T: MessageType = Field(..., description="Message type")
    S: str = Field(..., description="Symbol")
    t: str = Field(..., description="Timestamp")
    z: str = Field(..., description="Tape")


class TradeMessage(BaseStockMessage):
    """Trade message from Alpaca WebSocket - matches their schema exactly"""
    T: MessageType = Field(MessageType.TRADE, description="Message type")
    i: int = Field(..., description="Trade ID")
    x: str = Field(..., description="Exchange code")
    p: float = Field(..., description="Trade price")
    s: int = Field(..., description="Trade size")
    c: List[str] = Field(..., description="Trade conditions")


class QuoteMessage(BaseStockMessage):
    """Quote message from Alpaca WebSocket - matches their schema exactly"""
    T: MessageType = Field(MessageType.QUOTE, description="Message type")
    ax: str = Field(..., description="Ask exchange code")
    ap: float = Field(..., description="Ask price")
    as_: int = Field(..., alias="as", description="Ask size in round lots")
    bx: str = Field(..., description="Bid exchange code")
    bp: float = Field(..., description="Bid price")
    bs: int = Field(..., description="Bid size in round lots")
    c: List[str] = Field(..., description="Quote conditions")


class BarMessage(BaseStockMessage):
    """Bar message (minute, daily, or updated bars) - matches Alpaca's schema"""
    T: MessageType = Field(..., description="Message type: b, d, or u")
    o: float = Field(..., description="Open price")
    h: float = Field(..., description="High price")
    l: float = Field(..., description="Low price")
    c: float = Field(..., description="Close price")
    v: int = Field(..., description="Volume")
    vw: float = Field(..., description="Volume-weighted average price")
    n: int = Field(..., description="Number of trades")


class StatusMessage(BaseStockMessage):
    """Trading status message - matches Alpaca's schema"""
    T: MessageType = Field(MessageType.STATUS, description="Message type")
    sc: str = Field(..., description="Status code")
    sm: str = Field(..., description="Status message")
    rc: str = Field(..., description="Reason code")
    rm: str = Field(..., description="Reason message")


class ImbalanceMessage(BaseStockMessage):
    """Order imbalance message - matches Alpaca's schema"""
    T: MessageType = Field(MessageType.IMBALANCE, description="Message type")
    p: float = Field(..., description="Price")


# Control messages
class SuccessMessage(BaseModel):
    """Success response message"""
    T: MessageType = Field(MessageType.SUCCESS, description="Message type")
    msg: str = Field(..., description="Success message")


class ErrorMessage(BaseModel):
    """Error response message"""
    T: MessageType = Field(MessageType.ERROR, description="Message type")
    msg: str = Field(..., description="Error message")
    code: Optional[int] = Field(None, description="Error code")


class SubscriptionMessage(BaseModel):
    """Subscription confirmation message - matches Alpaca's response format"""
    T: MessageType = Field(MessageType.SUBSCRIPTION, description="Message type")
    trades: Optional[List[str]] = Field(default=None)
    quotes: Optional[List[str]] = Field(default=None)
    bars: Optional[List[str]] = Field(default=None)
    dailyBars: Optional[List[str]] = Field(default=None)
    updatedBars: Optional[List[str]] = Field(default=None)
    statuses: Optional[List[str]] = Field(default=None)
    lulds: Optional[List[str]] = Field(default=None)
    corrections: Optional[List[str]] = Field(default=None)
    cancelErrors: Optional[List[str]] = Field(default=None)


# Union type for all possible message types
StockMessage = Union[
    TradeMessage, QuoteMessage, BarMessage, StatusMessage, ImbalanceMessage,
    SuccessMessage, ErrorMessage, SubscriptionMessage
]


# Request/Response models
class AuthRequest(BaseModel):
    """Authentication request - matches Alpaca's expected format"""
    action: str = Field("auth", description="Action type")
    key: str = Field(..., description="Alpaca API key")
    secret: str = Field(..., description="Alpaca API secret")


class SubscriptionRequest(BaseModel):
    """Subscription request - matches Alpaca's expected format"""
    action: str = Field("subscribe", description="Action type")
    trades: Optional[List[str]] = Field(default=None)
    quotes: Optional[List[str]] = Field(default=None)
    bars: Optional[List[str]] = Field(default=None)
    dailyBars: Optional[List[str]] = Field(default=None)
    updatedBars: Optional[List[str]] = Field(default=None)
    statuses: Optional[List[str]] = Field(default=None)
    lulds: Optional[List[str]] = Field(default=None)
    corrections: Optional[List[str]] = Field(default=None)
    cancelErrors: Optional[List[str]] = Field(default=None)


class StreamingQuote(BaseModel):
    """Aggregated streaming quote combining real-time data"""
    symbol: str = Field(..., description="Stock symbol")
    last: Optional[float] = Field(None, description="Last trade price")
    bid: Optional[float] = Field(None, description="Best bid price")
    ask: Optional[float] = Field(None, description="Best ask price")
    volume: Optional[int] = Field(None, description="Volume")
    timestamp: datetime = Field(..., description="Quote timestamp")
    
    def to_quote(self) -> Quote:
        """Convert to Quote format"""
        from src.app.schemas.quote import QuoteData
        return Quote(
            symbol=self.symbol,
            quote=QuoteData(
                timestamp=self.timestamp,
                ask_exchange="",  # Default empty for now
                ask_price=self.ask or 0.0,
                ask_size=0,  # Default for now
                bid_exchange="",  # Default empty for now
                bid_price=self.bid or 0.0,
                bid_size=0,  # Default for now
                conditions=[],  # Default empty for now
                tape=""  # Default empty for now
            )
        )


class StreamingStatus(BaseModel):
    """Streaming service status"""
    status: str = Field(..., description="Connection status")
    connected: bool = Field(..., description="WebSocket connected")
    authenticated: bool = Field(..., description="Authentication status")
    feed: str = Field(..., description="Data feed type")
    sandbox: bool = Field(..., description="Sandbox mode")
    active_symbols: List[str] = Field(default_factory=list, description="Subscribed symbols")
    last_update: Optional[datetime] = Field(None, description="Last message timestamp")


class StreamingErrorResponse(BaseModel):
    """Error response for streaming endpoints"""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")


class StreamingError(Exception):
    """Custom exception for streaming service errors"""
    pass