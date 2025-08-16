"""
Streaming service integrated with existing AlpacaClient patterns
"""

import asyncio
import json
import logging
import websockets
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, AsyncGenerator
from websockets.exceptions import ConnectionClosed, WebSocketException

# Import your existing models and services
from src.app.clients.alpaca_client import AlpacaClient, AlpacaError
from src.app.services.quotes_service import QuotesService
from src.app.schemas.quote import Quote
from src.app.schemas.streaming import (
    StockMessage, StreamingQuote, SubscriptionRequest, AuthRequest,
    TradeMessage, QuoteMessage, BarMessage, StatusMessage,
    SuccessMessage, ErrorMessage, SubscriptionMessage, MessageType,
    StreamingError, StreamingStatus
)

logger = logging.getLogger(__name__)


class AlpacaStreamingClient:
    """
    WebSocket streaming client that follows Alpaca's WebSocket API specification
    """

    def __init__(
        self,
        alpaca_key_id: str,
        alpaca_secret_key: str,
        feed: str = "iex",
        sandbox: bool = False
    ):
        self.alpaca_key_id = alpaca_key_id
        self.alpaca_secret_key = alpaca_secret_key
        self.feed = feed
        self.sandbox = sandbox
        self.websocket = None
        self.connected = False
        self.authenticated = False
        self.subscriptions = set()
        self.last_update = None
        self._connection_lock = asyncio.Lock()

        # Build WebSocket URL according to Alpaca docs
        if sandbox:
            self.ws_url = f"wss://stream.data.sandbox.alpaca.markets/v2/{feed}"
        else:
            self.ws_url = f"wss://stream.data.alpaca.markets/v2/{feed}"

    async def connect(self) -> bool:
        """Connect and authenticate with Alpaca WebSocket"""
        async with self._connection_lock:
            if self.connected and self.websocket and not self.websocket.closed:
                return True

            try:
                logger.info(f"Connecting to Alpaca streaming: {self.ws_url}")

                self.websocket = await websockets.connect(
                    self.ws_url,
                    ping_interval=30,  # Less frequent pings for better performance
                    ping_timeout=5,    # Faster timeout detection
                    close_timeout=5    # Faster cleanup
                )

                # Wait for initial connection message
                message = await asyncio.wait_for(self.websocket.recv(), timeout=10)
                response = json.loads(message)

                if isinstance(response, list) and response[0].get("T") == "success":
                    self.connected = True
                    logger.info("WebSocket connected successfully")

                    # Authenticate immediately
                    if await self._authenticate():
                        return True
                    else:
                        await self.close()
                        return False
                else:
                    logger.error(f"Connection failed: {response}")
                    return False

            except Exception as e:
                logger.error(f"Failed to connect to Alpaca WebSocket: {e}")
                self.connected = False
                return False

    async def _authenticate(self) -> bool:
        """Authenticate using Alpaca's WebSocket auth format"""
        try:
            # Alpaca expects: {"action": "auth", "key": "YOUR_KEY", "secret": "YOUR_SECRET"}
            auth_request = {
                "action": "auth",
                "key": self.alpaca_key_id,
                "secret": self.alpaca_secret_key
            }

            await self.websocket.send(json.dumps(auth_request))

            message = await asyncio.wait_for(self.websocket.recv(), timeout=10)
            response = json.loads(message)

            if isinstance(response, list) and response[0].get("T") == "success":
                self.authenticated = True
                logger.info("WebSocket authenticated successfully")
                return True
            else:
                logger.error(f"Authentication failed: {response}")
                return False

        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False

    async def subscribe(self, symbols: List[str], data_types: List[str] = None) -> bool:
        """Subscribe to symbols using Alpaca's subscription format"""
        if not self.authenticated:
            raise StreamingError("Not authenticated with Alpaca")

        if data_types is None:
            data_types = ["trades", "quotes"]

        try:
            # Alpaca expects: {"action": "subscribe", "trades": ["AAPL"], "quotes": ["AMD"]}
            subscription = {"action": "subscribe"}

            # Set symbols for each requested data type
            for data_type in data_types:
                if data_type in ["trades", "quotes", "bars", "dailyBars", "updatedBars", "statuses", "lulds", "corrections", "cancelErrors"]:
                    subscription[data_type] = symbols

            await self.websocket.send(json.dumps(subscription))

            # Wait for subscription confirmation
            message = await asyncio.wait_for(self.websocket.recv(), timeout=10)
            response = json.loads(message)

            if isinstance(response, list) and response[0].get("T") == "subscription":
                logger.info(f"Successfully subscribed to {symbols} for data types: {data_types}")
                self.subscriptions.update(symbols)
                return True
            else:
                logger.error(f"Subscription failed: {response}")
                return False

        except Exception as e:
            logger.error(f"Subscription error: {e}")
            return False

    async def listen(self) -> AsyncGenerator[StockMessage, None]:
        """Listen for messages and parse them"""
        while self.connected:
            try:
                if not self.websocket:
                    break

                message = await self.websocket.recv()
                data = json.loads(message)

                # Handle both single messages and arrays
                messages = data if isinstance(data, list) else [data]

                for msg in messages:
                    parsed_message = self._parse_message(msg)
                    if parsed_message:
                        self.last_update = datetime.now(timezone.utc)
                        yield parsed_message

            except ConnectionClosed:
                logger.warning("WebSocket connection closed")
                self.connected = False
                break
            except Exception as e:
                logger.error(f"Error receiving message: {e}")
                await asyncio.sleep(1)
                continue

    def _parse_message(self, msg: Dict[str, Any]) -> Optional[StockMessage]:
        """Parse incoming message using Alpaca's message format"""
        try:
            msg_type = msg.get("T")

            if msg_type == MessageType.TRADE:
                return TradeMessage(**msg)
            elif msg_type == MessageType.QUOTE:
                return QuoteMessage(**msg)
            elif msg_type in [MessageType.MINUTE_BAR, MessageType.DAILY_BAR, MessageType.UPDATED_BAR]:
                return BarMessage(**msg)
            elif msg_type == MessageType.STATUS:
                return StatusMessage(**msg)
            elif msg_type == MessageType.SUCCESS:
                return SuccessMessage(**msg)
            elif msg_type == MessageType.ERROR:
                return ErrorMessage(**msg)
            elif msg_type == MessageType.SUBSCRIPTION:
                return SubscriptionMessage(**msg)
            else:
                logger.debug(f"Unhandled message type: {msg_type}")
                return None

        except Exception as e:
            logger.error(f"Failed to parse message {msg}: {e}")
            return None

    def get_status(self) -> StreamingStatus:
        """Get current streaming status"""
        return StreamingStatus(
            status="connected" if self.connected else "disconnected",
            connected=self.connected,
            authenticated=self.authenticated,
            feed=self.feed,
            sandbox=self.sandbox,
            active_symbols=list(self.subscriptions),
            last_update=self.last_update
        )

    async def close(self):
        """Close WebSocket connection"""
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
        self.connected = False
        self.authenticated = False


