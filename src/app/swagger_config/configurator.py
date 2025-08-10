from fastapi.openapi.utils import get_openapi
from fastapi import FastAPI
from src.app.swagger_config.tags import tags_metadata
from src.app.swagger_config.contact import get_contact_info
from src.app.swagger_config.servers import get_servers


def custom_openapi(app: FastAPI, settings):
    """
    Customizes the OpenAPI schema by adding tags, contact info, servers, and more.
    """
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=settings.app_name,
        version=settings.version,
        description=settings.description,
        routes=app.routes,
    )
    schema["tags"] = tags_metadata
    schema["info"].update(get_contact_info())
    schema["servers"] = get_servers()

    app.openapi_schema = schema
    return schema
