from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from src.app.core.http_client import get_http_client
from src.app.schemas.quote import Quote, QuoteData

logger = logging.getLogger(__name__)


class AlphaVantageError(Exception):
    """Custom exception for Alpha Vantage API errors."""
    pass


class AlphaVantageClient:
    """
    Client for Alpha Vantage API.
    
    Documentation: https://www.alphavantage.co/documentation/#latestprice
    
    This client provides a fallback for when Alpaca returns stale data.
    """
    
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://www.alphavantage.co/query",
        timeout: float = 8.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._http_client = httpx.AsyncClient(
            timeout=timeout,
            headers={
                "User-Agent": "MarketDataAPI/1.0",
            },
        )

    async def aclose(self) -> None:
        """Close the HTTP client."""
        await self._http_client.aclose()

    async def get_latest_quote(self, symbol: str) -> Quote:
        """
        Get the latest quote for a symbol using Alpha Vantage's latest price endpoint.
        
        Args:
            symbol: Stock symbol (e.g., 'AAPL', 'MSFT')
            
        Returns:
            Quote: Latest quote data transformed to match our schema
            
        Raises:
            AlphaVantageError: If the API request fails or returns an error
        """
        try:
            # Alpha Vantage latest price endpoint
            params = {
                "function": "GLOBAL_QUOTE",
                "symbol": symbol.upper(),
                "apikey": self.api_key,
                "datatype": "json"
            }
            
            logger.info(f"Fetching quote for {symbol} from Alpha Vantage")
            r = await self._http_client.get(self.base_url, params=params)
            
            if r.is_error:
                logger.error(f"Alpha Vantage HTTP {r.status_code}: {r.text}")
                raise AlphaVantageError(f"Alpha Vantage HTTP {r.status_code}: {r.text}")
            
            data = r.json()
            
            # Check for Alpha Vantage error responses
            if "Error Message" in data:
                raise AlphaVantageError(f"Alpha Vantage error: {data['Error Message']}")
            
            if "Note" in data:
                # Rate limit or API key issue
                raise AlphaVantageError(f"Alpha Vantage note: {data['Note']}")
            
            # Extract quote data from Alpha Vantage response
            quote_data = data.get("Global Quote", {})
            if not quote_data:
                raise AlphaVantageError(f"No quote data returned for {symbol}")
            
            logger.info(f"Alpha Vantage response for {symbol}: {data}")
            
            # Transform Alpha Vantage data to our QuoteData schema
            # Alpha Vantage returns: "01. symbol", "02. open", "03. high", "04. low", "05. price", "06. volume", "07. latest trading day", "08. previous close", "09. change", "10. change percent"
            current_price = float(quote_data.get("05. price", 0))
            previous_close = float(quote_data.get("08. previous close", 0))
            change = float(quote_data.get("09. change", 0))
            change_percent = quote_data.get("10. change percent", "0%").rstrip("%")
            volume = int(quote_data.get("06. volume", 0))
            latest_trading_day = quote_data.get("07. latest trading day", "")
            
            # Calculate bid/ask from current price (Alpha Vantage doesn't provide bid/ask)
            # Use a small spread for estimation
            spread_pct = 0.01  # 1 basis point spread
            bid_price = current_price * (1 - spread_pct/2)
            ask_price = current_price * (1 + spread_pct/2)
            
            # Create timestamp from latest trading day
            timestamp = self._parse_trading_day(latest_trading_day)
            
            # Transform to our QuoteData schema
            quote = QuoteData(
                timestamp=timestamp,
                ask_exchange="ALPHA_VANTAGE",  # Placeholder since Alpha Vantage doesn't provide exchange info
                ask_price=round(ask_price, 4),
                ask_size=volume,  # Use volume as size estimate
                bid_exchange="ALPHA_VANTAGE",
                bid_price=round(bid_price, 4),
                bid_size=volume,
                conditions=[],  # Alpha Vantage doesn't provide conditions
                tape="",  # Alpha Vantage doesn't provide tape info
                sip_timestamp=None,
                participant_timestamp=None,
                trade_id=None,  # Alpha Vantage doesn't provide trade ID
                quote_id=None,  # Alpha Vantage doesn't provide quote ID
                spread=round(ask_price - bid_price, 4),
                spread_pct=round(spread_pct * 100, 3),
                mid_price=round(current_price, 4)
            )
            
            return Quote(
                symbol=symbol.upper(),
                quote=quote,
                status="success (alpha_vantage_fallback)",
                timestamp=datetime.now(timezone.utc)
            )
            
        except httpx.TimeoutException:
            logger.error(f"Timeout fetching quote for {symbol} from Alpha Vantage")
            raise AlphaVantageError(f"Timeout fetching quote for {symbol}")
        except httpx.RequestError as e:
            logger.error(f"Request error fetching quote for {symbol} from Alpha Vantage: {e}")
            raise AlphaVantageError(f"Request error: {e}")
        except ValueError as e:
            logger.error(f"Data parsing error for {symbol} from Alpha Vantage: {e}")
            raise AlphaVantageError(f"Data parsing error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error fetching quote for {symbol} from Alpha Vantage: {e}")
            raise AlphaVantageError(f"Unexpected error: {e}")

    def _parse_trading_day(self, trading_day: str) -> datetime:
        """
        Parse Alpha Vantage trading day format to datetime.
        
        Alpha Vantage returns dates in format: "2024-01-15"
        """
        try:
            # Parse the date and set to end of trading day (4 PM ET)
            dt = datetime.strptime(trading_day, "%Y-%m-%d")
            # Set to 4 PM ET (end of trading day)
            dt = dt.replace(hour=16, minute=0, second=0, microsecond=0)
            # Assume ET timezone for now
            return dt
        except ValueError:
            logger.warning(f"Could not parse trading day: {trading_day}, using current time")
            return datetime.now(timezone.utc)

    async def health_check(self) -> bool:
        """
        Check if the Alpha Vantage API is accessible.
        
        Returns:
            bool: True if API is accessible, False otherwise
        """
        try:
            # Try to fetch a simple endpoint
            params = {
                "function": "TIME_SERIES_INTRADAY",
                "symbol": "AAPL",
                "interval": "1min",
                "apikey": self.api_key,
                "outputsize": "compact"
            }
            
            r = await self._http_client.get(self.base_url, params=params)
            return not r.is_error
        except Exception:
            return False
