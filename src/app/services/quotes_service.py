from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, Optional, List, Any

from src.app.clients.alpaca_client import AlpacaClient, AlpacaError
from src.app.schemas.quote import Quote

logger = logging.getLogger(__name__)

class QuotesServiceError(Exception):
    """Custom exception for Quotes service-related errors."""
    pass


class QuotesService:
    """
    Service for fetching and processing quote data from Alpaca.

    Handles business logic for price quotes and daily changes.
    """

    def __init__(self, alpaca_client: Optional[AlpacaClient] = None) -> None:
        """
        Initialize the QuotesService.

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
                raise QuotesServiceError(f"Failed to create Alpaca client: {str(e)}") from e

        return self._alpaca_client

    async def get_price_quote(self, symbol: str) -> Quote:
        """
        Get current price quote for a symbol.
        
        Args:
            symbol: Stock symbol (e.g., AAPL, SPY)
            
        Returns:
            Quote: Current price quote
            
        Raises:
            QuotesServiceError: If the request fails
        """
        try:
            alpaca_client = self._get_alpaca_client()
            logger.info(f"Fetching price quote for {symbol}")
            
            quote = await alpaca_client.get_price_quote(symbol)
            logger.info(f"Successfully retrieved price quote for {symbol}")
            return quote
            
        except AlpacaError as e:
            logger.error(f"Alpaca API error getting price quote for {symbol}: {str(e)}")
            raise QuotesServiceError(f"Failed to fetch price quote: {str(e)}") from e
        except Exception as e:
            logger.error(f"Unexpected error getting price quote for {symbol}: {str(e)}", exc_info=True)
            raise QuotesServiceError(f"Unexpected error: {str(e)}") from e

    async def get_daily_change_percent(self, symbol: str) -> float:
        """
        Get daily percent change for a symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            float: Daily percent change
        """
        try:
            alpaca_client = self._get_alpaca_client()
            logger.info(f"Calculating daily change for {symbol}")
            
            # Use the Alpaca client's proper calculation method
            change_percent = await alpaca_client.get_daily_change_percent(symbol)
            
            logger.info(f"Daily change for {symbol}: {change_percent}%")
            return change_percent
            
        except Exception as e:
            logger.error(f"Failed to get daily change for {symbol}: {str(e)}")
            return 0.0

    async def get_period_change_percent(self, symbol: str, timeframe: str = "ytd") -> float:
        """
        Get percentage change for a symbol over different time periods.
        
        Args:
            symbol: Stock symbol
            timeframe: Time period - "ytd", "quarterly", or "monthly"
            
        Returns:
            float: Percentage change over the specified period
        """
        try:
            alpaca_client = self._get_alpaca_client()
            logger.info(f"Calculating {timeframe.upper()} change for {symbol}")
            
            # Calculate days to look back based on timeframe
            from datetime import datetime, timedelta
            today = datetime.now()
            
            if timeframe == "ytd":
                # Year-to-date: from January 1st of current year
                start_date = datetime(today.year, 1, 1)
                days = (today - start_date).days
                period_name = "YTD"
            elif timeframe == "quarterly":
                # Quarterly: last 3 months (90 days)
                start_date = today - timedelta(days=90)
                days = 90
                period_name = "Quarterly"
            elif timeframe == "monthly":
                # Monthly: last 30 days
                start_date = today - timedelta(days=30)
                days = 30
                period_name = "Monthly"
            else:
                # Default to YTD
                start_date = datetime(today.year, 1, 1)
                days = (today - start_date).days
                period_name = "YTD"
            
            # Get current price from latest quote
            current_quote = await alpaca_client.get_price_quote(symbol)
            current_price = (current_quote.quote.ask_price + current_quote.quote.bid_price) / 2
            
            if current_price <= 0:
                logger.warning(f"Current price is 0 for {symbol}, cannot calculate {period_name} change")
                return 0.0
            
            # Get historical bars for the period
            bars = await alpaca_client.get_recent_bars(symbol, days=days, timeframe="1Day")
            if len(bars) < 2:
                logger.warning(f"Insufficient bars for {symbol} to calculate {period_name} change")
                return 0.0
            
            # Find the starting price (first bar in the period)
            start_price = float(bars[0].close)
            
            if start_price <= 0:
                logger.warning(f"Starting price is 0 for {symbol}, cannot calculate {period_name} change")
                return 0.0
            
            # Calculate percentage change
            change_percent = ((current_price - start_price) / start_price) * 100
            
            logger.debug(f"{period_name} change for {symbol}: current={current_price}, start={start_price}, change={change_percent:.2f}%")
            return round(change_percent, 2)
            
        except Exception as e:
            logger.error(f"Failed to calculate {timeframe} change for {symbol}: {str(e)}")
            return 0.0

    async def get_batch_quotes(self, symbols: List[str]) -> Dict[str, Quote]:
        """
        Get quotes for multiple symbols in parallel.
        
        Args:
            symbols: List of stock symbols
            
        Returns:
            Dict[str, Quote]: Map of symbol to quote
        """
        try:
            alpaca_client = self._get_alpaca_client()
            logger.info(f"Fetching batch quotes for {len(symbols)} symbols")
            
            # Parallel processing for multiple symbols
            import asyncio
            tasks = [self.get_price_quote(symbol) for symbol in symbols]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Build response with error handling
            quotes = {}
            for symbol, result in zip(symbols, results):
                if isinstance(result, Exception):
                    logger.warning(f"Failed to fetch quote for {symbol}: {result}")
                    quotes[symbol] = None  # Will be handled by router
                else:
                    quotes[symbol] = result
            
            logger.info(f"Successfully retrieved batch quotes for {len(symbols)} symbols")
            return quotes
            
        except Exception as e:
            logger.error(f"Failed to get batch quotes: {str(e)}")
            raise QuotesServiceError(f"Failed to fetch batch quotes: {str(e)}") from e

    async def get_quote_history(self, symbol: str, days: int = 30) -> List[Quote]:
        """
        Get historical quotes for a symbol (placeholder for future implementation).
        
        Args:
            symbol: Stock symbol
            days: Number of days to look back
            
        Returns:
            List[Quote]: List of historical quotes
        """
        # This is a stub for future implementation
        logger.info(f"Quote history endpoint called for {symbol} ({days} days) - not yet implemented")
        return []  # Return empty list for now

    # ---- Market Intelligence & Sentiment Analysis ----
    
    def _calculate_volume_momentum(self, current_volume: int, avg_volume: int) -> Dict[str, Any]:
        """Calculate volume momentum indicators"""
        if avg_volume == 0:
            return {"momentum": "neutral", "ratio": 1.0, "strength": "unknown"}
        
        volume_ratio = current_volume / avg_volume
        
        # Determine momentum strength
        if volume_ratio >= 3.0:
            strength = "very_high"
            momentum = "bullish" if current_volume > avg_volume else "bearish"
        elif volume_ratio >= 2.0:
            strength = "high"
            momentum = "bullish" if current_volume > avg_volume else "bearish"
        elif volume_ratio >= 1.5:
            strength = "moderate"
            momentum = "bullish" if current_volume > avg_volume else "bearish"
        elif volume_ratio >= 0.7:
            strength = "low"
            momentum = "neutral"
        else:
            strength = "very_low"
            momentum = "neutral"
        
        return {
            "momentum": momentum,
            "ratio": round(volume_ratio, 2),
            "strength": strength,
            "current_volume": current_volume,
            "avg_volume": avg_volume
        }
    
    def _calculate_bid_ask_imbalance(self, bid_size: int, ask_size: int) -> Dict[str, Any]:
        """Calculate bid-ask size imbalance for sentiment analysis"""
        total_size = bid_size + ask_size
        if total_size == 0:
            return {"imbalance": "neutral", "ratio": 1.0, "sentiment": "unknown"}
        
        bid_ratio = bid_size / total_size
        ask_ratio = ask_size / total_size
        
        # Determine imbalance direction
        if bid_ratio > 0.6:
            imbalance = "bid_heavy"
            sentiment = "bullish"
        elif ask_ratio > 0.6:
            imbalance = "ask_heavy"
            sentiment = "bearish"
        else:
            imbalance = "balanced"
            sentiment = "neutral"
        
        return {
            "imbalance": imbalance,
            "bid_ratio": round(bid_ratio, 3),
            "ask_ratio": round(ask_ratio, 3),
            "sentiment": sentiment,
            "total_size": total_size
        }
    
    def _calculate_price_momentum(self, current_price: float, prev_price: float, open_price: float) -> Dict[str, Any]:
        """Calculate price momentum indicators"""
        if prev_price == 0:
            return {"momentum": "neutral", "change_pct": 0.0, "intraday": "neutral"}
        
        # Overall change
        change_pct = ((current_price - prev_price) / prev_price) * 100
        
        # Intraday change
        intraday_change = ((current_price - open_price) / open_price) * 100
        
        # Determine momentum
        if change_pct > 2.0:
            momentum = "strong_bullish"
        elif change_pct > 0.5:
            momentum = "bullish"
        elif change_pct > -0.5:
            momentum = "neutral"
        elif change_pct > -2.0:
            momentum = "bearish"
        else:
            momentum = "strong_bearish"
        
        # Intraday sentiment
        if intraday_change > 1.0:
            intraday = "bullish"
        elif intraday_change > -1.0:
            intraday = "neutral"
        else:
            intraday = "bearish"
        
        return {
            "momentum": momentum,
            "change_pct": round(change_pct, 2),
            "intraday": intraday,
            "intraday_change": round(intraday_change, 2),
            "current_price": current_price,
            "prev_price": prev_price,
            "open_price": open_price
        }
    
    async def get_market_intelligence(
        self, 
        symbol: str,
        include_volume: bool = True,
        include_imbalance: bool = True,
        include_momentum: bool = True
    ) -> Dict[str, Any]:
        """
        Get comprehensive market intelligence for a symbol.
        
        Args:
            symbol: Stock symbol
            include_volume: Include volume analysis
            include_imbalance: Include bid-ask imbalance
            include_momentum: Include price momentum
            
        Returns:
            Dict containing market intelligence data
        """
        try:
            # Get current quote
            current_quote = await self.get_price_quote(symbol)
            if not current_quote:
                raise QuotesServiceError(f"No quote data available for {symbol}")
            
            # Get daily change for comparison
            daily_change = await self.get_daily_change_percent(symbol)
            
            # Extract quote data
            quote_data = current_quote.quote
            
            # Validate quote data to prevent division by zero
            if quote_data.ask_price <= 0 or quote_data.bid_price <= 0:
                logger.warning(f"Invalid quote data for {symbol}: ask_price={quote_data.ask_price}, bid_price={quote_data.bid_price}")
                raise QuotesServiceError(f"Invalid quote data: ask_price or bid_price is zero or negative")
            
            # Initialize result with safe calculations
            spread = quote_data.ask_price - quote_data.bid_price
            spread_pct = (spread / quote_data.ask_price) * 100 if quote_data.ask_price > 0 else 0
            
            intelligence = {
                "symbol": symbol,
                "timestamp": quote_data.timestamp,
                "current_price": quote_data.ask_price,  # Use ask as current price
                "bid_price": quote_data.bid_price,
                "ask_price": quote_data.ask_price,
                "spread": round(spread, 4),
                "spread_pct": round(spread_pct, 3)
            }
            
            # Volume analysis
            if include_volume:
                # For now, we'll use placeholder volume data
                # In production, this would come from real-time volume feeds
                current_volume = quote_data.ask_size + quote_data.bid_size
                avg_volume = current_volume * 2  # Placeholder - would be real avg volume
                
                volume_analysis = self._calculate_volume_momentum(current_volume, avg_volume)
                intelligence["volume_analysis"] = volume_analysis
            
            # Bid-ask imbalance
            if include_imbalance:
                imbalance_analysis = self._calculate_bid_ask_imbalance(
                    quote_data.bid_size, quote_data.ask_size
                )
                intelligence["market_imbalance"] = imbalance_analysis
            
            # Price momentum
            if include_momentum:
                # Use daily change as previous price for momentum calculation
                # Prevent division by zero when daily_change is -100%
                if daily_change == -100:
                    prev_price = quote_data.ask_price * 2  # If price dropped 100%, prev was double
                else:
                    prev_price = quote_data.ask_price / (1 + daily_change / 100)
                
                open_price = prev_price  # Placeholder - would be real open price
                
                momentum_analysis = self._calculate_price_momentum(
                    quote_data.ask_price, prev_price, open_price
                )
                intelligence["price_momentum"] = momentum_analysis
            
            # Overall sentiment score
            sentiment_score = 0
            sentiment_factors = []
            
            if include_volume and "volume_analysis" in intelligence:
                if intelligence["volume_analysis"]["momentum"] == "bullish":
                    sentiment_score += 1
                    sentiment_factors.append("high_volume")
                elif intelligence["volume_analysis"]["momentum"] == "bearish":
                    sentiment_score -= 1
                    sentiment_factors.append("low_volume")
            
            if include_imbalance and "market_imbalance" in intelligence:
                if intelligence["market_imbalance"]["sentiment"] == "bullish":
                    sentiment_score += 1
                    sentiment_factors.append("bid_heavy")
                elif intelligence["market_imbalance"]["sentiment"] == "bearish":
                    sentiment_score -= 1
                    sentiment_factors.append("ask_heavy")
            
            if include_momentum and "price_momentum" in intelligence:
                if intelligence["price_momentum"]["momentum"] in ["bullish", "strong_bullish"]:
                    sentiment_score += 1
                    sentiment_factors.append("price_momentum")
                elif intelligence["price_momentum"]["momentum"] in ["bearish", "strong_bearish"]:
                    sentiment_score -= 1
                    sentiment_factors.append("price_decline")
            
            # Determine overall sentiment
            if sentiment_score >= 2:
                overall_sentiment = "strong_bullish"
            elif sentiment_score == 1:
                overall_sentiment = "bullish"
            elif sentiment_score == 0:
                overall_sentiment = "neutral"
            elif sentiment_score == -1:
                overall_sentiment = "bearish"
            else:
                overall_sentiment = "strong_bearish"
            
            intelligence["sentiment"] = {
                "overall": overall_sentiment,
                "score": sentiment_score,
                "factors": sentiment_factors,
                "confidence": "high" if abs(sentiment_score) >= 2 else "medium"
            }
            
            logger.info(f"Generated market intelligence for {symbol}: {overall_sentiment}")
            return intelligence
            
        except Exception as e:
            logger.error(f"Failed to generate market intelligence for {symbol}: {str(e)}")
            raise QuotesServiceError(f"Failed to generate intelligence: {str(e)}") from e

    async def get_comparative_analysis(
        self, 
        symbol: str, 
        benchmarks: List[str] = None,
        metrics: List[str] = None,
        timeframe: str = "ytd"  # ytd, quarterly, monthly
    ) -> Dict[str, Any]:
        """
        Get comparative analysis vs benchmarks and market indices.
        
        Args:
            symbol: Stock symbol to analyze
            benchmarks: List of benchmark symbols (default: SPY, QQQ, IWM)
            metrics: List of metrics to compare (default: all)
            timeframe: Time period for comparison - "ytd", "quarterly", or "monthly"
            
        Returns:
            Dict containing comparative analysis
        """
        if benchmarks is None:
            benchmarks = ["SPY", "QQQ", "IWM"]  # S&P 500, Nasdaq, Russell 2000
        
        if metrics is None:
            metrics = ["price_change", "relative_strength", "correlation", "volatility"]
        
        # Validate timeframe
        valid_timeframes = ["ytd", "quarterly", "monthly"]
        if timeframe not in valid_timeframes:
            timeframe = "ytd"  # Default to YTD if invalid
            logger.warning(f"Invalid timeframe '{timeframe}', defaulting to 'ytd'")
        
        logger.info(f"Generating {timeframe.upper()} comparative analysis for {symbol}")
        
        try:
            # Get current quote for main symbol
            main_quote = await self.get_price_quote(symbol)
            if not main_quote:
                raise QuotesServiceError(f"No quote data available for {symbol}")
            
            # Get quotes for benchmarks
            benchmark_quotes = await self.get_batch_quotes(benchmarks)
            
            # Calculate comparative metrics
            analysis = {
                "symbol": symbol,
                "timestamp": main_quote.quote.timestamp,
                "timeframe": timeframe,
                "benchmarks": benchmarks,
                "comparison": {}
            }
            
            # Use mid price for more accurate comparison (average of bid/ask)
            main_price = (main_quote.quote.ask_price + main_quote.quote.bid_price) / 2
            main_change = await self.get_period_change_percent(symbol, timeframe)
            
            # Debug logging for period changes
            logger.info(f"{timeframe.upper()} changes for {symbol}: main_symbol={main_change}%")
            
            for benchmark in benchmarks:
                if benchmark in benchmark_quotes and benchmark_quotes[benchmark]:
                    benchmark_quote = benchmark_quotes[benchmark]
                    
                    # Check if it's a Quote object (successful quote)
                    if hasattr(benchmark_quote, 'quote') and hasattr(benchmark_quote, 'status') and benchmark_quote.status == 'success':
                        # Extract benchmark data from Quote object
                        benchmark_price = (benchmark_quote.quote.ask_price + benchmark_quote.quote.bid_price) / 2
                        benchmark_change = await self.get_period_change_percent(benchmark, timeframe)
                        logger.info(f"  {benchmark}: price={benchmark_price}, change={benchmark_change}%")
                        
                        if benchmark_price > 0:
                            # Price change comparison
                            if "price_change" in metrics:
                                price_diff = main_change - benchmark_change
                                outperforming = price_diff > 0
                                
                                logger.info(f"  {benchmark} comparison: {symbol}={main_change}%, {benchmark}={benchmark_change}%, diff={price_diff}%, outperforming={outperforming}")
                                
                                analysis["comparison"][benchmark] = {
                                    "price_change": {
                                        "symbol": round(main_change, 2),
                                        "benchmark": round(benchmark_change, 2),
                                        "difference": round(price_diff, 2),
                                        "outperformance": outperforming,
                                        "outperformance_pct": round(abs(price_diff), 2)
                                    }
                                }
                            
                            # Relative strength (price performance ratio, not absolute price ratio)
                            if "relative_strength" in metrics:
                                # Calculate relative strength based on performance, not absolute price
                                if benchmark_change != 0:
                                    relative_strength = main_change / benchmark_change
                                    # Normalize to -1 to 1 scale where positive = outperforming
                                    if relative_strength > 0:
                                        strength_score = min(relative_strength, 2.0)  # Cap at 2x
                                    else:
                                        strength_score = max(relative_strength, -2.0)  # Cap at -2x
                                    
                                    if strength_score > 1.5:
                                        strength = "very_strong"
                                    elif strength_score > 1.2:
                                        strength = "strong"
                                    elif strength_score > 0.8:
                                        strength = "neutral"
                                    elif strength_score > 0.5:
                                        strength = "weak"
                                    else:
                                        strength = "very_weak"
                                else:
                                    relative_strength = 0
                                    strength = "neutral"
                                
                                analysis["comparison"][benchmark]["relative_strength"] = {
                                    "ratio": round(relative_strength, 4),
                                    "strength": strength,
                                    "strength_score": round(strength_score, 3)
                                }
                            
                            # Volatility comparison (calculate actual price volatility)
                            if "volatility" in metrics:
                                try:
                                    # Get recent price data for volatility calculation
                                    symbol_volatility = await self._calculate_price_volatility(symbol)
                                    benchmark_volatility = await self._calculate_price_volatility(benchmark)
                                    
                                    # Compare volatility levels
                                    if abs(symbol_volatility - benchmark_volatility) < 0.5:
                                        comparison = "similar"
                                    elif symbol_volatility > benchmark_volatility:
                                        comparison = "higher"
                                    else:
                                        comparison = "lower"
                                    
                                    analysis["comparison"][benchmark]["volatility"] = {
                                        "symbol_volatility": round(symbol_volatility, 2),
                                        "benchmark_volatility": round(benchmark_volatility, 2),
                                        "comparison": comparison,
                                        "difference": round(symbol_volatility - benchmark_volatility, 2)
                                    }
                                except Exception as e:
                                    logger.warning(f"Could not calculate volatility for {benchmark}: {e}")
                                    analysis["comparison"][benchmark]["volatility"] = {
                                        "error": "Volatility calculation failed",
                                        "status": "unavailable"
                                    }
                        else:
                            # Handle case where benchmark price is 0 or invalid
                            logger.warning(f"Invalid benchmark price for {benchmark}: {benchmark_price}")
                            analysis["comparison"][benchmark] = {
                                "error": f"Invalid benchmark price: {benchmark_price}",
                                "status": "invalid_price"
                            }
                    
                    # Check if it's a dict format (alternative data structure)
                    elif isinstance(benchmark_quote, dict) and "error" not in benchmark_quote:
                        # Handle dict format
                        quote_data = benchmark_quote.get('quote', {})
                        benchmark_price = (quote_data.get('ask_price', 0) + quote_data.get('bid_price', 0)) / 2
                        benchmark_change = 0.0  # Would need to implement for benchmarks
                        logger.info(f"  {benchmark}: price={benchmark_price}, change={benchmark_change}% (dict format)")
                        
                        if benchmark_price > 0:
                            # Process dict format data (same logic as above)
                            # ... (similar processing for dict format)
                            pass
                        else:
                            analysis["comparison"][benchmark] = {
                                "error": f"Invalid benchmark price: {benchmark_price}",
                                "status": "invalid_price"
                            }
                    
                    else:
                        # Handle other error cases
                        logger.warning(f"Benchmark {benchmark} has error in data: {benchmark_quote}")
                        analysis["comparison"][benchmark] = {
                            "error": "Data format error",
                            "status": "format_error"
                        }
                else:
                    # Handle missing benchmark data - this is the key fix!
                    logger.warning(f"Benchmark {benchmark} quote failed or is missing")
                    analysis["comparison"][benchmark] = {
                        "error": "Quote fetch failed",
                        "status": "unavailable"
                    }
            
            # Overall performance summary
            outperforming_count = sum(
                1 for b in analysis["comparison"].values() 
                if "price_change" in b and b["price_change"]["outperformance"]
            )
            
            # Debug logging to understand the performance calculation
            logger.info(f"Performance summary for {symbol}:")
            for benchmark, data in analysis["comparison"].items():
                if "price_change" in data:
                    logger.info(f"  {benchmark}: symbol={data['price_change']['symbol']}%, benchmark={data['price_change']['benchmark']}%, diff={data['price_change']['difference']}%, outperforming={data['price_change']['outperformance']}")
            
            logger.info(f"  Total benchmarks: {len(benchmarks)}, Outperforming: {outperforming_count}, Underperforming: {len(benchmarks) - outperforming_count}")
            
            # More nuanced overall performance calculation
            if outperforming_count == len(benchmarks):
                overall_performance = "outperforming_all"
            elif outperforming_count > len(benchmarks) / 2:
                overall_performance = "outperforming_majority"
            elif outperforming_count == 0:
                overall_performance = "underperforming_all"
            elif outperforming_count < len(benchmarks) / 2:
                overall_performance = "underperforming_majority"
            else:
                overall_performance = "mixed"
            
            analysis["summary"] = {
                "total_benchmarks": len(benchmarks),
                "outperforming": outperforming_count,
                "underperforming": len(benchmarks) - outperforming_count,
                "overall_performance": overall_performance,
                "performance_ratio": round(outperforming_count / len(benchmarks), 2)
            }
            
            logger.info(f"Generated comparative analysis for {symbol} vs {len(benchmarks)} benchmarks")
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to generate comparative analysis for {symbol}: {str(e)}")
            raise QuotesServiceError(f"Failed to generate comparative analysis: {str(e)}") from e

    async def _calculate_price_volatility(self, symbol: str, days: int = 20) -> float:
        """
        Calculate price volatility for a symbol using recent price data.
        
        Args:
            symbol: Stock symbol
            days: Number of days to look back for volatility calculation
            
        Returns:
            float: Volatility as standard deviation of daily returns
        """
        try:
            alpaca_client = self._get_alpaca_client()
            
            # Get recent bars for volatility calculation
            bars = await alpaca_client.get_recent_bars(symbol, days=days, timeframe="1Day")
            
            if len(bars) < 2:
                logger.warning(f"Insufficient bars for {symbol} to calculate volatility")
                return 0.0
            
            # Calculate daily returns
            daily_returns = []
            for i in range(1, len(bars)):
                prev_close = float(bars[i-1].close)
                curr_close = float(bars[i].close)
                
                if prev_close > 0:
                    daily_return = (curr_close - prev_close) / prev_close
                    daily_returns.append(daily_return)
            
            if len(daily_returns) < 2:
                logger.warning(f"Insufficient daily returns for {symbol} to calculate volatility")
                return 0.0
            
            # Calculate volatility as standard deviation of daily returns
            import statistics
            volatility = statistics.stdev(daily_returns)
            
            # Convert to percentage and annualize (√252 trading days)
            annualized_volatility = volatility * (252 ** 0.5) * 100
            
            logger.debug(f"Volatility for {symbol}: {annualized_volatility:.2f}% (annualized)")
            return annualized_volatility
            
        except Exception as e:
            logger.error(f"Failed to calculate volatility for {symbol}: {e}")
            return 0.0

# Factory function to create quotes service from existing PricesService
def create_quotes_service(prices_service) -> QuotesService:
    """Create a QuotesService that uses an existing PricesService for configuration"""
    # Extract the AlpacaClient from the PricesService
    alpaca_client = prices_service._alpaca_client if hasattr(prices_service, '_alpaca_client') else None
    return QuotesService(alpaca_client)


# Global instance management (similar to your existing patterns)
_quotes_service: Optional[QuotesService] = None

async def get_quotes_service() -> QuotesService:
    """Get global quotes service instance using existing PricesService"""
    global _quotes_service

    if _quotes_service is None:
        # Create PricesService using same pattern as your existing code
        from src.app.core.config import get_alpaca
        prices_service = get_alpaca()

        _quotes_service = create_quotes_service(prices_service)

    return _quotes_service
