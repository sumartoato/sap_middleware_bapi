import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.config import get_settings
from app.db.database import init_db
from app.logging_config import setup_logging
from app.sap.bapi_client import BAPIClient
from app.scheduler import start_scheduler
from app.services.sync_service import SyncService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.log_level)
    init_db()

    bapi_client = BAPIClient(settings)
    app.state.bapi_client = bapi_client

    scheduler = start_scheduler(settings, SyncService(bapi_client))
    app.state.scheduler = scheduler

    logger.info("SAP middleware started (mock_mode=%s)", settings.sap_mock_mode)
    yield

    if scheduler is not None:
        scheduler.shutdown(wait=False)
    bapi_client.close()


app = FastAPI(
    title="SAP BAPI Middleware",
    description="Pulls data from SAP via BAPI/RFC and stores it in PostgreSQL",
    version="1.0.0",
    lifespan=lifespan,
)
app.include_router(router)