class StreamingPriceAggregator:
    """
    Aggregates streaming data with snapshot data to create complete PriceQuote objects
    """

    def __init__(self, quotes_service: QuotesService):
        self.quotes_service = quotes_service
        self.streaming_quotes: Dict[str, StreamingQuote] = {}
        self.base_quotes: Dict[str, Quote] = {}
        self._lock = asyncio.Lock()

    async def update_from_message(self, message: StockMessage) -> Optional[Quote]:
        """Update aggregated data from streaming message"""
        if not hasattr(message, 'S'):
            return None

        symbol = message.S
        now = datetime.now(timezone.utc)

        async with self._lock:
            # Initialize streaming quote if needed
            if symbol not in self.streaming_quotes:
                self.streaming_quotes[symbol] = StreamingQuote(
                    symbol=symbol,
                    timestamp=now
                )

            quote = self.streaming_quotes[symbol]
            quote.timestamp = now

            # Update based on message type
            if isinstance(message, TradeMessage):
                quote.last = message.p
                quote.volume = message.s
            elif isinstance(message, QuoteMessage):
                quote.bid = message.bp
                quote.ask = message.ap
            elif isinstance(message, BarMessage):
                quote.last = message.c
                quote.volume = message.v

            # Get base quote if we don't have it
            if symbol not in self.base_quotes:
                try:
                    base_quote = await self.quotes_service.get_price_quote(symbol)
                    self.base_quotes[symbol] = base_quote
                except AlpacaError as e:
                    logger.warning(f"Failed to get base quote for {symbol}: {e}")
                    # Create minimal base quote using Quote schema
                    from src.app.schemas.quote import QuoteData
                    self.base_quotes[symbol] = Quote(
                        symbol=symbol,
                        quote=QuoteData(
                            timestamp=now,
                            ask_exchange="",
                            ask_price=quote.ask or 0.0,
                            ask_size=0,
                            bid_exchange="",
                            bid_price=quote.bid or 0.0,
                            bid_size=0,
                            conditions=[],
                            tape=""
                        )
                    )

            # Create merged quote from streaming data and base quote
            return self._merge_quotes(quote, self.base_quotes[symbol])

    def _merge_quotes(self, streaming: StreamingQuote, base: Quote) -> Quote:
        """Merge streaming data with base quote data"""
        from src.app.schemas.quote import QuoteData
        return Quote(
            symbol=base.symbol,
            quote=QuoteData(
                timestamp=streaming.timestamp,
                ask_exchange="",
                ask_price=streaming.ask or base.quote.ask_price,
                ask_size=base.quote.ask_size,
                bid_exchange="",
                bid_price=streaming.bid or base.quote.bid_price,
                bid_size=base.quote.bid_size,
                conditions=base.quote.conditions,
                tape=base.quote.tape
            )
        )

    async def get_current_quote(self, symbol: str) -> Optional[Quote]:
        """Get current merged quote for symbol"""
        async with self._lock:
            if symbol in self.streaming_quotes and symbol in self.base_quotes:
                return self._merge_quotes(self.streaming_quotes[symbol], self.base_quotes[symbol])
            elif symbol in self.base_quotes:
                return self.base_quotes[symbol]
            return None


