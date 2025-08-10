from src.app.core.app_factory import create_app
from dotenv import load_dotenv

load_dotenv()
app = create_app()

# Optional entry point for programmatically running the app
if __name__ == "__main__":
    import uvicorn
    from src.app.core.config import settings

    uvicorn.run(
        "src.app.main:app",
        host="0.0.0.0",
        port=int(settings.port),
        reload=True
    )

