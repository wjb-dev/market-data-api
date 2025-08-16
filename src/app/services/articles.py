"""
Articles service for fetching and processing news articles from Alpaca.
Handles business logic for article retrieval and data transformation.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple, Any
import re

from src.app.clients.alpaca_client import AlpacaClient, AlpacaError
from src.app.schemas.content import ContentCollection, ContentItem

logger = logging.getLogger(__name__)


class ArticlesServiceError(Exception):
    """Custom exception for Articles service-related errors."""
    pass


class NewsCache:
    """High-performance news caching system with TTL and hit rate tracking."""
    
    def __init__(self, ttl_seconds: int = 300):  # 5 minutes default TTL
        self.cache: Dict[str, Tuple[Any, datetime]] = {}
        self.ttl = timedelta(seconds=ttl_seconds)
        self._lock = asyncio.Lock()
        self._total_requests = 0
        self._cache_hits = 0
        self._cache_misses = 0
        self._evictions = 0
    
    async def get(self, key: str) -> Optional[Any]:
        """Get cached news data with hit rate tracking."""
        async with self._lock:
            self._total_requests += 1
            
            if key in self.cache:
                data, timestamp = self.cache[key]
                if datetime.now() - timestamp < self.ttl:
                    self._cache_hits += 1
                    return data
                else:
                    # Expired, remove it
                    del self.cache[key]
                    self._evictions += 1
            
            self._cache_misses += 1
            return None
    
    async def set(self, key: str, value: Any):
        """Cache news data with timestamp."""
        async with self._lock:
            self.cache[key] = (value, datetime.now())
    
    async def invalidate(self, key: str):
        """Invalidate specific cache entry."""
        async with self._lock:
            if key in self.cache:
                del self.cache[key]
    
    async def clear(self):
        """Clear all cached data."""
        async with self._lock:
            self.cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        total = self._total_requests
        hit_rate = (self._cache_hits / total * 100) if total > 0 else 0
        
        return {
            "total_requests": total,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "hit_rate_percent": round(hit_rate, 2),
            "cache_size": len(self.cache),
            "evictions": self._evictions,
            "ttl_seconds": self.ttl.total_seconds()
        }


class ArticlesService:
    """Service for fetching and managing news articles."""
    
    def __init__(self, alpaca_client: Optional[AlpacaClient] = None) -> None:
        """
        Initialize the ArticlesService.

        Args:
            alpaca_client: Optional AlpacaClient instance.
                          If None, will create one using the factory.
        """
        self._alpaca_client = alpaca_client
        self._client_owned = alpaca_client is None
        
        # Initialize high-performance caching
        self._news_cache = NewsCache(ttl_seconds=300)  # 5 minutes TTL
        self._symbol_cache = NewsCache(ttl_seconds=600)  # 10 minutes TTL for symbol-specific
        
        # Performance tracking
        self._total_requests = 0
        self._successful_requests = 0
        self._failed_requests = 0
        self._total_response_time = 0.0
        self._request_times: List[float] = []
    
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self) -> None:
        """Close resources if we own them."""
        if self._client_owned and self._alpaca_client:
            # Note: AlpacaClient doesn't have a close method in your current implementation
            # So we'll just clear the reference
            self._alpaca_client = None

    def _get_alpaca_client(self) -> AlpacaClient:
        """Get or create Alpaca client instance."""
        if self._alpaca_client is None:
            try:
                # Use the existing factory pattern from your codebase
                from src.app.core.config import get_alpaca_client
                self._alpaca_client = get_alpaca_client()
            except Exception as e:
                raise ArticlesServiceError(f"Failed to create Alpaca client: {str(e)}") from e

        return self._alpaca_client

    def _record_request(self, start_time: datetime, success: bool):
        """Record request performance metrics."""
        response_time = (datetime.now() - start_time).total_seconds()
        self._total_requests += 1
        self._total_response_time += response_time
        self._request_times.append(response_time)
        
        if success:
            self._successful_requests += 1
        else:
            self._failed_requests += 1
    
    def _clean_html_content(self, html_content: str) -> str:
        """
        Convert HTML content to clean, readable plain text.
        
        Args:
            html_content: Raw HTML content from Alpaca
            
        Returns:
            str: Clean plain text content
        """
        if not html_content:
            return ""
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', html_content)
        
        # Clean up common HTML entities
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        text = text.replace('&#39;', "'")
        text = text.replace('&nbsp;', ' ')
        
        # Clean up extra whitespace and newlines
        text = re.sub(r'\n\s*\n', '\n\n', text)  # Multiple newlines to double newlines
        text = re.sub(r' +', ' ', text)  # Multiple spaces to single space
        text = text.strip()
        
        return text

    async def get_articles_by_symbol(self, symbol: str, **kwargs) -> ContentCollection:
        """
        Get articles for a specific symbol with caching.
        
        Args:
            symbol: Stock symbol
            **kwargs: Additional query parameters
            
        Returns:
            ContentCollection: Articles for the symbol
        """
        start_time = datetime.now()
        
        try:
            # Generate cache key for symbol-specific query
            cache_key = f"symbol_news:{symbol.upper()}:{hash(str(kwargs))}"
            
            # Check cache first
            cached_result = await self._symbol_cache.get(cache_key)
            if cached_result:
                logger.info(f"Cache HIT for symbol {symbol}")
                self._record_request(start_time, success=True)
                return cached_result
            
            # Build query parameters
            query_params = {"symbols": symbol, **kwargs}
            result = await self.get_articles_from_alpaca(query_params)
            
            # Cache the result
            await self._symbol_cache.set(cache_key, result)
            
            self._record_request(start_time, success=True)
            return result
            
        except Exception as e:
            self._record_request(start_time, success=False)
            raise

    async def get_articles_from_alpaca(self, params: Dict) -> ContentCollection:
        """
        Get articles from Alpaca news API.
        
        Args:
            params: Query parameters for news search
            
        Returns:
            ContentCollection: Collection of news articles
        """
        try:
            logger.info(f"Starting Alpaca news fetch with params: {params}")
            
            # Get Alpaca client
            alpaca_client = self._get_alpaca_client()
            logger.info(f"Got Alpaca client: {type(alpaca_client)}")
            
            # Clean and validate parameters
            cleaned_params = self._clean_query_params(params)
            logger.info(f"Cleaned params: {cleaned_params}")
            
            # Fetch news from Alpaca
            logger.info("Calling _fetch_news_from_alpaca...")
            articles_response = await self._fetch_news_from_alpaca(alpaca_client, cleaned_params)
            logger.info(f"Got response from Alpaca: {type(articles_response)}")
            logger.info(f"Response keys: {list(articles_response.keys()) if isinstance(articles_response, dict) else 'Not a dict'}")
            
            # Transform response to our schema
            logger.info("Starting response transformation...")
            transformed_collection = self._transform_response(articles_response)
            logger.info(f"Transformation complete. Items count: {len(transformed_collection.items)}")
            
            return transformed_collection
            
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            raise ArticlesServiceError(f"Unexpected error: {str(e)}") from e

    async def _fetch_news_from_alpaca(self, alpaca_client: AlpacaClient, params: Dict) -> Dict:
        """
        Fetch news from Alpaca API.
        
        Args:
            alpaca_client: Alpaca client instance
            params: Query parameters
            
        Returns:
            Dict: Raw API response
        """
        try:
            # Use the real Alpaca news API
            logger.info("Fetching real news data from Alpaca API")
            
            # Map our parameters to Alpaca API parameters
            alpaca_params = {
                "limit": params.get("limit", 50),
                "include_content": params.get("include_content", False),
                "exclude_contentless": params.get("exclude_contentless", True),
                "sort": params.get("sort", "desc")
            }
            
            if params.get("symbols"):
                alpaca_params["symbols"] = params["symbols"]
            if params.get("start"):
                alpaca_params["start"] = params["start"]
            if params.get("end"):
                alpaca_params["end"] = params["end"]
            
            logger.info(f"Calling alpaca_client.get_news with params: {alpaca_params}")
            
            # Call the real Alpaca news endpoint
            news_response = await alpaca_client.get_news(**alpaca_params)
            
            logger.info(f"get_news call completed successfully")
            logger.info(f"Response type: {type(news_response)}")
            logger.info(f"Response content: {news_response}")
            
            if isinstance(news_response, dict):
                logger.info(f"Response keys: {list(news_response.keys())}")
                logger.info(f"News items count: {len(news_response.get('news', []))}")
                if news_response.get('news'):
                    logger.info(f"First news item: {news_response['news'][0]}")
            else:
                logger.warning(f"Unexpected response type: {type(news_response)}")
            
            logger.info(f"Successfully fetched {len(news_response.get('news', []))} articles from Alpaca")
            return news_response
            
        except Exception as e:
            logger.error(f"Failed to fetch news from Alpaca: {str(e)}")
            logger.error(f"Exception type: {type(e)}")
            logger.error(f"Exception details: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            raise ArticlesServiceError(f"Alpaca news API failed: {str(e)}")

    def _clean_query_params(self, params: Dict) -> Dict:
        """
        Clean and validate query parameters.

        Args:
            params: Raw query parameters

        Returns:
            Dict: Cleaned parameters
        """
        cleaned = {}

        for key, value in params.items():
            if value is not None:
                if key == "symbols" and isinstance(value, str):
                    # Clean up symbols
                    symbols = [s.strip().upper() for s in value.split(",") if s.strip()]
                    cleaned[key] = ",".join(symbols)
                elif key == "limit":
                    # Ensure limit is within bounds
                    cleaned[key] = max(1, min(int(value), 1000))
                elif key == "sort":
                    # Validate sort order
                    cleaned[key] = value if value in ["asc", "desc"] else "desc"
                else:
                    cleaned[key] = value

        return cleaned

    def _transform_response(self, response: Dict) -> ContentCollection:
        """
        Transform Alpaca news response to our schema.
        
        Args:
            response: Raw API response from Alpaca
            
        Returns:
            ContentCollection: Transformed news collection
        """
        try:
            news_items = response.get("news", [])
            
            logger.info(f"Raw Alpaca news response: {response}")
            logger.info(f"News items count: {len(news_items)}")
            if news_items:
                logger.info(f"First news item sample: {news_items[0]}")
            
            if not isinstance(news_items, list):
                logger.warning(f"Unexpected news format from Alpaca: {type(news_items)}")
                news_items = []

            transformed_items = []
            for i, item in enumerate(news_items):
                try:
                    transformed_item = self._transform_news_item(item)
                    if transformed_item:
                        transformed_items.append(transformed_item)
                except Exception as e:
                    logger.warning(f"Failed to transform news item {i}: {str(e)}")
                    continue

            logger.info(f"Transformed {len(transformed_items)} out of {len(news_items)} news items")
            
            return ContentCollection(
                items=transformed_items,
                next_page_token=response.get("next_page_token")
            )
            
        except Exception as e:
            logger.error(f"Failed to transform response: {str(e)}")
            raise ArticlesServiceError(f"Failed to transform response: {str(e)}")

    def _transform_news_item(self, item: Dict) -> Optional[ContentItem]:
        """
        Transform a single news item to ContentItem schema.
        
        Args:
            item: Raw news item from Alpaca API
            
        Returns:
            ContentItem: Transformed news item or None if invalid
        """
        try:
            # Map Alpaca fields to our schema with proper type conversion
            transformed = {
                "id": str(item.get("id", "")),  # Convert int to str
                "headline": item.get("headline", ""),
                "author": item.get("author", "Unknown"),
                "content": self._clean_html_content(item.get("content", "")), # Clean HTML content
                "created_at": self._parse_datetime(item.get("created_at")),
                "updated_at": self._parse_datetime(item.get("updated_at")),
                "summary": item.get("summary", ""),
                "url": str(item.get("url", "")),  # Ensure it's a string for HttpUrl validation
                "symbols": item.get("symbols", []),
                "source": "benzinga",
                "type": "news"
            }
            
            # Validate required fields
            if not transformed["id"] or not transformed["headline"]:
                return None
            
            # Check if datetime parsing failed
            if transformed["created_at"] is None:
                return None
                
            if transformed["updated_at"] is None:
                return None
            
            # Create and validate ContentItem
            content_item = ContentItem(**transformed)
            
            return content_item
            
        except Exception as e:
            logger.debug(f"Failed to transform news item {item.get('id', 'unknown')}: {str(e)}")
            import traceback
            logger.debug(f"Full traceback: {traceback.format_exc()}")
            return None

    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """
        Parse datetime string to datetime object.
        
        Args:
            dt_str: ISO format datetime string
            
        Returns:
            datetime: Parsed datetime or None if invalid
        """
        if not dt_str:
            return None
            
        try:
            parsed = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            return parsed
        except Exception as e:
            logger.warning(f"Failed to parse datetime '{dt_str}': {str(e)}")
            return None

    def health_check(self) -> Dict:
        """
        Check service health.

        Returns:
            Dict: Health status information
        """
        try:
            client = self._get_alpaca_client()
            # Check if client is accessible
            alpaca_healthy = client is not None
        except Exception:
            alpaca_healthy = False

        return {
            "service": "articles",
            "status": "healthy" if alpaca_healthy else "degraded",
            "alpaca_client": "connected" if alpaca_healthy else "disconnected",
            "timestamp": datetime.now().isoformat(),
        }
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics."""
        total_requests = self._total_requests
        avg_response_time = (self._total_response_time / total_requests) if total_requests > 0 else 0.0
        
        # Calculate percentiles
        sorted_times = sorted(self._request_times)
        p95_response_time = sorted_times[int(len(sorted_times) * 0.95)] if sorted_times else 0.0
        p99_response_time = sorted_times[int(len(sorted_times) * 0.99)] if sorted_times else 0.0
        
        return {
            "total_requests": total_requests,
            "successful_requests": self._successful_requests,
            "failed_requests": self._failed_requests,
            "success_rate_percent": round((self._successful_requests / total_requests * 100) if total_requests > 0 else 0, 2),
            "avg_response_time_ms": round(avg_response_time * 1000, 2),
            "p95_response_time_ms": round(p95_response_time * 1000, 2),
            "p99_response_time_ms": round(p99_response_time * 1000, 2),
            "news_cache_stats": self._news_cache.get_stats(),
            "symbol_cache_stats": self._symbol_cache.get_stats(),
            "timestamp": datetime.now().isoformat()
        }
    
    def _generate_cache_key(self, params: Dict) -> str:
        """Generate deterministic cache key from query parameters."""
        # Sort parameters for consistent cache keys
        sorted_params = sorted(params.items())
        key_parts = [f"{k}:{v}" for k, v in sorted_params if v is not None]
        return f"news:{':'.join(key_parts)}"
    
    async def invalidate_cache(self, pattern: str = None):
        """Invalidate cache entries matching pattern."""
        if pattern:
            # Invalidate specific pattern
            keys_to_remove = [k for k in self._news_cache.cache.keys() if pattern in k]
            for key in keys_to_remove:
                await self._news_cache.invalidate(key)
            logger.info(f"Invalidated {len(keys_to_remove)} cache entries matching '{pattern}'")
        else:
            # Clear all caches
            await self._news_cache.clear()
            await self._symbol_cache.clear()
            logger.info("All news caches cleared")
    
    async def get_cache_status(self) -> Dict[str, Any]:
        """Get comprehensive cache status and performance."""
        return {
            "news_cache": self._news_cache.get_stats(),
            "symbol_cache": self._symbol_cache.get_stats(),
            "performance": self.get_performance_stats(),
            "timestamp": datetime.now().isoformat()
        }


# Factory function for dependency injection
def create_articles_service(alpaca_client=None) -> ArticlesService:
    """Create an ArticlesService instance."""
    return ArticlesService(alpaca_client=alpaca_client)


# Global instance management
_articles_service: Optional[ArticlesService] = None

async def get_articles_service() -> ArticlesService:
    """Get global articles service instance."""
    global _articles_service
    
    if _articles_service is None:
        from src.app.core.config import get_alpaca_client
        alpaca_client = get_alpaca_client()
        _articles_service = create_articles_service(alpaca_client)
    
    return _articles_service
