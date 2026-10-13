from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.App.Settings import get_settings
from src.Features.Health.Router import router as health_router
from src.Features.Opencode.ContainerManager import ContainerManager
from src.Features.Opencode.Router import router as opencode_router
from src.Shared.Errors.ExceptionHandlers import register_exception_handlers
from src.Shared.Middleware.RequestIdMiddleware import RequestIdMiddleware

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    version="0.1.0",
)
app.state.settings = settings
app.state.container_manager = ContainerManager(settings)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)
app.add_middleware(RequestIdMiddleware)
register_exception_handlers(app)

app.include_router(health_router, prefix=settings.api_prefix)
app.include_router(opencode_router, prefix=settings.api_prefix)
