import datetime as dt

from sqlalchemy import DateTime, ForeignKeyConstraint, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class Customer(Base):
    """Mirrors BAPI_CUSTOMER_GETLIST / KNA1 address data."""

    __tablename__ = "customers"

    kunnr: Mapped[str] = mapped_column(String(10), primary_key=True)  # SAP customer number
    name1: Mapped[str | None] = mapped_column(String(35))
    city: Mapped[str | None] = mapped_column(String(35))
    postal_code: Mapped[str | None] = mapped_column(String(10))
    country: Mapped[str | None] = mapped_column(String(3))
    region: Mapped[str | None] = mapped_column(String(3))
    street: Mapped[str | None] = mapped_column(String(60))
    telephone: Mapped[str | None] = mapped_column(String(30))
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow
    )


class Material(Base):
    """Mirrors BAPI_MATERIAL_GETALL / MARA master data."""

    __tablename__ = "materials"

    matnr: Mapped[str] = mapped_column(String(18), primary_key=True)  # SAP material number
    description: Mapped[str | None] = mapped_column(String(40))
    material_type: Mapped[str | None] = mapped_column(String(4))
    material_group: Mapped[str | None] = mapped_column(String(9))
    base_uom: Mapped[str | None] = mapped_column(String(3))
    industry_sector: Mapped[str | None] = mapped_column(String(1))
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow
    )


class SalesOrder(Base):
    """Mirrors BAPI_SALESORDER_GETLIST / VBAK header data."""

    __tablename__ = "sales_orders"

    vbeln: Mapped[str] = mapped_column(String(10), primary_key=True)  # SAP sales document number
    doc_type: Mapped[str | None] = mapped_column(String(4))
    doc_date: Mapped[dt.date | None] = mapped_column()
    sold_to: Mapped[str | None] = mapped_column(String(10))
    sales_org: Mapped[str | None] = mapped_column(String(4))
    distr_channel: Mapped[str | None] = mapped_column(String(2))
    division: Mapped[str | None] = mapped_column(String(2))
    net_value: Mapped[float | None] = mapped_column(Numeric(15, 2))
    currency: Mapped[str | None] = mapped_column(String(5))
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow
    )

    items: Mapped[list["SalesOrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class SalesOrderItem(Base):
    """Mirrors BAPI_SALESORDER_GETLIST / VBAP item data."""

    __tablename__ = "sales_order_items"
    __table_args__ = (
        ForeignKeyConstraint(["vbeln"], ["sales_orders.vbeln"], ondelete="CASCADE"),
    )

    vbeln: Mapped[str] = mapped_column(String(10), primary_key=True)
    posnr: Mapped[str] = mapped_column(String(6), primary_key=True)  # item number
    matnr: Mapped[str | None] = mapped_column(String(18))
    quantity: Mapped[float | None] = mapped_column(Numeric(15, 3))
    uom: Mapped[str | None] = mapped_column(String(3))
    net_value: Mapped[float | None] = mapped_column(Numeric(15, 2))
    plant: Mapped[str | None] = mapped_column(String(4))

    order: Mapped["SalesOrder"] = relationship(back_populates="items")


class SyncLog(Base):
    """Audit trail of every BAPI-to-Postgres sync run."""

    __tablename__ = "sync_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bapi_name: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(10))  # SUCCESS | FAILED
    records_synced: Mapped[int] = mapped_column(default=0)
    message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
