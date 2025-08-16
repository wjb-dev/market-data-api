from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, Optional, List

from src.app.clients.alpaca_client import AlpacaClient, AlpacaError
from src.app.schemas.candles import Candle
from src.app.schemas.levels import SRLevel, SRResponse
from src.app.schemas.quote import Quote

logger = logging.getLogger(__name__)

class PricesServiceError(Exception):
    """Custom exception for Prices service-related errors."""
    pass


class PricesService:
    """
    Service for fetching and processing market data from Alpaca.

    Handles business logic for price quotes, bars, and support/resistance levels.
    """

    def __init__(self, alpaca_client: Optional[AlpacaClient] = None) -> None:
        """
        Initialize the PricesService.

        Args:
            alpaca_client: Optional AlpacaClient instance.
                          If None, will create one using the factory.
        """
        self._alpaca_client = alpaca_client
        self._client_owned = alpaca_client is None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self) -> None:
        """Close resources if we own them."""
        if self._client_owned and self._alpaca_client:
            await self._alpaca_client.aclose()
            self._alpaca_client = None

    def _get_alpaca_client(self) -> AlpacaClient:
        """Get or create Alpaca client instance."""
        if self._alpaca_client is None:
            try:
                from src.app.core.config import get_alpaca_client
                self._alpaca_client = get_alpaca_client()
            except Exception as e:
                raise PricesServiceError(f"Failed to create Alpaca client: {str(e)}") from e

        return self._alpaca_client

    async def get_price_quote(self, symbol: str) -> Quote:
        """
        Get current price quote for a symbol.
        
        Args:
            symbol: Stock symbol (e.g., AAPL, SPY)
            
        Returns:
            PriceQuote: Current price quote
            
        Raises:
            PricesServiceError: If the request fails
        """
        try:
            alpaca_client = self._get_alpaca_client()
            logger.info(f"Fetching price quote for {symbol}")
            
            quote = await alpaca_client.get_price_quote(symbol)
            logger.info(f"Successfully retrieved price quote for {symbol}")
            return quote
            
        except AlpacaError as e:
            logger.error(f"Alpaca API error getting price quote for {symbol}: {str(e)}")
            raise PricesServiceError(f"Failed to fetch price quote: {str(e)}") from e
        except Exception as e:
            logger.error(f"Unexpected error getting price quote for {symbol}: {str(e)}", exc_info=True)
            raise PricesServiceError(f"Unexpected error: {str(e)}") from e

    async def get_daily_change_percent(self, symbol: str) -> float:
        """
        Get daily percent change for a symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            float: Daily percent change
        """
        try:
            quote = await self.get_price_quote(symbol)
            return float(quote.changePercent or 0.0)
        except Exception as e:
            logger.error(f"Failed to get daily change for {symbol}: {str(e)}")
            return 0.0

    async def get_bars(
            self,
            symbol: str,
            timeframe: str = "1Day",
            start: Optional[datetime] = None,
            end: Optional[datetime] = None,
            limit: int = 1000,
            adjustment: str = "split",
    ) -> List[Candle]:
        """
        Get historical bars for a symbol.
        
        Args:
            symbol: Stock symbol
            timeframe: Bar timeframe (e.g., "1Day", "1Min")
            start: Start time
            end: End time
            limit: Maximum number of bars
            adjustment: Price adjustment (split, dividend, all)
            
        Returns:
            List[Candle]: List of candle bars
        """
        try:
            alpaca_client = self._get_alpaca_client()
            logger.info(f"Fetching {timeframe} bars for {symbol}")
            
            bars = await alpaca_client.get_bars(
                symbol=symbol,
                timeframe=timeframe,
                start=start,
                end=end,
                limit=limit,
                adjustment=adjustment
            )
            
            logger.info(f"Successfully retrieved {len(bars)} bars for {symbol}")
            return bars
            
        except AlpacaError as e:
            logger.error(f"Alpaca API error getting bars for {symbol}: {str(e)}")
            raise PricesServiceError(f"Failed to fetch bars: {str(e)}") from e
        except Exception as e:
            logger.error(f"Unexpected error getting bars for {symbol}: {str(e)}", exc_info=True)
            raise PricesServiceError(f"Unexpected error: {str(e)}") from e

    async def get_recent_bars(self, symbol: str, days: int, timeframe: str = "1Day") -> List[Candle]:
        """
        Get recent bars for a symbol.
        
        Args:
            symbol: Stock symbol
            days: Number of days to look back
            timeframe: Bar timeframe
            
        Returns:
            List[Candle]: List of recent candle bars
        """
        try:
            alpaca_client = self._get_alpaca_client()
            logger.info(f"Fetching recent {days} day bars for {symbol}")
            
            bars = await alpaca_client.get_recent_bars(symbol, days, timeframe)
            
            logger.info(f"Successfully retrieved {len(bars)} recent bars for {symbol}")
            return bars
            
        except AlpacaError as e:
            logger.error(f"Alpaca API error getting recent bars for {symbol}: {str(e)}")
            raise PricesServiceError(f"Failed to fetch recent bars: {str(e)}") from e
        except Exception as e:
            logger.error(f"Unexpected error getting recent bars for {symbol}: {str(e)}", exc_info=True)
            raise PricesServiceError(f"Unexpected error: {str(e)}") from e

    async def get_aggregated_sr(
            self,
            symbol: str,
            windows: List[int] = [7, 30, 90],
            max_levels: int = 10,
            swing_window: int = 2,
            tolerance_factor: float = 0.5,
    ) -> SRResponse:
        """
        Get aggregated support/resistance levels for a symbol.
        
        Args:
            symbol: Stock symbol
            windows: List of lookback windows in days
            max_levels: Maximum number of levels to return
            swing_window: Swing detection window size
            tolerance_factor: Clustering tolerance factor
            
        Returns:
            SRResponse: Support/resistance levels
        """
        try:
            alpaca_client = self._get_alpaca_client()
            logger.info(f"Fetching aggregated S/R levels for {symbol}")
            
            sr_response = await alpaca_client.get_aggregated_sr(
                symbol=symbol,
                windows=windows,
                max_levels=max_levels,
                swing_window=swing_window,
                tolerance_factor=tolerance_factor
            )
            
            logger.info(f"Successfully retrieved {len(sr_response.levels)} S/R levels for {symbol}")
            return sr_response
            
        except AlpacaError as e:
            logger.error(f"Alpaca API error getting S/R levels for {symbol}: {str(e)}")
            raise PricesServiceError(f"Failed to fetch S/R levels: {str(e)}") from e
        except Exception as e:
            logger.error(f"Unexpected error getting S/R levels for {symbol}: {str(e)}", exc_info=True)
            raise PricesServiceError(f"Unexpected error: {str(e)}") from e

    def health_check(self) -> Dict:
        """
        Check service health.

        Returns:
            Dict: Health status information
        """
        try:
            client = self._get_alpaca_client()
            # Check if client is properly initialized
            alpaca_healthy = hasattr(client, '_alpaca_client') and client._alpaca_client is not None
        except Exception:
            alpaca_healthy = False

        return {
            "service": "prices",
            "status": "healthy" if alpaca_healthy else "degraded",
            "alpaca_client": "connected" if alpaca_healthy else "disconnected",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
