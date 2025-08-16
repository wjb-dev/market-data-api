"""
Streaming API router integrated with existing AlpacaClient patterns
"""

import asyncio
import json
import logging
from typing import List
from fastapi import APIRouter, Query, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from src.app.core.config import get_settings, get_alpaca
from src.app.services.streaming_service import get_streaming_service, StreamingError, create_streaming_service
from src.app.clients.alpaca_client import AlpacaError
from src.app.schemas.streaming import StreamingErrorResponse, StreamingStatus

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/streaming", tags=["Streaming"])

async def require_api_key():
    """
    API key validation dependency
    Placeholder for authentication logic - implement based on your auth requirements
    """
    return True


async def validate_symbols(symbols_param: str) -> List[str]:
    """Validate and parse symbols parameter using existing patterns"""
    if not symbols_param:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=StreamingErrorResponse(
                error="bad_request",
                message="symbols parameter is required"
            ).model_dump()
        )

    symbols = [s.strip().upper() for s in symbols_param.split(",") if s.strip()]

    if not symbols:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=StreamingErrorResponse(
                error="bad_request",
                message="At least one valid symbol is required"
            ).model_dump()
        )

    if len(symbols) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=StreamingErrorResponse(
                error="bad_request",
                message=f"Too many symbols (max {100})"
            ).model_dump()
        )

    return symbols


async def sse_event_generator(symbols: List[str]):
    """Generate Server-Sent Events for price streaming"""
    streaming_service = None

    try:
        # Check if streaming is enabled
        if not get_settings().alpaca_streaming_enabled:
            yield f"event: error\ndata: {json.dumps({'error': 'streaming_disabled', 'message': 'Real-time streaming is disabled'})}\n\n"
            return

        # Create streaming service
        prices_service = get_alpaca()
        streaming_service = create_streaming_service(prices_service)

        # Send initial connection event
        yield f"event: connected\ndata: {json.dumps({'symbols': symbols, 'status': 'connecting'})}\n\n"

        # Stream price data
        async for event in streaming_service.stream_prices(symbols):
            event_type = event.get("event", "data")
            event_data = event.get("data", {})

            # Format as SSE
            sse_event = f"event: {event_type}\ndata: {json.dumps(event_data)}\n\n"
            yield sse_event

            # Add small delay to prevent overwhelming
            await asyncio.sleep(0.01)

    except StreamingError as e:
        logger.error(f"Streaming error: {e}")
        error_event = f"event: error\ndata: {json.dumps({'error': 'streaming_error', 'message': str(e)})}\n\n"
        yield error_event

    except AlpacaError as e:
        logger.error(f"Alpaca API error: {e}")
        error_event = f"event: error\ndata: {json.dumps({'error': 'alpaca_error', 'message': str(e)})}\n\n"
        yield error_event

    except asyncio.CancelledError:
        logger.info("Streaming connection cancelled by client")

    except Exception as e:
        logger.error(f"Unexpected error in streaming: {e}")
        error_event = f"event: error\ndata: {json.dumps({'error': 'internal_error', 'message': 'Internal server error'})}\n\n"
        yield error_event

    finally:
        # Clean up streaming service
        if streaming_service:
            try:
                await streaming_service.close()
            except Exception as e:
                logger.error(f"Error closing streaming service: {e}")


@router.get(
    "/prices",
    summary="Stream real-time stock prices",
    description="Stream real-time price data for specified symbols via Server-Sent Events. "
                "Combines Alpaca WebSocket streaming with REST API snapshots for complete price data.",
    responses={
        200: {
            "description": "Server-Sent Events stream of price data",
            "content": {
                "text/event-stream": {
                    "example": "event: price\ndata: {\"symbol\": \"AAPL\", \"last\": 150.25, \"change\": 2.15, \"changePercent\": 1.45}\n\n"
                }
            }
        },
        400: {"model": StreamingErrorResponse},
        500: {"model": StreamingErrorResponse}
    }
)
async def stream_prices(
        symbols: str = Query(
            ...,
            description="Comma-separated list of stock symbols (e.g., 'AAPL,GOOGL,MSFT')",
            example="AAPL,GOOGL,MSFT"
        ),
        _: bool = Depends(require_api_key)
):
    """
    Stream real-time price data for the specified stock symbols.

    This endpoint provides Server-Sent Events with:
    - `connected`: Initial connection confirmation
    - `price`: Complete PriceQuote objects with real-time updates
    - `raw`: Raw market data from Alpaca WebSocket
    - `error`: Error messages

    The streaming service combines real-time WebSocket data with REST API snapshots
    to provide complete price information including OHLC, volume, and calculated fields.
    """
    validated_symbols = await validate_symbols(symbols)

    try:
        generator = sse_event_generator(validated_symbols)

        return StreamingResponse(
            generator,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Cache-Control",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            }
        )

    except Exception as e:
        logger.error(f"Failed to start streaming for symbols {validated_symbols}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=StreamingErrorResponse(
                error="service_error",
                message="Failed to initialize streaming service"
            ).model_dump()
        )


