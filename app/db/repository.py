import datetime as dt
from typing import Any, Iterable, Mapping

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import Customer, Material, SalesOrder, SalesOrderItem, SyncLog


def _upsert(session: Session, model, rows: Iterable[Mapping[str, Any]], pk_columns: list[str]) -> int:
    rows = [dict(row) for row in rows]
    if not rows:
        return 0

    stmt = pg_insert(model).values(rows)
    update_cols = {
        col.name: getattr(stmt.excluded, col.name)
        for col in model.__table__.columns
        if col.name not in pk_columns
    }
    stmt = stmt.on_conflict_do_update(index_elements=pk_columns, set_=update_cols)
    session.execute(stmt)
    return len(rows)


def upsert_customers(session: Session, rows: Iterable[Mapping[str, Any]]) -> int:
    return _upsert(session, Customer, rows, ["kunnr"])


def upsert_materials(session: Session, rows: Iterable[Mapping[str, Any]]) -> int:
    return _upsert(session, Material, rows, ["matnr"])


def upsert_sales_orders(session: Session, rows: Iterable[Mapping[str, Any]]) -> int:
    return _upsert(session, SalesOrder, rows, ["vbeln"])


def upsert_sales_order_items(session: Session, rows: Iterable[Mapping[str, Any]]) -> int:
    return _upsert(session, SalesOrderItem, rows, ["vbeln", "posnr"])


def write_sync_log(
    session: Session,
    bapi_name: str,
    status: str,
    records_synced: int,
    started_at: dt.datetime,
    finished_at: dt.datetime,
    message: str | None = None,
) -> SyncLog:
    log = SyncLog(
        bapi_name=bapi_name,
        status=status,
        records_synced=records_synced,
        message=message,
        started_at=started_at,
        finished_at=finished_at,
    )
    session.add(log)
    session.flush()
    return log
