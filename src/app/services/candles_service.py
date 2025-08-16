from __future__ import annotations

import logging
import httpx
from datetime import datetime, timezone
from typing import Dict, Optional, List, Any

from src.app.clients.alpaca_client import AlpacaClient, AlpacaError
from src.app.schemas.candle import Candle
from src.app.schemas.levels import SRLevel, SRResponse

logger = logging.getLogger(__name__)

class CandlesServiceError(Exception):
    """Custom exception for Candles service-related errors."""
    pass


class CandlesService:
    """
    Service for fetching and processing candle/bar data from Alpaca.

    Handles business logic for historical bars and support/resistance levels.
    """

    def __init__(self, alpaca_client: Optional[AlpacaClient] = None) -> None:
        """
        Initialize the CandlesService.

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
                raise CandlesServiceError(f"Failed to create Alpaca client: {str(e)}") from e

        return self._alpaca_client

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
            raise CandlesServiceError(f"Failed to fetch bars: {str(e)}") from e
        except httpx.ConnectTimeout as e:
            logger.error(f"Connection timeout to Alpaca API for {symbol}: {str(e)}")
            raise CandlesServiceError(f"Connection timeout to Alpaca API: {str(e)}") from e
        except httpx.RequestError as e:
            logger.error(f"Request error to Alpaca API for {symbol}: {str(e)}")
            raise CandlesServiceError(f"Request error to Alpaca API: {str(e)}") from e
        except Exception as e:
            logger.error(f"Unexpected error getting bars for {symbol}: {str(e)}", exc_info=True)
            raise CandlesServiceError(f"Unexpected error: {str(e)}") from e

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
            raise CandlesServiceError(f"Failed to fetch recent bars: {str(e)}") from e
        except Exception as e:
            logger.error(f"Unexpected error getting recent bars for {symbol}: {str(e)}", exc_info=True)
            raise CandlesServiceError(f"Unexpected error: {str(e)}") from e

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
            logger.info(f"Fetching aggregated S/R levels for {symbol} with windows {windows}")
            
            levels = await alpaca_client.get_aggregated_sr(
                symbol=symbol,
                windows=windows,
                max_levels=max_levels,
                swing_window=swing_window,
                tolerance_factor=tolerance_factor
            )
            
            logger.info(f"Successfully retrieved {len(levels.levels)} S/R levels for {symbol}")
            return levels
            
        except AlpacaError as e:
            logger.error(f"Alpaca API error getting S/R levels for {symbol}: {str(e)}")
            raise CandlesServiceError(f"Failed to fetch S/R levels: {str(e)}") from e
        except Exception as e:
            logger.error(f"Unexpected error getting S/R levels for {symbol}: {str(e)}", exc_info=True)
            raise CandlesServiceError(f"Unexpected error: {str(e)}") from e

    async def get_atr(self, symbol: str, period: int = 14, days: int = 30) -> float:
        """
        Get Average True Range (ATR) for a symbol.
        
        Args:
            symbol: Stock symbol
            period: ATR period (default 14)
            days: Number of days to look back
            
        Returns:
            float: ATR value
        """
        try:
            alpaca_client = self._get_alpaca_client()
            logger.info(f"Calculating {period}-period ATR for {symbol} over {days} days")
            
            # First fetch the bars data
            bars = await alpaca_client.get_recent_bars(symbol, days, "1Day")
            
            # Then calculate ATR using the standalone function
            from src.app.clients.alpaca_client import _atr14
            atr = _atr14(bars)
            
            logger.info(f"Successfully calculated ATR for {symbol}: {atr}")
            return atr
            
        except AlpacaError as e:
            logger.error(f"Alpaca API error calculating ATR for {symbol}: {str(e)}")
            raise CandlesServiceError(f"Failed to calculate ATR: {str(e)}") from e
        except Exception as e:
            logger.error(f"Unexpected error calculating ATR for {symbol}: {str(e)}", exc_info=True)
            raise CandlesServiceError(f"Unexpected error: {str(e)}") from e

    # ---- Technical Indicators ----
    
    def _calculate_sma(self, prices: List[float], period: int) -> List[float]:
        """Calculate Simple Moving Average"""
        if len(prices) < period:
            return []
        
        sma_values = []
        for i in range(period - 1, len(prices)):
            sma = sum(prices[i - period + 1:i + 1]) / period
            sma_values.append(sma)
        
        return sma_values
    
    def _calculate_ema(self, prices: List[float], period: int) -> List[float]:
        """Calculate Exponential Moving Average"""
        if len(prices) < period:
            return []
        
        ema_values = []
        multiplier = 2 / (period + 1)
        
        # First EMA is SMA
        first_ema = sum(prices[:period]) / period
        ema_values.append(first_ema)
        
        # Calculate subsequent EMAs
        for i in range(period, len(prices)):
            ema = (prices[i] * multiplier) + (ema_values[-1] * (1 - multiplier))
            ema_values.append(ema)
        
        return ema_values
    
    def _calculate_rsi(self, prices: List[float], period: int = 14) -> List[float]:
        """Calculate Relative Strength Index"""
        if len(prices) < period + 1:
            return []
        
        gains = []
        losses = []
        
        # Calculate price changes
        for i in range(1, len(prices)):
            change = prices[i] - prices[i - 1]
            gains.append(max(change, 0))
            losses.append(max(-change, 0))
        
        rsi_values = []
        
        # Calculate first average gain/loss
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        
        # Calculate first RSI
        if avg_loss == 0:
            rsi = 100
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
        rsi_values.append(rsi)
        
        # Calculate subsequent RSIs
        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            
            if avg_loss == 0:
                rsi = 100
            else:
                rs = avg_gain / avg_loss
                rsi = 100 - (100 / (1 + rs))
            rsi_values.append(rsi)
        
        return rsi_values
    
    def _calculate_macd(self, prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, List[float]]:
        """Calculate MACD (Moving Average Convergence Divergence)"""
        if len(prices) < slow:
            return {"macd": [], "signal": [], "histogram": []}
        
        # Calculate fast and slow EMAs
        fast_ema = self._calculate_ema(prices, fast)
        slow_ema = self._calculate_ema(prices, slow)
        
        # Align EMAs (slow EMA will be shorter)
        start_idx = slow - fast
        macd_line = [fast_ema[i + start_idx] - slow_ema[i] for i in range(len(slow_ema))]
        
        # Calculate signal line (EMA of MACD line)
        signal_line = self._calculate_ema(macd_line, signal)
        
        # Calculate histogram
        histogram = []
        for i in range(len(signal_line)):
            hist = macd_line[i + len(macd_line) - len(signal_line)] - signal_line[i]
            histogram.append(hist)
        
        return {
            "macd": macd_line,
            "signal": signal_line,
            "histogram": histogram
        }
    
    def _calculate_bollinger_bands(self, prices: List[float], period: int = 20, std_dev: float = 2.0) -> Dict[str, List[float]]:
        """Calculate Bollinger Bands"""
        if len(prices) < period:
            return {"upper": [], "middle": [], "lower": []}
        
        # Calculate SMA (middle band)
        middle_band = self._calculate_sma(prices, period)
        
        # Calculate standard deviation
        upper_band = []
        lower_band = []
        
        for i in range(period - 1, len(prices)):
            window = prices[i - period + 1:i + 1]
            mean = sum(window) / period
            variance = sum((x - mean) ** 2 for x in window) / period
            std = variance ** 0.5
            
            upper = mean + (std_dev * std)
            lower = mean - (std_dev * std)
            
            upper_band.append(upper)
            lower_band.append(lower)
        
        return {
            "upper": upper_band,
            "middle": middle_band,
            "lower": lower_band
        }
    
    async def get_technical_indicators(
        self, 
        symbol: str, 
        indicators: List[str] = None,
        period: int = 20,
        days: int = 100
    ) -> Dict[str, Any]:
        """
        Get technical indicators for a symbol.
        
        Args:
            symbol: Stock symbol
            indicators: List of indicators to calculate (default: all)
            period: Period for calculations (default: 20)
            days: Number of days to look back
            
        Returns:
            Dict containing calculated indicators
        """
        if indicators is None:
            indicators = ["sma", "ema", "rsi", "macd", "bbands", "atr"]
        
        try:
            # Get price data
            bars = await self.get_recent_bars(symbol, days, "1Day")
            if not bars:
                raise CandlesServiceError(f"No price data available for {symbol}")
            
            # Extract close prices
            close_prices = [float(bar.close) for bar in bars]
            
            # Calculate indicators
            result = {}
            
            if "sma" in indicators:
                result["sma"] = self._calculate_sma(close_prices, period)
            
            if "ema" in indicators:
                result["ema"] = self._calculate_ema(close_prices, period)
            
            if "rsi" in indicators:
                result["rsi"] = self._calculate_rsi(close_prices, period)
            
            if "macd" in indicators:
                result["macd"] = self._calculate_macd(close_prices)
            
            if "bbands" in indicators:
                result["bbands"] = self._calculate_bollinger_bands(close_prices, period)
            
            if "atr" in indicators:
                result["atr"] = await self.get_atr(symbol, period, days)
            
            logger.info(f"Successfully calculated {len(result)} indicators for {symbol}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to calculate technical indicators for {symbol}: {str(e)}")
            raise CandlesServiceError(f"Failed to calculate indicators: {str(e)}") from e

    # ---- Pivot Points ----
    
    def _calculate_pivot_points(
        self, 
        high: float, 
        low: float, 
        close: float,
        method: str = "standard"
    ) -> Dict[str, float]:
        """
        Calculate pivot points using different methods.
        
        Args:
            high: High price
            low: Low price  
            close: Close price
            method: Calculation method (standard, fibonacci, camarilla, woodie)
            
        Returns:
            Dict containing pivot point levels
        """
        if method == "standard":
            # Standard Pivot Point (Floor Trading)
            pivot = (high + low + close) / 3
            
            r1 = (2 * pivot) - low
            s1 = (2 * pivot) - high
            r2 = pivot + (high - low)
            s2 = pivot - (high - low)
            r3 = high + 2 * (pivot - low)
            s3 = low - 2 * (high - pivot)
            
        elif method == "fibonacci":
            # Fibonacci Pivot Points
            pivot = (high + low + close) / 3
            
            r1 = pivot + 0.382 * (high - low)
            s1 = pivot - 0.382 * (high - low)
            r2 = pivot + 0.618 * (high - low)
            s2 = pivot - 0.618 * (high - low)
            r3 = pivot + 1.000 * (high - low)
            s3 = pivot - 1.000 * (high - low)
            
        elif method == "camarilla":
            # Camarilla Pivot Points
            pivot = (high + low + close) / 3
            
            r1 = close + (high - low) * 1.1/12
            s1 = close - (high - low) * 1.1/12
            r2 = close + (high - low) * 1.1/6
            s2 = close - (high - low) * 1.1/6
            r3 = close + (high - low) * 1.1/4
            s3 = close - (high - low) * 1.1/4
            
        elif method == "woodie":
            # Woodie Pivot Points
            pivot = (high + low + (close * 2)) / 4
            
            r1 = (2 * pivot) - low
            s1 = (2 * pivot) - high
            r2 = pivot + (high - low)
            s2 = pivot - (high - low)
            r3 = high + 2 * (pivot - low)
            s3 = low - 2 * (high - pivot)
            
        else:
            raise ValueError(f"Unknown pivot point method: {method}")
        
        return {
            "pivot": round(pivot, 4),
            "r1": round(r1, 4),
            "r2": round(r2, 4),
            "r3": round(r3, 4),
            "s1": round(s1, 4),
            "s2": round(s2, 4),
            "s3": round(s3, 4)
        }
    
    async def get_pivot_points(
        self, 
        symbol: str,
        timeframe: str = "daily",
        method: str = "standard",
        periods: int = 1
    ) -> Dict[str, Any]:
        """
        Get pivot points for a symbol at different timeframes.
        
        Args:
            symbol: Stock symbol
            timeframe: Timeframe (daily, weekly, monthly)
            method: Pivot point calculation method
            periods: Number of periods to calculate
            
        Returns:
            Dict containing pivot point levels for each period
        """
        try:
            # Map timeframe to Alpaca timeframe and days
            timeframe_mapping = {
                "daily": ("1Day", 30),
                "weekly": ("1Week", 52),  # ~1 year of weekly data
                "monthly": ("1Month", 24)  # ~2 years of monthly data
            }
            
            if timeframe not in timeframe_mapping:
                raise CandlesServiceError(f"Invalid timeframe: {timeframe}. Use: daily, weekly, monthly")
            
            alpaca_timeframe, days = timeframe_mapping[timeframe]
            
            # Get bars for the specified timeframe
            bars = await self.get_recent_bars(symbol, days, alpaca_timeframe)
            if not bars:
                raise CandlesServiceError(f"No {timeframe} data available for {symbol}")
            
            # Calculate pivot points for each period
            pivot_points = {}
            
            for i in range(min(periods, len(bars))):
                bar = bars[-(i + 1)]  # Start from most recent
                
                # Extract OHLC data
                high = float(bar.high)
                low = float(bar.low)
                close = float(bar.close)
                
                # Calculate pivot points
                pivots = self._calculate_pivot_points(high, low, close, method)
                
                # Add timestamp and period info
                period_data = {
                    "timestamp": bar.timestamp,
                    "high": high,
                    "low": low,
                    "close": close,
                    "pivot_levels": pivots,
                    "method": method
                }
                
                if periods == 1:
                    pivot_points = period_data
                else:
                    period_key = f"period_{i + 1}"
                    pivot_points[period_key] = period_data
            
            logger.info(f"Calculated {timeframe} pivot points for {symbol} using {method} method")
            return pivot_points
            
        except Exception as e:
            logger.error(f"Failed to calculate pivot points for {symbol}: {str(e)}")
            raise CandlesServiceError(f"Failed to calculate pivot points: {str(e)}") from e
    
    async def get_multi_timeframe_pivots(
        self, 
        symbol: str,
        methods: List[str] = None
    ) -> Dict[str, Any]:
        """
        Get pivot points for all timeframes (daily, weekly, monthly).
        
        Args:
            symbol: Stock symbol
            methods: List of pivot point methods to calculate
            
        Returns:
            Dict containing pivot points for all timeframes
        """
        if methods is None:
            methods = ["standard", "fibonacci"]
        
        try:
            # Calculate pivot points for all timeframes
            timeframes = ["daily", "weekly", "monthly"]
            results = {}
            
            for timeframe in timeframes:
                timeframe_pivots = {}
                
                for method in methods:
                    try:
                        pivots = await self.get_pivot_points(symbol, timeframe, method)
                        timeframe_pivots[method] = pivots
                    except Exception as e:
                        logger.warning(f"Failed to calculate {method} pivots for {timeframe}: {e}")
                        timeframe_pivots[method] = {"error": str(e)}
                
                results[timeframe] = timeframe_pivots
            
            # Add summary information
            results["summary"] = {
                "symbol": symbol,
                "timeframes": timeframes,
                "methods": methods,
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"Calculated multi-timeframe pivot points for {symbol}")
            return results
            
        except Exception as e:
            logger.error(f"Failed to calculate multi-timeframe pivots for {symbol}: {str(e)}")
            raise CandlesServiceError(f"Failed to calculate multi-timeframe pivots: {str(e)}") from e

    # ---- Pattern Recognition ----
    
    def _detect_doji(self, open_price: float, close_price: float, high: float, low: float, threshold: float = 0.1) -> bool:
        """Detect Doji pattern (open and close are very close)"""
        body_size = abs(close_price - open_price)
        total_range = high - low
        if total_range == 0:
            return False
        return body_size / total_range < threshold
    
    def _detect_hammer(self, open_price: float, close_price: float, high: float, low: float) -> bool:
        """Detect Hammer pattern (long lower shadow, small body)"""
        body_size = abs(close_price - open_price)
        lower_shadow = min(open_price, close_price) - low
        upper_shadow = high - max(open_price, close_price)
        
        # Hammer criteria: long lower shadow, small body, small upper shadow
        return (lower_shadow > 2 * body_size and 
                upper_shadow < body_size and
                body_size > 0)
    
    def _detect_engulfing(self, prev_open: float, prev_close: float, curr_open: float, curr_close: float) -> str:
        """Detect Bullish or Bearish Engulfing pattern"""
        prev_body = abs(prev_close - prev_open)
        curr_body = abs(curr_close - curr_open)
        
        if curr_body <= prev_body:
            return "none"
        
        # Bullish engulfing: current green candle completely engulfs previous red candle
        if (curr_close > curr_open and  # Current is green
            prev_close < prev_open and  # Previous is red
            curr_open < prev_close and  # Current open below previous close
            curr_close > prev_open):    # Current close above previous open
            return "bullish"
        
        # Bearish engulfing: current red candle completely engulfs previous green candle
        if (curr_close < curr_open and  # Current is red
            prev_close > prev_open and  # Previous is green
            curr_open > prev_close and  # Current open above previous close
            curr_close < prev_open):    # Current close below previous open
            return "bearish"
        
        return "none"
    
    async def get_candlestick_patterns(
        self, 
        symbol: str, 
        patterns: List[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Detect candlestick patterns for a symbol.
        
        Args:
            symbol: Stock symbol
            patterns: List of patterns to detect (default: all)
            days: Number of days to look back
            
        Returns:
            Dict containing detected patterns with timestamps
        """
        if patterns is None:
            patterns = ["doji", "hammer", "engulfing"]
        
        try:
            # Get price data
            bars = await self.get_recent_bars(symbol, days, "1Day")
            if len(bars) < 2:
                raise CandlesServiceError(f"Insufficient data for pattern detection: need at least 2 bars")
            
            # Extract OHLC data
            ohlc_data = []
            for bar in bars:
                ohlc_data.append({
                    'timestamp': bar.timestamp,
                    'open': float(bar.open),
                    'high': float(bar.high),
                    'low': float(bar.low),
                    'close': float(bar.close)
                })
            
            # Detect patterns
            detected_patterns = {
                "doji": [],
                "hammer": [],
                "engulfing": []
            }
            
            for i, candle in enumerate(ohlc_data):
                # Doji detection
                if "doji" in patterns:
                    if self._detect_doji(candle['open'], candle['close'], candle['high'], candle['low']):
                        detected_patterns["doji"].append({
                            "timestamp": candle['timestamp'],
                            "position": i,
                            "confidence": "high"
                        })
                
                # Hammer detection
                if "hammer" in patterns:
                    if self._detect_hammer(candle['open'], candle['close'], candle['high'], candle['low']):
                        detected_patterns["hammer"].append({
                            "timestamp": candle['timestamp'],
                            "position": i,
                            "confidence": "high"
                        })
                
                # Engulfing detection (needs previous candle)
                if "engulfing" in patterns and i > 0:
                    prev_candle = ohlc_data[i - 1]
                    engulfing_type = self._detect_engulfing(
                        prev_candle['open'], prev_candle['close'],
                        candle['open'], candle['close']
                    )
                    if engulfing_type != "none":
                        detected_patterns["engulfing"].append({
                            "timestamp": candle['timestamp'],
                            "position": i,
                            "type": engulfing_type,
                            "confidence": "high"
                        })
            
            # Filter out empty patterns
            result = {k: v for k, v in detected_patterns.items() if v}
            
            logger.info(f"Detected {sum(len(v) for v in result.values())} patterns for {symbol}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to detect patterns for {symbol}: {str(e)}")
            raise CandlesServiceError(f"Failed to detect patterns: {str(e)}") from e

# Factory function to create candles service from existing PricesService
def create_candles_service(prices_service) -> CandlesService:
    """Create a CandlesService that uses an existing PricesService for configuration"""
    # Extract the AlpacaClient from the PricesService
    alpaca_client = prices_service._alpaca_client if hasattr(prices_service, '_alpaca_client') else None
    return CandlesService(alpaca_client)


# Global instance management (similar to your existing patterns)
_candles_service: Optional[CandlesService] = None

async def get_candles_service() -> CandlesService:
    """Get global candles service instance using existing PricesService"""
    global _candles_service

    if _candles_service is None:
        # Create PricesService using same pattern as your existing code
        from src.app.core.config import get_alpaca
        prices_service = get_alpaca()

        _candles_service = create_candles_service(prices_service)

    return _candles_service
