import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from core.config import settings
from api.api_v1.api import api_router
from init_gatekeeper import register_apis_to_gatekeeper
from utils.pdf_cleanup import cleanup_loop


@asynccontextmanager
async def lifespan(fa: FastAPI):
    if settings.REPORTING_USING_GATEKEEPER:
        register_apis_to_gatekeeper()
    # PARCHE CNTA: borrado periodico de los PDF generados (ver utils/pdf_cleanup.py)
    limpieza = None
    if settings.REPORTING_PDF_RETENTION_HOURS > 0:
        limpieza = asyncio.create_task(
            cleanup_loop(
                settings.PDF_DIRECTORY,
                settings.REPORTING_PDF_RETENTION_HOURS,
                settings.REPORTING_PDF_CLEANUP_INTERVAL_MINUTES,
            )
        )
    try:
        yield
    finally:
        if limpieza:
            limpieza.cancel()
            with suppress(asyncio.CancelledError):
                await limpieza


app = FastAPI(
    title="Reporting service", openapi_url="/api/v1/openapi.json", lifespan=lifespan
)


# Set all CORS enabled origins
if settings.REPORTING_BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.REPORTING_BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix="/api/v1")
