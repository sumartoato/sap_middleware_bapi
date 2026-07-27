import datetime as dt

from pydantic import BaseModel


class SyncResult(BaseModel):
    status: str
    bapi_name: str
    records_synced: int
    started_at: dt.datetime
    finished_at: dt.datetime
    message: str | None = None


class MaterialSyncRequest(BaseModel):
    material_numbers: list[str]


class SalesOrderSyncRequest(BaseModel):
    customer_number: str | None = None
    sales_organization: str | None = None


class CustomerOut(BaseModel):
    kunnr: str
    name1: str | None = None
    city: str | None = None
    postal_code: str | None = None
    country: str | None = None
    region: str | None = None
    street: str | None = None
    telephone: str | None = None

    model_config = {"from_attributes": True}


class MaterialOut(BaseModel):
    matnr: str
    description: str | None = None
    material_type: str | None = None
    material_group: str | None = None
    base_uom: str | None = None
    industry_sector: str | None = None

    model_config = {"from_attributes": True}


class SalesOrderOut(BaseModel):
    vbeln: str
    doc_type: str | None = None
    doc_date: dt.date | None = None
    sold_to: str | None = None
    sales_org: str | None = None
    net_value: float | None = None
    currency: str | None = None

    model_config = {"from_attributes": True}


class GenericBAPIRequest(BaseModel):
    bapi_name: str
    params: dict = {}
