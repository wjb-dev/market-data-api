"""
Real-time news streaming service using Alpaca's WebSocket API.
Provides live news updates for trading and analysis.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import AsyncGenerator, Dict, Any, Optional, List
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

logger = logging.getLogger(__name__)


class NewsStreamingError(Exception):
    """Custom exception for news streaming errors."""
    pass


class NewsStreamingService:
    """
    Service for streaming real-time news from Alpaca WebSocket API.
    
    Based on Alpaca's real-time news documentation:
    https://docs.alpaca.markets/docs/streaming-real-time-news
    """
    
    def __init__(
        self, 
        api_key: str,
        api_secret: str,
        sandbox: bool = False
    ):
        """
        Initialize the news streaming service.
        
        Args:
            api_key: Alpaca API key
            api_secret: Alpaca API secret
            sandbox: Use sandbox environment if True
        """
        self.api_key = api_key
        self.api_secret = api_secret
        
        # WebSocket URLs based on Alpaca documentation
        if sandbox:
            self.ws_url = "wss://stream.data.sandbox.alpaca.markets/v1beta1/news"
        else:
            self.ws_url = "wss://stream.data.alpaca.markets/v1beta1/news"
        
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.connected = False
        self.subscribed = False
        
    async def connect(self) -> bool:
        """
        Connect to Alpaca news WebSocket stream.
        
        Returns:
            bool: True if connection successful
        """
        try:
            # Connect to WebSocket
            self.websocket = await websockets.connect(
                self.ws_url,
                extra_headers={
                    "APCA-API-KEY-ID": self.api_key,
                    "APCA-API-SECRET-KEY": self.api_secret
                }
            )
            
            # Wait for connection confirmation
            response = await self.websocket.recv()
            response_data = json.loads(response)
            
            if response_data.get("T") == "success" and response_data.get("msg") == "connected":
                logger.info("Successfully connected to Alpaca news WebSocket")
                self.connected = True
                return True
            else:
                logger.error(f"Unexpected connection response: {response_data}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect to news WebSocket: {str(e)}")
            self.connected = False
            return False
    
    async def authenticate(self) -> bool:
        """
        Authenticate with Alpaca WebSocket.
        
        Returns:
            bool: True if authentication successful
        """
        if not self.connected or not self.websocket:
            logger.error("Cannot authenticate - not connected")
            return False
            
        try:
            # Wait for authentication message
            response = await self.websocket.recv()
            response_data = json.loads(response)
            
            if response_data.get("T") == "success" and response_data.get("msg") == "authenticated":
                logger.info("Successfully authenticated with Alpaca news WebSocket")
                return True
            else:
                logger.error(f"Authentication failed: {response_data}")
                return False
                
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return False
    
    async def subscribe(self, symbols: Optional[List[str]] = None) -> bool:
        """
        Subscribe to news stream.
        
        Args:
            symbols: List of symbols to subscribe to, or None for all news
            
        Returns:
            bool: True if subscription successful
        """
        if not self.connected or not self.websocket:
            logger.error("Cannot subscribe - not connected")
            return False
            
        try:
            # Prepare subscription message
            if symbols:
                # Subscribe to specific symbols
                subscription_msg = {
                    "action": "subscribe",
                    "news": symbols
                }
            else:
                # Subscribe to all news
                subscription_msg = {
                    "action": "subscribe",
                    "news": ["*"]
                }
            
            # Send subscription
            await self.websocket.send(json.dumps(subscription_msg))
            
            # Wait for subscription confirmation
            response = await self.websocket.recv()
            response_data = json.loads(response)
            
            if response_data.get("T") == "subscription":
                logger.info(f"Successfully subscribed to news stream: {symbols or 'all'}")
                self.subscribed = True
                return True
            else:
                logger.error(f"Subscription failed: {response_data}")
                return False
                
        except Exception as e:
            logger.error(f"Subscription error: {str(e)}")
            return False
    
    async def stream_news(self, symbols: Optional[List[str]] = None) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream real-time news from Alpaca.
        
        Args:
            symbols: List of symbols to filter by, or None for all
            
        Yields:
            Dict: News article data
        """
        try:
            # Connect and authenticate
            if not await self.connect():
                raise NewsStreamingError("Failed to connect to news WebSocket")
                
            if not await self.authenticate():
                raise NewsStreamingError("Failed to authenticate with news WebSocket")
                
            # Subscribe to news stream
            if not await self.subscribe(symbols):
                raise NewsStreamingError("Failed to subscribe to news stream")
            
            logger.info("Starting news stream...")
            
            # Stream news messages
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    
                    # Check if it's a news message
                    if data.get("T") == "n":
                        # Transform to our schema format
                        news_item = self._transform_news_message(data)
                        
                        # Filter by symbols if specified
                        if symbols and not self._matches_symbols(news_item, symbols):
                            continue
                        
                        yield {
                            "event": "news",
                            "data": news_item,
                            "timestamp": datetime.now().isoformat()
                        }
                    
                    elif data.get("T") == "error":
                        logger.error(f"WebSocket error: {data}")
                        yield {
                            "event": "error",
                            "data": data,
                            "timestamp": datetime.now().isoformat()
                        }
                        
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse WebSocket message: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Error processing news message: {e}")
                    continue
                    
        except ConnectionClosed:
            logger.info("News WebSocket connection closed")
        except WebSocketException as e:
            logger.error(f"WebSocket error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in news stream: {e}")
        finally:
            await self.close()
    
    def _transform_news_message(self, message: Dict) -> Dict[str, Any]:
        """
        Transform Alpaca WebSocket news message to our schema.
        
        Args:
            message: Raw WebSocket message
            
        Returns:
            Dict: Transformed news item
        """
        # Map Alpaca fields to our schema based on documentation
        return {
            "id": str(message.get("id", "")),
            "headline": message.get("headline", ""),
            "summary": message.get("summary", ""),
            "author": message.get("author", "Unknown"),
            "created_at": message.get("created_at", ""),
            "updated_at": message.get("updated_at", ""),
            "content": message.get("content", ""),
            "url": message.get("url", ""),
            "symbols": message.get("symbols", []),
            "source": message.get("source", "benzinga"),
            "type": "news"
        }
    
    def _matches_symbols(self, news_item: Dict, symbols: List[str]) -> bool:
        """
        Check if news item matches any of the specified symbols.
        
        Args:
            news_item: News item data
            symbols: List of symbols to match
            
        Returns:
            bool: True if news item matches any symbol
        """
        news_symbols = news_item.get("symbols", [])
        return any(symbol in news_symbols for symbol in symbols)
    
    async def close(self):
        """Close the WebSocket connection."""
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
        
        self.connected = False
        self.subscribed = False
        logger.info("News WebSocket connection closed")


# Factory function for dependency injection
def create_news_streaming_service(
    api_key: str,
    api_secret: str,
    sandbox: bool = False
) -> NewsStreamingService:
    """Create a NewsStreamingService instance."""
    return NewsStreamingService(api_key, api_secret, sandbox)


# Global instance management
_news_streaming_service: Optional[NewsStreamingService] = None

async def get_news_streaming_service() -> NewsStreamingService:
    """Get global news streaming service instance."""
    global _news_streaming_service
    
    if _news_streaming_service is None:
        from src.app.core.config import get_settings
        settings = get_settings()
        
        _news_streaming_service = create_news_streaming_service(
            api_key=settings.alpaca_key_id,
            api_secret=settings.alpaca_secret_key,
            sandbox=settings.alpaca_data_base_url != "https://data.alpaca.markets/v2"
        )
    
    return _news_streaming_service
