# Utils API Group
utils_tags_metadata = [
    {
        "name": "Performance",
        "description": "System performance metrics, cache statistics, and Redis monitoring. Track API performance, cache efficiency, and system health for optimization.",
        "externalDocs": {
            "description": "Performance monitoring documentation",
            "url": "https://docs.alpaca.markets/reference/rate-limits"
        }
    },
    {
        "name": "Monitoring",
        "description": "Advanced system monitoring, health checks, and performance analytics. Comprehensive monitoring for production environments and DevOps operations.",
        "externalDocs": {
            "description": "System monitoring guide",
            "url": "https://docs.alpaca.markets/reference/rate-limits"
        }
    },
    {
        "name": "Health",
        "description": "Lightweight health check endpoints consumed by orchestrators (K8s, Nomad, ...) to verify container liveness and readiness.",
        "externalDocs": {
            "description": "Health check standards",
            "url": "https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/"
        }
    }
]

# Market Data API Group
market_data_tags_metadata = [
    {
        "name": "Quotes",
        "description": "Real-time market quotes, pricing data, market intelligence, and comparative analysis. Get live bid/ask prices, spreads, volume analysis, and performance comparisons against benchmarks.",
        "externalDocs": {
            "description": "Learn more about market quotes",
            "url": "https://docs.alpaca.markets/reference/stockquotes-1"
        }
    },
    {
        "name": "Candles",
        "description": "Historical OHLCV data, technical indicators, candlestick patterns, and support/resistance levels. Access historical price data, calculate technical indicators, and detect trading patterns.",
        "externalDocs": {
            "description": "Learn more about historical data",
            "url": "https://docs.alpaca.markets/reference/stockbars-1"
        }
    },
    {
        "name": "Articles",
        "description": "Financial news and market sentiment data. Fetch real-time news articles, filter by symbols, and get clean text content for AI analysis and sentiment processing.",
        "externalDocs": {
            "description": "Learn more about news data",
            "url": "https://docs.alpaca.markets/reference/news"
        }
    },
    {
        "name": "Streaming",
        "description": "Real-time data streaming via Server-Sent Events (SSE). Get live price updates, market data streams, and real-time notifications for active trading.",
        "externalDocs": {
            "description": "Learn more about streaming",
            "url": "https://docs.alpaca.markets/reference/streaming"
        }
    }
]

# Legacy tags for backward compatibility
tags_metadata = utils_tags_metadata + market_data_tags_metadata
