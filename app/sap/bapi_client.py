import logging
from contextlib import contextmanager
from typing import Any, Iterator

from app.config import Settings
from app.sap.exceptions import BAPIExecutionError
from app.sap.mock_client import MockSAPConnection

logger = logging.getLogger(__name__)

_ERROR_TYPES = {"E", "A"}


class BAPIClient:
    """High-level façade over SAP BAPI calls.

    Talks to a real SAP system through pyrfc when SAP_MOCK_MODE=false, or to
    an in-memory fake (app.sap.mock_client) otherwise. Callers never touch
    the raw RFC connection - they get plain Python dicts/lists shaped like
    the middleware's Postgres tables.
    """

    def __init__(self, settings: Settings):
        self._settings = settings
        self._mock = MockSAPConnection() if settings.sap_mock_mode else None
        self._pool = None
        if not settings.sap_mock_mode:
            from app.sap.connection import SAPConnectionManager

            self._pool = SAPConnectionManager(settings)

    @contextmanager
    def _connection(self) -> Iterator[Any]:
        if self._mock is not None:
            yield self._mock
        else:
            with self._pool.get_connection() as conn:
                yield conn

    def call(self, bapi_name: str, **params) -> dict:
        with self._connection() as conn:
            result = conn.call(bapi_name, **params)
        self._raise_on_error(bapi_name, result)
        return result

    @staticmethod
    def _raise_on_error(bapi_name: str, result: dict) -> None:
        ret = result.get("RETURN")
        if not ret:
            return
        messages = [ret] if isinstance(ret, dict) else ret
        errors = [m for m in messages if m.get("TYPE") in _ERROR_TYPES]
        if errors:
            raise BAPIExecutionError(bapi_name, errors)

    # -- Customers -----------------------------------------------------

    def get_customers(self, max_rows: int = 100) -> list[dict]:
        result = self.call("BAPI_CUSTOMER_GETLIST", MAXROWS=max_rows)
        return [
            {
                "kunnr": row["CUSTOMER"],
                "name1": row.get("NAME"),
                "city": row.get("CITY"),
                "postal_code": row.get("POSTL_COD1"),
                "country": row.get("COUNTRY"),
                "region": row.get("REGION"),
                "street": row.get("STREET"),
                "telephone": row.get("TEL_NUMBER"),
            }
            for row in result.get("ADDRESSDATA", [])
        ]

    # -- Materials -------------------------------------------------------

    def get_material_details(self, material_numbers: list[str]) -> list[dict]:
        materials = []
        for matnr in material_numbers:
            result = self.call("BAPI_MATERIAL_GET_DETAIL", MATERIAL=matnr)
            data = result.get("MATERIAL_GENERAL_DATA")
            if not data:
                continue
            materials.append(
                {
                    "matnr": data["MATERIAL"],
                    "description": data.get("MATL_DESC"),
                    "material_type": data.get("MATL_TYPE"),
                    "material_group": data.get("MATL_GROUP"),
                    "base_uom": data.get("BASE_UOM"),
                    "industry_sector": data.get("IND_SECTOR"),
                }
            )
        return materials

    # -- Sales orders ------------------------------------------------------

    def get_sales_orders(
        self, customer_number: str | None = None, sales_organization: str | None = None
    ) -> tuple[list[dict], list[dict]]:
        list_result = self.call(
            "BAPI_SALESORDER_GETLIST",
            CUSTOMER_NUMBER=customer_number or "",
            SALES_ORGANIZATION=sales_organization or "",
        )
        doc_numbers = [row["DOC_NUMBER"] for row in list_result.get("SALES_ORDERS", [])]
        if not doc_numbers:
            return [], []

        detail_result = self.call(
            "BAPI_SALESORDER_GETDETAILEDLIST",
            SALES_DOCUMENTS=[{"DOC_NUMBER": doc} for doc in doc_numbers],
        )

        headers = [
            {
                "vbeln": row["DOC_NUMBER"],
                "doc_type": row.get("DOC_TYPE"),
                "doc_date": _parse_sap_date(row.get("DOC_DATE")),
                "sold_to": row.get("SOLD_TO"),
                "sales_org": row.get("SALES_ORG"),
                "distr_channel": row.get("DISTR_CHAN"),
                "division": row.get("DIVISION"),
                "net_value": _to_decimal(row.get("NET_VALUE")),
                "currency": row.get("CURRENCY"),
            }
            for row in detail_result.get("ORDER_HEADERS_OUT", [])
        ]
        items = [
            {
                "vbeln": row["DOC_NUMBER"],
                "posnr": row["ITM_NUMBER"],
                "matnr": row.get("MATERIAL"),
                "quantity": _to_decimal(row.get("REQ_QTY")),
                "uom": row.get("SALES_UNIT"),
                "net_value": _to_decimal(row.get("NET_VALUE")),
                "plant": row.get("PLANT"),
            }
            for row in detail_result.get("ORDER_ITEMS_OUT", [])
        ]
        return headers, items

    def create_sales_order(
        self, header: dict, items: list[dict], partners: list[dict] | None = None
    ) -> str:
        """Creates a sales order via BAPI_SALESORDER_CREATEFROMDAT2 and commits it.

        Rolls back the SAP LUW if creation fails or the BAPI reports errors.
        """
        with self._connection() as conn:
            result = conn.call(
                "BAPI_SALESORDER_CREATEFROMDAT2",
                ORDER_HEADER_IN=header,
                ORDER_ITEMS_IN=items,
                ORDER_PARTNERS=partners or [],
            )
            try:
                self._raise_on_error("BAPI_SALESORDER_CREATEFROMDAT2", result)
            except BAPIExecutionError:
                conn.call("BAPI_TRANSACTION_ROLLBACK")
                raise
            conn.call("BAPI_TRANSACTION_COMMIT", WAIT="X")
        return result["SALESDOCUMENT"]

    def close(self) -> None:
        if self._pool is not None:
            self._pool.close_all()


def _parse_sap_date(value: str | None):
    if not value:
        return None
    try:
        import datetime as dt

        return dt.datetime.strptime(value, "%Y%m%d").date()
    except ValueError:
        return None


def _to_decimal(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
