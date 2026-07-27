import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import Settings
from app.services.sync_service import SyncService

logger = logging.getLogger(__name__)


def start_scheduler(settings: Settings, sync_service: SyncService) -> BackgroundScheduler | None:
    if settings.sync_interval_minutes <= 0:
        logger.info("Scheduler disabled (SYNC_INTERVAL_MINUTES=0)")
        return None

    scheduler = BackgroundScheduler()

    def run_all_syncs() -> None:
        logger.info("Scheduled sync run starting")
        sync_service.sync_customers()
        sync_service.sync_sales_orders()
        logger.info("Scheduled sync run finished")

    scheduler.add_job(
        run_all_syncs,
        "interval",
        minutes=settings.sync_interval_minutes,
        id="sap_sync",
    )
    scheduler.start()
    logger.info("Scheduler started, interval=%s minutes", settings.sync_interval_minutes)
    return scheduler