class StreamingService:
    """
    Main streaming service that integrates with existing PricesService
    """

    def __init__(self, quotes_service: QuotesService):
        self.quotes_service = quotes_service
        self.client: Optional[AlpacaStreamingClient] = None
        self.aggregator = StreamingPriceAggregator(quotes_service)
        self._lock = asyncio.Lock()

    async def get_client(self) -> AlpacaStreamingClient:
        """Get or create streaming client using AlpacaClient credentials"""
        async with self._lock:
            if self.client is None or not self.client.connected:
                # Extract credentials from existing PricesService's AlpacaClient
                alpaca_client = self.prices_service._get_alpaca_client()
                alpaca_key_id = alpaca_client._alpaca_client.headers.get("APCA-API-KEY-ID")
                alpaca_secret_key = alpaca_client._alpaca_client.headers.get("APCA-API-SECRET-KEY")

                if not alpaca_key_id or not alpaca_secret_key:
                    raise StreamingError("Alpaca credentials not found in PricesService")

                # Determine if sandbox based on base URL
                sandbox = "sandbox" in alpaca_client.alpaca_base_url

                self.client = AlpacaStreamingClient(
                    alpaca_key_id=alpaca_key_id,
                    alpaca_secret_key=alpaca_secret_key,
                    feed=alpaca_client.feed or "iex",
                    sandbox=sandbox
                )

                connected = await self.client.connect()
                if not connected:
                    raise StreamingError("Failed to connect to Alpaca streaming")

            return self.client

    async def stream_prices(self, symbols: List[str]) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream price data for symbols as SSE events"""
        import time
        start_time = time.time()
        message_count = 0
        
        try:
            client = await self.get_client()

            # Subscribe to symbols
            subscribed = await client.subscribe(symbols, ["trades", "quotes", "bars"])
            if not subscribed:
                raise StreamingError("Failed to subscribe to symbols")

            # Listen for messages and convert to events
            async for message in client.listen():
                # Early return for invalid messages
                if not message or not hasattr(message, 'S') or message.S not in symbols:
                    continue
                    
                # Update aggregator and get merged quote
                merged_quote = await self.aggregator.update_from_message(message)

                if merged_quote:
                    # Pre-serialize data for better performance
                    quote_data = merged_quote.model_dump(mode='json')
                    yield {
                        "event": "price",
                        "data": quote_data
                    }

                # Also yield raw message for advanced clients (pre-serialized)
                if not isinstance(message, (SuccessMessage, ErrorMessage, SubscriptionMessage)):
                    raw_data = message.model_dump(mode='json')
                    yield {
                        "event": "raw",
                        "data": raw_data
                    }
                
                # Performance monitoring
                message_count += 1
                if message_count % 100 == 0:  # Log every 100 messages
                    elapsed = time.time() - start_time
                    rate = message_count / elapsed if elapsed > 0 else 0
                    logger.info(f"Streaming performance: {message_count} messages in {elapsed:.2f}s ({rate:.1f} msg/s)")

        except Exception as e:
            logger.error(f"Error in price streaming: {e}")
            yield {
                "event": "error",
                "data": {"error": "streaming_error", "message": str(e)}
            }

    async def get_current_quotes(self, symbols: List[str]) -> Dict[str, Quote]:
        """Get current quotes for symbols (combination of streaming + snapshot)"""
        quotes = {}

        for symbol in symbols:
            # Try to get from aggregator first (real-time data)
            quote = await self.aggregator.get_current_quote(symbol)

            if not quote:
                # REMOVE FALLBACK - let streaming failures surface
                logger.error(f"No real-time quote available for {symbol} - streaming service failed")
                continue

            if quote:
                quotes[symbol] = quote

        return quotes

    async def get_status(self) -> StreamingStatus:
        """Get streaming service status"""
        if self.client:
            return self.client.get_status()
        else:
            return StreamingStatus(
                status="disconnected",
                connected=False,
                authenticated=False,
                feed="iex",  # Default feed
                sandbox=False,  # Default to production
                active_symbols=[]
            )

    async def close(self):
        """Close streaming service"""
        if self.client:
            await self.client.close()


# Factory function to create streaming service from existing QuotesService
def create_streaming_service(quotes_service: QuotesService) -> StreamingService:
    """Create a StreamingService that uses an existing QuotesService for configuration"""
    return StreamingService(quotes_service)


# Global instance management (similar to your existing patterns)
_streaming_service: Optional[StreamingService] = None

async def get_streaming_service() -> StreamingService:
    """Get global streaming service instance using existing QuotesService"""
    global _streaming_service

    if _streaming_service is None:
        # Create QuotesService using same pattern as your existing code
        from src.app.core.config import get_quotes_service
        quotes_service = get_quotes_service()

        _streaming_service = create_streaming_service(quotes_service)

    return _streaming_service