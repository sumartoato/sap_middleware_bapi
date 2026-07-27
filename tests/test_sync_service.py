from sqlalchemy import select

from app.config import get_settings
from app.db.database import session_scope
from app.db.models import Customer, SalesOrder, SalesOrderItem
from app.sap.bapi_client import BAPIClient
from app.services.sync_service import SyncService


def _service() -> SyncService:
    return SyncService(BAPIClient(get_settings()))


def test_sync_customers_upserts_into_postgres():
    result = _service().sync_customers(max_rows=3)

    assert result["status"] == "SUCCESS"
    assert result["records_synced"] == 3
    with session_scope() as session:
        assert session.execute(select(Customer)).scalars().all().__len__() == 3


def test_sync_customers_is_idempotent():
    service = _service()
    service.sync_customers(max_rows=3)
    result = service.sync_customers(max_rows=3)

    assert result["status"] == "SUCCESS"
    with session_scope() as session:
        assert len(session.execute(select(Customer)).scalars().all()) == 3


def test_sync_sales_orders_stores_headers_and_items():
    result = _service().sync_sales_orders(customer_number="1000000000")

    assert result["status"] == "SUCCESS"
    assert result["records_synced"] == 5
    with session_scope() as session:
        assert len(session.execute(select(SalesOrder)).scalars().all()) == 5
        assert len(session.execute(select(SalesOrderItem)).scalars().all()) > 0
