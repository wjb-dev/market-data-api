from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional, List, Tuple

import httpx

from src.app.core.http_client import get_http_client

from src.app.schemas.candle import Candle
from src.app.schemas.levels import SRLevel, SRResponse
from src.app.schemas.quote import Quote

logger = logging.getLogger(__name__)


class AlpacaError(Exception):
    pass


class AlpacaClient:
    """
    Thin client around Alpaca Market Data v2.

    Defaults:
      alpaca_base_url: https://data.alpaca.markets/v2     (prod)
                https://data.sandbox.alpaca.markets/v2  (sandbox)
      feed:     "iex" or "sip" (optional; if omitted Alpaca uses your best plan)
    """
    def __init__(
        self,
        alpaca_key_id: str,
        alpaca_secret_key: str,
        alpaca_base_url: str = "https://data.alpaca.markets/v2",
        feed: Optional[str] = None,
        timeout: float = 8.0,
    ) -> None:
        self.alpaca_base_url = alpaca_base_url.rstrip("/")
        self.feed = feed
        self._alpaca_client = httpx.AsyncClient(
            base_url=self.alpaca_base_url,
            timeout=timeout,
            headers={
                "APCA-API-KEY-ID": alpaca_key_id,
                "APCA-API-SECRET-KEY": alpaca_secret_key,
            },
        )

    async def aclose(self) -> None:
        await self._alpaca_client.aclose()

    def _is_data_stale(self, timestamp: datetime) -> bool:
        """
        Check if the data timestamp is older than the last valid trading day.
        
        Args:
            timestamp: The timestamp to check
            
        Returns:
            bool: True if data is stale, False if fresh
        """
        try:
            from datetime import datetime, timezone, timedelta
            
            # Get current time in UTC
            now = datetime.now(timezone.utc)
            
            # Calculate how old the data is
            data_age = now - timestamp
            
            # Check if data is older than 24 hours (conservative threshold)
            # This will catch data from previous trading days
            if data_age > timedelta(hours=24):
                logger.info(f"Data is {data_age.total_seconds() / 3600:.1f} hours old")
                return True
            
            # Additional check: if data is from a weekend or holiday, it's stale
            # For now, we'll use the 24-hour threshold as it's more reliable
            return False
            
        except Exception as e:
            logger.warning(f"Error checking data staleness: {e}")
            # If we can't determine staleness, assume it's fresh
            return False

    # ---- Public API -----------------------------------------------------

    async def get_latest_quote(self, symbol: str) -> Quote:
        """
        Get the latest quote for a symbol using Alpaca's quotes endpoint.
        Based on: https://docs.alpaca.markets/reference/stocklatestquotesingle-1
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Quote: Latest quote data
        """
        try:
            params = {}
            if self.feed:
                params["feed"] = self.feed  # eg "iex" (free) or "sip" (Pro)
            
            # Use the proper quotes endpoint: /v2/stocks/{symbol}/quotes/latest
            r = await self._alpaca_client.get(f"/stocks/{symbol}/quotes/latest", params=params)
            
            if r.status_code == 429:
                reset = r.headers.get("x-ratelimit-reset")
                raise AlpacaError(f"Rate limited by Alpaca (reset={reset})")
            
            if r.is_error:
                raise AlpacaError(f"Alpaca HTTP {r.status_code}: {r.text}")
            
            data = r.json() or {}
            quote_data = data.get("quotes", [{}])[0] if data.get("quotes") else data
            
            # Debug: Log the raw response to see what Alpaca is actually returning
            logger.info(f"Raw Alpaca response for {symbol}: {data}")
            logger.info(f"Quote data extracted: {quote_data}")
            
            # Handle nested quote structure - Alpaca returns {"quote": {...}, "symbol": "..."}
            if "quote" in data and isinstance(data["quote"], dict):
                quote_data = data["quote"]
                logger.info(f"Using nested quote structure for {symbol}")
            elif "quotes" in data and data["quotes"]:
                quote_data = data["quotes"][0]
                logger.info(f"Using quotes array structure for {symbol}")
            else:
                quote_data = data
                logger.info(f"Using direct data structure for {symbol}")
            
            # Extract quote fields from Alpaca's response
            timestamp = _coerce_ts(quote_data.get("t") or quote_data.get("timestamp"))
            sip_timestamp = _coerce_ts(quote_data.get("s")) if quote_data.get("s") else None
            participant_timestamp = _coerce_ts(quote_data.get("p")) if quote_data.get("p") else None
            
            # Try multiple possible field names for prices
            ask_price = _get_num(quote_data, "ap", "ask_price", "askPrice", "ask")
            ask_size = int(_get_num(quote_data, "as", "ask_size", "askSize", "askSize") or 0)
            ask_exchange = quote_data.get("ax") or quote_data.get("askExchange") or quote_data.get("ask_exchange") or ""
            
            bid_price = _get_num(quote_data, "bp", "bid_price", "bidPrice", "bid")
            bid_size = int(_get_num(quote_data, "bs", "bid_size", "bidSize", "bidSize") or 0)
            bid_exchange = quote_data.get("bx") or quote_data.get("bidExchange") or quote_data.get("bid_exchange") or ""
            
            # Debug: Log what we extracted
            logger.info(f"Extracted prices for {symbol}: ask_price={ask_price}, bid_price={bid_price}")
            
            # Validate that we have essential price data
            if ask_price is None or bid_price is None:
                logger.error(f"Missing price data for {symbol}: ask_price={ask_price}, bid_price={bid_price}")
                logger.error(f"Raw quote data: {quote_data}")
                logger.error(f"Available fields: {list(quote_data.keys())}")
                
                # Try fallback to snapshot endpoint
                logger.info(f"Attempting fallback to snapshot endpoint for {symbol}")
                try:
                    return await self._get_snapshot_quote(symbol)
                except Exception as fallback_error:
                    logger.error(f"Fallback to snapshot also failed for {symbol}: {fallback_error}")
                    raise AlpacaError(f"Invalid quote data: missing ask_price or bid_price for {symbol}. Raw data: {quote_data}")
            
            # Handle partial quotes (bid-only or ask-only) - this is normal in some market conditions
            if ask_price <= 0 and bid_price <= 0:
                logger.error(f"Invalid price values for {symbol}: ask_price={ask_price}, bid_price={bid_price}")
                logger.error(f"Raw quote data: {quote_data}")
                raise AlpacaError(f"Invalid quote data: both ask_price and bid_price are zero or negative for {symbol}")
            
            # Log partial quote warnings
            if ask_price <= 0:
                logger.warning(f"Partial quote for {symbol}: ask_price={ask_price} (bid-only quote available)")
                # For bid-only quotes, derive ask from bid with small spread
                ask_price = bid_price * 1.001  # 0.1% spread
                ask_size = 1  # Minimal size
                ask_exchange = "DERIVED"
                
            elif bid_price <= 0:
                logger.warning(f"Partial quote for {symbol}: bid_price={bid_price} (ask-only quote available)")
                # For ask-only quotes, derive bid from ask with small spread
                bid_price = ask_price * 0.999  # 0.1% spread
                bid_size = 1  # Minimal size
                bid_exchange = "DERIVED"
            
            conditions = quote_data.get("c", []) or []
            tape = quote_data.get("z", "")
            trade_id = quote_data.get("i", None)  # "i" is trade_id (integer)
            quote_id = quote_data.get("q", None)  # "q" is quote_id (integer)
            
            # Calculate derived fields
            spread = ask_price - bid_price
            spread_pct = (spread / bid_price * 100) if bid_price > 0 else None
            mid_price = (ask_price + bid_price) / 2
            
            # Check if data is stale (older than last valid trading day)
            if self._is_data_stale(timestamp):
                logger.warning(f"Quote data for {symbol} is stale (timestamp: {timestamp}), will trigger fallback")
                raise AlpacaError(f"Quote data for {symbol} is stale (timestamp: {timestamp}). This symbol may be delisted, inactive, or have market data issues.")
            
            from src.app.schemas.quote import QuoteData
            return Quote(
                symbol=symbol.upper(),
                quote=QuoteData(
                    timestamp=timestamp,
                    ask_exchange=ask_exchange,
                    ask_price=ask_price,  # Now guaranteed to be valid
                    ask_size=ask_size,
                    bid_exchange=bid_exchange,
                    bid_price=bid_price,  # Now guaranteed to be valid
                    bid_size=bid_size,
                    conditions=conditions,
                    tape=tape,
                    sip_timestamp=sip_timestamp,
                    participant_timestamp=participant_timestamp,
                    trade_id=trade_id,
                    quote_id=quote_id,
                    spread=round(spread, 4),
                    spread_pct=round(spread_pct, 3) if spread_pct else None,
                    mid_price=round(mid_price, 4)
                ),
                status="success",
                timestamp=datetime.now(timezone.utc)
            )
            
        except Exception as e:
            logger.error(f"Failed to get latest quote for {symbol}: {e}")
            raise AlpacaError(f"Failed to fetch quote: {str(e)}") from e

    async def _get_snapshot_quote(self, symbol: str) -> Quote:
        """
        Fallback method to get quote data from snapshot endpoint when quotes endpoint fails.
        This provides a backup source of price data.
        """
        try:
            logger.info(f"Using snapshot fallback for {symbol}")
            
            # Get snapshot data
            snapshot = await self._get_snapshot(symbol)
            
            # Extract latest trade and quote data
            latest_trade = snapshot.get("latestTrade", {})
            latest_quote = snapshot.get("latestQuote", {})
            
            # Use trade price as current price if quote is not available
            current_price = float(latest_trade.get("p", 0)) if latest_trade else 0
            
            # If we have quote data, use it; otherwise derive from trade
            if latest_quote and latest_quote.get("ap") and latest_quote.get("bp"):
                ask_price = float(latest_quote.get("ap", 0))
                bid_price = float(latest_quote.get("bp", 0))
                ask_size = int(latest_quote.get("as", 0))
                bid_size = int(latest_quote.get("bs", 0))
            else:
                # Derive bid/ask from trade price with small spread
                spread_factor = 0.001  # 0.1% spread
                ask_price = current_price * (1 + spread_factor)
                bid_price = current_price * (1 - spread_factor)
                ask_size = 100
                bid_size = 100
            
            # Validate prices
            if ask_price <= 0 or bid_price <= 0:
                raise AlpacaError(f"Invalid prices from snapshot: ask={ask_price}, bid={bid_price}")
            
            # Calculate derived fields
            spread = ask_price - bid_price
            spread_pct = (spread / bid_price * 100) if bid_price > 0 else None
            mid_price = (ask_price + bid_price) / 2
            
            from src.app.schemas.quote import QuoteData
            return Quote(
                symbol=symbol.upper(),
                quote=QuoteData(
                    timestamp=_coerce_ts(latest_trade.get("t") or latest_quote.get("t")),
                    ask_exchange=latest_quote.get("ax", ""),
                    ask_price=ask_price,
                    ask_size=ask_size,
                    bid_exchange=latest_quote.get("bx", ""),
                    bid_price=bid_price,
                    bid_size=bid_size,
                    conditions=latest_quote.get("c", []),
                    tape=latest_quote.get("z", ""),
                    sip_timestamp=None,
                    participant_timestamp=None,
                    trade_id=latest_trade.get("i"),
                    quote_id=latest_quote.get("q"),
                    spread=round(spread, 4),
                    spread_pct=round(spread_pct, 3) if spread_pct else None,
                    mid_price=round(mid_price, 4)
                ),
                status="success (snapshot fallback)",
                timestamp=datetime.now(timezone.utc)
            )
            
        except Exception as e:
            logger.error(f"Snapshot fallback failed for {symbol}: {e}")
            raise AlpacaError(f"Both quotes and snapshot endpoints failed for {symbol}: {str(e)}") from e

    async def get_price_quote(self, symbol: str) -> Quote:
        """
        Get current price quote for a symbol.
        This method now uses the proper quotes endpoint for better data quality.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Quote: Current quote data
        """
        return await self.get_latest_quote(symbol)

    async def get_daily_change_percent(self, symbol: str) -> float:
        """
        Calculate daily percent change for a symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            float: Daily percent change as a percentage (e.g., 1.5 for +1.5%)
        """
        try:
            # Get current quote (latest trade price)
            snapshot = await self._get_snapshot(symbol)
            latest_trade = snapshot.get("latestTrade", {})
            current_price = float(latest_trade.get("p", 0))
            
            if current_price == 0:
                logger.warning(f"Current price is 0 for {symbol}, cannot calculate change")
                return 0.0
            
            # Get previous day's closing price
            bars = await self.get_recent_bars(symbol, days=2, timeframe="1Day")
            if len(bars) < 2:
                logger.warning(f"Insufficient bars for {symbol} to calculate daily change")
                return 0.0
            
            # Previous day's close (second to last bar)
            prev_close = float(bars[-2].close)
            
            if prev_close == 0:
                logger.warning(f"Previous close is 0 for {symbol}, cannot calculate change")
                return 0.0
            
            # Calculate percent change
            change_percent = ((current_price - prev_close) / prev_close) * 100
            
            logger.debug(f"Daily change for {symbol}: current={current_price}, prev_close={prev_close}, change={change_percent:.2f}%")
            return round(change_percent, 2)
            
        except Exception as e:
            logger.error(f"Failed to calculate daily change for {symbol}: {e}")
            return 0.0

    async def get_news(
        self,
        limit: int = 50,
        include_content: bool = False,
        exclude_contentless: bool = True,
        sort: str = "desc",
        symbols: Optional[str] = None,
        start: Optional[str] = None,
        end: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get news articles from Alpaca's news API.
        Based on: https://docs.alpaca.markets/reference/news
        
        Args:
            limit: Maximum number of articles to return (1-1000)
            include_content: Whether to include full article content
            exclude_contentless: Whether to exclude articles without content
            sort: Sort order - "asc" (oldest first) or "desc" (newest first)
            symbols: Comma-separated list of symbols to filter by
            start: Start date for news search (ISO format)
            end: End date for news search (ISO format)
            
        Returns:
            Dict: News API response with articles and pagination
        """
        try:
            logger.info(f"AlpacaClient.get_news called with params: limit={limit}, include_content={include_content}, exclude_contentless={exclude_contentless}, sort={sort}, symbols={symbols}")
            
            # Build query parameters
            params = {
                "limit": min(max(limit, 1), 1000),  # Ensure limit is 1-1000
                "include_content": include_content,
                "exclude_contentless": exclude_contentless,
                "sort": sort if sort in ["asc", "desc"] else "desc"
            }
            
            # Add optional parameters
            if symbols:
                params["symbols"] = symbols
            if start:
                params["start"] = start
            if end:
                params["end"] = end
            
            logger.info(f"Built query params: {params}")
            logger.info(f"Making HTTP request to: https://data.alpaca.markets/v1beta1/news")
            logger.info(f"Using _alpaca_client: {type(self._alpaca_client)}")
            
            # Call Alpaca's news endpoint
            # https://data.alpaca.markets/v1beta1/news use this instead
            r = await self._alpaca_client.get("https://data.alpaca.markets/v1beta1/news", params=params)
            
            logger.info(f"HTTP request completed. Status: {r.status_code}")
            logger.info(f"Response headers: {dict(r.headers)}")
            logger.info(f"Response text length: {len(r.text) if r.text else 0}")
            
            if r.status_code == 429:
                reset = r.headers.get("x-ratelimit-reset")
                logger.error(f"Rate limited by Alpaca (reset={reset})")
                raise AlpacaError(f"Rate limited by Alpaca (reset={reset})")
            
            if r.is_error:
                logger.error(f"Alpaca HTTP error {r.status_code}: {r.text}")
                raise AlpacaError(f"Alpaca HTTP {r.status_code}: {r.text}")
            
            logger.info("Parsing JSON response...")
            data = r.json() or {}
            logger.info(f"JSON parsing successful. Data type: {type(data)}")
            logger.info(f"Data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
            
            if isinstance(data, dict) and 'news' in data:
                logger.info(f"Successfully fetched {len(data.get('news', []))} news articles from Alpaca")
            else:
                logger.warning(f"Unexpected response structure: {data}")
            
            return data
            
        except Exception as e:
            logger.error(f"Failed to fetch news from Alpaca: {e}")
            logger.error(f"Exception type: {type(e)}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            raise AlpacaError(f"Failed to fetch news: {str(e)}") from e

    # ---- Internal -------------------------------------------------------

    async def _get_snapshot(self, symbol: str) -> Dict[str, Any]:
        params = {}
        if self.feed:
            params["feed"] = self.feed  # eg "iex" (free) or "sip" (Pro). See FAQ.
        # GET /v2/stocks/{symbol}/snapshot
        # https://docs.alpaca.markets/reference/stocksnapshotsingle
        r = await self._alpaca_client.get(f"/stocks/{symbol}/snapshot", params=params)
        if r.status_code == 429:
            # Surface rate limits for the caller to apply backoff
            reset = r.headers.get("x-ratelimit-reset")
            raise AlpacaError(f"Rate limited by Alpaca (reset={reset})")
        if r.is_error:
            # Keep the body to aid debugging; consider redaction if you log this.
            raise AlpacaError(f"Alpaca HTTP {r.status_code}: {r.text}")
        data = r.json() or {}
        # Single-snapshot REST replies tend to flatten to top-level keys.
        # Some SDKs wrap as {"symbol": "...", "LatestTrade": {...}, ...}
        return data

    async def get_bars(
            self,
            symbol: str,
            timeframe: str = "1Day",
            start: Optional[datetime] = None,
            end: Optional[datetime] = None,
            limit: int = 1000,
            adjustment: str = "split",
    ) -> List[Candle]:
        params: Dict[str, Any] = {
            "timeframe": timeframe,
            "limit": min(limit, 10000),
            "adjustment": adjustment,
        }
        if start:
            params["start"] = start.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
        if end:
            params["end"] = end.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
        if self.feed:
            params["feed"] = self.feed

        out: List[Candle] = []
        page_token: Optional[str] = None
        prev_close: Optional[float] = None

        while True:
            if page_token:
                params["page_token"] = page_token
            r = await self._alpaca_client.get(f"/stocks/{symbol}/bars", params=params)

            if r.is_error:
                logger.error(
                    f"Error fetching bars for {symbol}: {r.status_code} | {r.text} | {r.url}"
                )
                r.raise_for_status()  # Raise exception to indicate failure

            data = r.json() or {}
            bars = data.get("bars") or []
            for b in bars:
                current_close = float(b["c"])
                
                # Calculate changePercent from previous close
                if prev_close is not None and prev_close > 0:
                    change_percent = ((current_close - prev_close) / prev_close) * 100
                else:
                    change_percent = 0.0  # First bar or invalid previous close
                
                out.append(
                    Candle(
                        timestamp=_to_dt(b.get("t")),
                        open=float(b["o"]),
                        high=float(b["h"]),
                        low=float(b["l"]),
                        close=current_close,
                        volume=float(b["v"]),
                        vwap=float(b["vw"]) if b.get("vw") is not None else None,
                        changePercent=round(change_percent, 2),
                    )
                )
                
                # Update previous close for next iteration
                prev_close = current_close
                
            page_token = data.get("next_page_token") or data.get("nextPageToken")
            if not page_token or len(out) >= limit:
                break

        return out

    async def get_recent_bars(self, symbol: str, days: int, timeframe: str = "1Day") -> List[Candle]:
        # Pull a couple of extra buffer days so indicators (ATR) have room
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=max(days + 5, 20))
        bars = await self.get_bars(symbol, timeframe=timeframe, start=start, end=end, limit=1000)
        # Keep only the last <days> bars in case we fetched more
        return bars[-days:]

    # ========= NEW: Aggregated Support/Resistance =========
    async def get_aggregated_sr(
            self,
            symbol: str,
            windows: List[int] = [7, 30, 90],
            max_levels: int = 10,
            swing_window: int = 2,
            tolerance_factor: float = 0.5,
    ) -> SRResponse:
        """
        Build aggregated S/R by:
          1) fetching bars for each lookback window,
          2) computing ATR(14),
          3) detecting swing highs/lows (fractal window),
          4) clustering prices within tolerance = max(ATR * tolerance_factor, range * 0.5%)
          5) scoring by touches + recency.
        """
        windows = sorted(set(int(x) for x in windows))
        atr_map: Dict[int, float] = {}
        all_levels: List[Tuple[float, str, int, datetime, datetime, int]] = []
        # (price, side, touches, first_ts, last_ts, window_days)

        for w in windows:
            bars = await self.get_recent_bars(symbol, days=w, timeframe="1Day")
            if len(bars) < max(15, swing_window * 2 + 1):
                continue

            atr = _atr14(bars)
            atr_map[w] = atr

            swings = _find_swings(bars, swing_window=swing_window)
            # tolerance based on ATR and range
            price_min = min(b.low for b in bars)
            price_max = max(b.high for b in bars)
            rng = max(price_max - price_min, 1e-9)
            tol = max(atr * tolerance_factor, rng * 0.005)

            clustered = _cluster_levels(swings, tolerance=tol)
            # append with window tag
            for lv in clustered:
                all_levels.append((lv.price, lv.side, lv.touches, lv.firstSeen, lv.lastSeen, w))

        # Merge across windows with a second clustering pass (use median ATR as tol baseline)
        if not all_levels:
            return SRResponse(symbol=symbol.upper(), windows=windows, atr14=atr_map, levels=[])

        median_atr = _median(list(atr_map.values())) if atr_map else 0.0
        tol_cross = max(median_atr * 0.5, 0.005 * _price_range_from_levels(all_levels))
        merged = _merge_across_windows(all_levels, tolerance=tol_cross)

        # Score and keep top-N by strength (balanced S/R mix)
        levels_scored = _score_levels(merged)
        # cap total levels
        levels_scored.sort(key=lambda x: x.strength, reverse=True)
        levels_out = levels_scored[:max_levels]

        return SRResponse(symbol=symbol.upper(), windows=windows, atr14=atr_map, levels=levels_out)


def _get_num(obj: Dict[str, Any], *keys: str) -> Optional[float]:
    for k in keys:
        v = obj.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    return None


def _coerce_ts(value: Any) -> datetime:
    if isinstance(value, datetime):
        # Ensure UTC
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        # Alpaca returns RFC3339 with Z; normalize to aware UTC
        # Example: "2023-09-29T19:59:59.246196362Z"
        s = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(s).astimezone(timezone.utc)
        except Exception:
            pass
    # Fallback to now (avoid None in schema)
    return datetime.now(timezone.utc)

# ----------------- helpers -----------------

def _to_dt(value) -> datetime:
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


def _atr14(bars: List[Candle]) -> float:
    if len(bars) < 2:
        return 0.0
    trs: List[float] = []
    prev_close = bars[0].close
    for i in range(1, len(bars)):
        h, l, c = bars[i].high, bars[i].low, bars[i].close
        tr = max(h - l, abs(h - prev_close), abs(l - prev_close))
        trs.append(tr)
        prev_close = c
    # Wilder's smoothing approximation; simple average is okay for our use
    n = min(14, len(trs))
    return sum(trs[-n:]) / n if trs else 0.0


def _find_swings(bars: List[Candle], swing_window: int = 2) -> List[SRLevel]:
    """
    Mark swing highs (resistance) and swing lows (support)
    using a simple fractal rule with window k on each side.
    """
    out: List[SRLevel] = []
    for i in range(swing_window, len(bars) - swing_window):
        hi = max(b.high for b in bars[i - swing_window: i + swing_window + 1])
        lo = min(b.low for b in bars[i - swing_window: i + swing_window + 1])
        b = bars[i]
        default_strength_value = 0.5
        if b.high >= hi:
            out.append(SRLevel(
                price=b.high,
                side="resistance",
                touches=1,
                firstSeen=b.timestamp,
                lastSeen=b.timestamp,
                sources=[],
                strength=default_strength_value
            ))
        if b.low <= lo:
            out.append(SRLevel(price=b.low, side="support", touches=1, firstSeen=b.timestamp, lastSeen=b.timestamp, sources=[], strength=default_strength_value))
    return out


def _cluster_levels(levels: List[SRLevel], tolerance: float) -> List[SRLevel]:
    """
    Greedy 1D clustering: merge levels within +/- tolerance.
    Touches add up; timestamps expand; price becomes weighted average by touches.
    """
    if not levels:
        return []
    levels_sorted = sorted(levels, key=lambda x: x.price)
    clusters: List[SRLevel] = []
    cur = levels_sorted[0]
    for lv in levels_sorted[1:]:
        if lv.side != cur.side or abs(lv.price - cur.price) > tolerance:
            clusters.append(cur)
            cur = lv
        else:
            total_touches = cur.touches + lv.touches
            cur.price = (cur.price * cur.touches + lv.price * lv.touches) / max(total_touches, 1)
            cur.touches = total_touches
            cur.firstSeen = min(cur.firstSeen, lv.firstSeen)
            cur.lastSeen = max(cur.lastSeen, lv.lastSeen)
    clusters.append(cur)
    return clusters


def _price_range_from_levels(all_levels: List[tuple]) -> float:
    prices = [p for (p, *_rest) in all_levels]
    return (max(prices) - min(prices)) if prices else 0.0


def _merge_across_windows(
        all_levels: List[tuple], tolerance: float
) -> List[SRLevel]:
    """
    Merge tuples (price, side, touches, first, last, window) across windows.
    """
    if not all_levels:
        return []
    # Separate supports/resistances to avoid cross-merge
    supports = [x for x in all_levels if x[1] == "support"]
    resistances = [x for x in all_levels if x[1] == "resistance"]

    def _merge(side_entries: List[tuple]) -> List[SRLevel]:
        if not side_entries:
            return []
        side_entries.sort(key=lambda x: x[0])
        merged: List[SRLevel] = []
        # seed
        cur_price, _, cur_touch, cur_first, cur_last, cur_win = side_entries[0]
        cur_src = {cur_win}
        for (price, _side, touches, first, last, win) in side_entries[1:]:
            if abs(price - cur_price) <= tolerance:
                # merge
                total = cur_touch + touches
                cur_price = (cur_price * cur_touch + price * touches) / max(total, 1)
                cur_touch = total
                cur_first = min(cur_first, first)
                cur_last = max(cur_last, last)
                cur_src.add(win)
            else:
                merged.append(
                    SRLevel(
                        price=float(cur_price),
                        side="support" if side_entries[0][1] == "support" else "resistance",
                        touches=int(cur_touch),
                        strength=0.0,  # filled later
                        firstSeen=cur_first,
                        lastSeen=cur_last,
                        sources=sorted(list(cur_src)),
                    )
                )
                cur_price, cur_touch, cur_first, cur_last, cur_src = price, touches, first, last, {win}
        merged.append(
            SRLevel(
                price=float(cur_price),
                side="support" if side_entries[0][1] == "support" else "resistance",
                touches=int(cur_touch),
                strength=0.0,
                firstSeen=cur_first,
                lastSeen=cur_last,
                sources=sorted(list(cur_src)),
            )
        )
        return merged

    return _merge(supports) + _merge(resistances)


def _score_levels(levels: List[SRLevel]) -> List[SRLevel]:
    """
    Score: touches (60%) + recency (40%).
    Recency ~ 1 / (1 + age_days).
    """
    if not levels:
        return levels

    now = datetime.now(timezone.utc)
    max_touches = max(l.touches for l in levels) or 1
    for l in levels:
        touch_score = l.touches / max_touches
        last_seen = l.lastSeen.replace(tzinfo=timezone.utc) if l.lastSeen and l.lastSeen.tzinfo is None else l.lastSeen
        age_days = max((now - (last_seen or now)).days, 0)
        recency = 1.0 / (1.0 + age_days)
        l.strength = round(0.6 * touch_score + 0.4 * recency, 4)
    return levels


def _median(arr: List[float]) -> float:
    if not arr:
        return 0.0
    s = sorted(arr)
    n = len(s)
    mid = n // 2
    if n % 2:
        return s[mid]
    return 0.5 * (s[mid - 1] + s[mid])