@router.get(
    "/quotes",
    summary="Get current quotes",
    description="Get current quotes combining real-time streaming data with REST API snapshots",
    response_model=dict
)
async def get_current_quotes(
        symbols: str = Query(
            ...,
            description="Comma-separated list of stock symbols",
            example="AAPL,GOOGL,MSFT"
        ),
        _: bool = Depends(require_api_key)
):
    """
    Get current quotes for the specified symbols.

    This endpoint returns Quote objects that combine:
    - Real-time streaming data (if available)
    - REST API snapshot data as fallback
    - Complete bid/ask, volume, and timestamp data
    """
    validated_symbols = await validate_symbols(symbols)

    try:
        if get_settings().alpaca_streaming_enabled:
            # Use streaming service for real-time data
            streaming_service = await get_streaming_service()
            quotes = await streaming_service.get_current_quotes(validated_symbols)
        else:
            # Fallback to REST API only
            prices_service = get_alpaca()
            quotes = {}

            for symbol in validated_symbols:
                try:
                    quote = await prices_service.get_price_quote(symbol)
                    quotes[symbol] = quote
                except AlpacaError as e:
                    logger.warning(f"Failed to get quote for {symbol}: {e}")
                    continue

            await prices_service.aclose()

        # Convert Quote objects to dictionaries
        quotes_dict = {symbol: quote.model_dump() for symbol, quote in quotes.items()}

        return {
            "quotes": quotes_dict,
            "requested_symbols": validated_symbols,
            "found_symbols": list(quotes.keys()),
            "streaming_enabled": get_settings().alpaca_streaming_enabled,
            "timestamp": quotes[list(quotes.keys())[0]].quote.timestamp.isoformat() if quotes else None
        }

    except AlpacaError as e:
        logger.error(f"Alpaca API error getting quotes for {validated_symbols}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=StreamingErrorResponse(
                error="alpaca_error",
                message=f"Alpaca API error: {str(e)}"
            ).model_dump()
        )

    except Exception as e:
        logger.error(f"Failed to get quotes for symbols {validated_symbols}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=StreamingErrorResponse(
                error="service_error",
                message="Failed to retrieve quotes"
            ).model_dump()
        )


@router.get(
    "/status",
    summary="Get streaming service status",
    description="Check the health and status of the streaming service",
    response_model=StreamingStatus
)
async def get_streaming_status(_: bool = Depends(require_api_key)):
    """Get the current status of the streaming service"""
    try:
        if not get_settings().alpaca_streaming_enabled:
            return StreamingStatus(
                status="disabled",
                connected=False,
                authenticated=False,
                feed="iex",
                sandbox=get_settings().is_alpaca_sandbox,
                active_symbols=[]
            )

        streaming_service = await get_streaming_service()
        status = await streaming_service.get_status()

        return status

    except Exception as e:
        logger.error(f"Streaming service health check failed: {e}")
        return StreamingStatus(
            status="error",
            connected=False,
            authenticated=False,
            feed="iex",
            sandbox=False,
            active_symbols=[]
        )


@router.get(
    "/health",
    summary="Streaming service health check",
    description="Simple health check endpoint for monitoring"
)
async def health_check():
    """Simple health check endpoint"""
    return {
        "status": "alive",
        "service": "streaming",
        "streaming_enabled": get_settings().alpaca_streaming_enabled,
    }