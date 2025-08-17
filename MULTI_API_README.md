# Multi-API Market Data Platform

This platform now supports multiple API groups with a **single Swagger UI** that includes a dropdown selector to switch between different API specifications. **This is now the default behavior!**

## 🚀 Quick Start

### Multi-API Mode (Default)
```bash
# Start the multi-API version (now the default)
make run

# Or directly with Python
python -m src.app.main
```

### Legacy Single API Mode
```bash
# Start the legacy single API version
make run-single-api

# Note: This requires modifying the app factory to use the old single-API setup
```

## 📚 Available API Documentation

### Multi-API Mode (Default)
When running the platform, you'll have access to:

1. **Single Swagger UI** (`/market-data-api/docs`)
   - **Dropdown Selector** in the top right corner to switch between APIs
   - **Market Data API** - Financial data, quotes, and market intelligence
   - **Utils API** - System performance, monitoring, and health checks
   - Each API specification shows only its relevant endpoints and tags

2. **API Specifications**
   - **Market Data API**: `/market-data/openapi.json`
   - **Utils API**: `/utils/openapi.json`

### Legacy Single API Mode
When running in legacy mode, you'll have:
- Single Swagger documentation at `/market-data-api/docs`
- All endpoints in one place
- Original behavior for backward compatibility

## 🔧 API Group Organization

### Utils API Group
- **Performance**: Cache statistics, response times, system performance
- **Monitoring**: Health checks, uptime monitoring, system analytics
- **Health**: Container orchestration health verification

### Market Data API Group
- **Quotes**: Real-time market quotes, pricing data, market intelligence
- **Candles**: Historical OHLCV data, technical indicators, patterns
- **Articles**: Financial news, market sentiment, AI-ready content
- **Streaming**: Real-time data streaming via Server-Sent Events

## 🌐 Access URLs

### Multi-API Mode (Default)
- **Single Swagger UI**: http://localhost:8000/market-data-api/docs
- **ReDoc**: http://localhost:8000/market-data-api/redoc
- **Root Info**: http://localhost:8000/

### Legacy Single API Mode
- **API Documentation**: http://localhost:8000/market-data-api/docs
- **ReDoc**: http://localhost:8000/market-data-api/redoc

## 🎯 How to Use the Dropdown Selector

1. **Navigate to Swagger UI**: Go to `http://localhost:8000/market-data-api/docs`
2. **Find the Dropdown**: Look for the dropdown selector in the **top right corner** of the Swagger UI
3. **Switch APIs**: Click the dropdown and select:
   - **Market Data API** - For financial data endpoints
   - **Utils API** - For system utilities and monitoring
4. **Explore Endpoints**: Each API specification shows only its relevant endpoints and tags

## 🏗️ Architecture

The multi-API setup uses FastAPI's mounting capabilities with multiple OpenAPI specifications:

```
Main App (/) - Single Swagger UI with dropdown selector
├── Utils App (/utils) - System utilities and monitoring
└── Market Data App (/market-data) - Financial data and market intelligence
```

**Key Features:**
- **Single Swagger UI** at `/market-data-api/docs` (now the default)
- **Dropdown selector** to switch between API specifications
- **Separate OpenAPI specs** for each API group
- **Mounted apps** for clean endpoint organization
- **Unified developer experience** with easy API switching

## 🔄 Migration

### For Existing Users
- **No breaking changes**: Your existing code continues to work
- **Same endpoints**: All API endpoints remain at the same paths
- **Enhanced docs**: Better organized documentation with API groups
- **Single UI**: One place to explore all APIs (now default)

### For New Development
- **Choose your API**: Use dropdown to focus on relevant endpoints
- **Focused docs**: Each API specification shows only relevant endpoints
- **Better UX**: Cleaner, more focused developer experience
- **Easy switching**: Toggle between APIs without leaving the page

## 🛠️ Development

### Adding New Endpoints
1. Create your router in `src/app/api/v1/routers/`
2. Add it to the appropriate group in `src/app/core/routers.py`
3. The endpoint will automatically appear in the correct API specification

### Customizing API Groups
1. Modify `src/app/swagger_config/api_groups.py`
2. Update tags in `src/app/swagger_config/tags.py`
3. Adjust router grouping in `src/app/core/routers.py`
4. Update the `urls` parameter in Swagger UI configuration

### Running Tests
```bash
# Run all tests
make test

# Run specific test categories
pytest tests/unit/
pytest tests/integration/
```

## 📊 Benefits

1. **Single Interface**: One Swagger UI to rule them all (now default)
2. **Easy Switching**: Dropdown selector for quick API navigation
3. **Better Organization**: Clear separation between system utilities and market data
4. **Focused Documentation**: Developers see only relevant endpoints for their use case
5. **Scalability**: Easy to add new API groups in the future
6. **Maintainability**: Cleaner code organization and easier maintenance
7. **Developer Experience**: Better navigation and understanding of available APIs

## 🚀 Future Enhancements

- **Authentication Groups**: Different auth requirements per API group
- **Rate Limiting**: Group-specific rate limiting policies
- **Monitoring**: Separate metrics and monitoring per API group
- **Documentation**: Group-specific examples and tutorials
- **SDKs**: Language-specific client libraries per API group
- **API Versioning**: Support for multiple API versions within groups

## 🔧 Configuration

The multi-API functionality is now configured in:
- `src/app/core/app_factory.py` - Main app factory with multi-API setup
- `src/app/swagger_config/api_groups.py` - API group definitions
- `src/app/swagger_config/tags.py` - Tag organization
- `src/app/core/routers.py` - Router grouping logic

**Implementation based on Swagger UI 3 multiple document support** as described in [GitHub issue #1326](https://github.com/RicoSuter/NSwag/issues/1326).
