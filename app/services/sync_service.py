import datetime as dt
import logging

from app.db.database import session_scope
from app.db.repository import (
    upsert_customers,
    upsert_materials,
    upsert_sales_order_items,
    upsert_sales_orders,
    write_sync_log,
)
from app.sap.bapi_client import BAPIClient
from app.sap.exceptions import BAPIExecutionError, SAPConnectionError

logger = logging.getLogger(__name__)


class SyncService:
    """Orchestrates: call a BAPI -> transform rows -> upsert into Postgres -> log the run."""

    def __init__(self, bapi_client: BAPIClient):
        self._bapi = bapi_client

    def sync_customers(self, max_rows: int = 100) -> dict:
        return self._run("BAPI_CUSTOMER_GETLIST", lambda: self._sync_customers(max_rows))

    def sync_materials(self, material_numbers: list[str]) -> dict:
        return self._run(
            "BAPI_MATERIAL_GET_DETAIL", lambda: self._sync_materials(material_numbers)
        )

    def sync_sales_orders(
        self, customer_number: str | None = None, sales_organization: str | None = None
    ) -> dict:
        return self._run(
            "BAPI_SALESORDER_GETDETAILEDLIST",
            lambda: self._sync_sales_orders(customer_number, sales_organization),
        )

    # -- internal ------------------------------------------------------

    def _run(self, bapi_name: str, fn) -> dict:
        started_at = dt.datetime.utcnow()
        try:
            records = fn()
            finished_at = dt.datetime.utcnow()
            with session_scope() as session:
                write_sync_log(
                    session, bapi_name, "SUCCESS", records, started_at, finished_at
                )
            return {
                "status": "SUCCESS",
                "bapi_name": bapi_name,
                "records_synced": records,
                "started_at": started_at,
                "finished_at": finished_at,
            }
        except (BAPIExecutionError, SAPConnectionError) as exc:
            finished_at = dt.datetime.utcnow()
            logger.exception("Sync failed for %s", bapi_name)
            with session_scope() as session:
                write_sync_log(
                    session, bapi_name, "FAILED", 0, started_at, finished_at, message=str(exc)
                )
            return {
                "status": "FAILED",
                "bapi_name": bapi_name,
                "records_synced": 0,
                "started_at": started_at,
                "finished_at": finished_at,
                "message": str(exc),
            }

    def _sync_customers(self, max_rows: int) -> int:
        rows = self._bapi.get_customers(max_rows=max_rows)
        with session_scope() as session:
            return upsert_customers(session, rows)

    def _sync_materials(self, material_numbers: list[str]) -> int:
        rows = self._bapi.get_material_details(material_numbers)
        with session_scope() as session:
            return upsert_materials(session, rows)

    def _sync_sales_orders(
        self, customer_number: str | None, sales_organization: str | None
    ) -> int:
        headers, items = self._bapi.get_sales_orders(customer_number, sales_organization)
        with session_scope() as session:
            count = upsert_sales_orders(session, headers)
            upsert_sales_order_items(session, items)
        return count
