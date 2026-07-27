from fastapi import APIRouter, Depends, HTTPException, Query, Request, Security
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.database import get_db
from app.db.models import Customer, Material, SalesOrder
from app.sap.bapi_client import BAPIClient
from app.sap.exceptions import BAPIExecutionError, SAPConnectionError
from app.services.sync_service import SyncService

from app.api.schemas import (
    CustomerOut,
    GenericBAPIRequest,
    MaterialOut,
    MaterialSyncRequest,
    SalesOrderOut,
    SalesOrderSyncRequest,
    SyncResult,
)

router = APIRouter()

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(
    api_key: str | None = Security(_api_key_header), settings: Settings = Depends(get_settings)
) -> None:
    if api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key header")


def get_bapi_client(request: Request) -> BAPIClient:
    return request.app.state.bapi_client


def get_sync_service(bapi_client: BAPIClient = Depends(get_bapi_client)) -> SyncService:
    return SyncService(bapi_client)


@router.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict:
    return {"status": "ok", "sap_mock_mode": settings.sap_mock_mode}


# -- Sync (SAP -> Postgres) ------------------------------------------------


@router.post("/sync/customers", response_model=SyncResult, dependencies=[Depends(require_api_key)])
def sync_customers(
    max_rows: int = Query(100, ge=1, le=1000), service: SyncService = Depends(get_sync_service)
):
    return service.sync_customers(max_rows=max_rows)


@router.post("/sync/materials", response_model=SyncResult, dependencies=[Depends(require_api_key)])
def sync_materials(body: MaterialSyncRequest, service: SyncService = Depends(get_sync_service)):
    if not body.material_numbers:
        raise HTTPException(status_code=422, detail="material_numbers must not be empty")
    return service.sync_materials(body.material_numbers)


@router.post(
    "/sync/sales-orders", response_model=SyncResult, dependencies=[Depends(require_api_key)]
)
def sync_sales_orders(
    body: SalesOrderSyncRequest, service: SyncService = Depends(get_sync_service)
):
    return service.sync_sales_orders(
        customer_number=body.customer_number, sales_organization=body.sales_organization
    )


@router.post("/bapi/call", dependencies=[Depends(require_api_key)])
def call_bapi(body: GenericBAPIRequest, client: BAPIClient = Depends(get_bapi_client)):
    """Escape hatch for calling any BAPI function directly. Guarded by API key."""
    try:
        return client.call(body.bapi_name, **body.params)
    except BAPIExecutionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except SAPConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


# -- Read stored data -------------------------------------------------------


@router.get("/customers", response_model=list[CustomerOut])
def list_customers(
    limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)
):
    return db.execute(select(Customer).limit(limit)).scalars().all()


@router.get("/materials", response_model=list[MaterialOut])
def list_materials(
    limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)
):
    return db.execute(select(Material).limit(limit)).scalars().all()


@router.get("/sales-orders", response_model=list[SalesOrderOut])
def list_sales_orders(
    limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)
):
    return db.execute(select(SalesOrder).limit(limit)).scalars().all()
