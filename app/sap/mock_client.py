"""Fake SAP RFC backend used when SAP_MOCK_MODE=true.

Mimics the subset of pyrfc.Connection.call() behaviour the middleware relies
on, so app/sap/bapi_client.py can talk to it identically to a real RFC
connection. This lets the whole app (API, sync jobs, Postgres writes) run
and be demoed/tested without network access to an SAP system.
"""

import datetime as dt
import logging

logger = logging.getLogger(__name__)

_CUSTOMERS = [
    {
        "CUSTOMER": f"{100000 + i:010d}",
        "NAME": name,
        "CITY": city,
        "POSTL_COD1": postal,
        "COUNTRY": "US",
        "REGION": region,
        "STREET": street,
        "TEL_NUMBER": phone,
    }
    for i, (name, city, postal, region, street, phone) in enumerate(
        [
            ("Acme Corp", "New York", "10001", "NY", "5th Avenue 1", "212-555-0100"),
            ("Globex Inc", "Chicago", "60601", "IL", "Wacker Dr 200", "312-555-0101"),
            ("Initech LLC", "Austin", "73301", "TX", "Congress Ave 55", "512-555-0102"),
            ("Umbrella Trading", "Seattle", "98101", "WA", "Pine St 10", "206-555-0103"),
            ("Wayne Enterprises", "Gotham", "07001", "NJ", "Founders Way 1", "973-555-0104"),
        ]
    )
]

_MATERIAL_TYPES = ["FERT", "ROH", "HALB", "HAWA"]


def _fake_material(matnr: str) -> dict:
    return {
        "MATERIAL": matnr,
        "MATL_DESC": f"Sample material {matnr}",
        "IND_SECTOR": "M",
        "MATL_TYPE": _MATERIAL_TYPES[hash(matnr) % len(_MATERIAL_TYPES)],
        "MATL_GROUP": "GEN-01",
        "BASE_UOM": "EA",
    }


def _fake_order_header(sd_doc: str) -> dict:
    idx = int(sd_doc[-4:]) if sd_doc[-4:].isdigit() else 0
    customer = _CUSTOMERS[idx % len(_CUSTOMERS)]
    return {
        "DOC_NUMBER": sd_doc,
        "DOC_TYPE": "OR",
        "DOC_DATE": (dt.date.today() - dt.timedelta(days=idx)).strftime("%Y%m%d"),
        "SOLD_TO": customer["CUSTOMER"],
        "SALES_ORG": "1000",
        "DISTR_CHAN": "10",
        "DIVISION": "00",
        "NET_VALUE": f"{1000 + idx * 137.5:.2f}",
        "CURRENCY": "USD",
    }


def _fake_order_items(sd_doc: str) -> list[dict]:
    items = []
    for pos in range(1, 3):
        matnr = f"MAT-{(hash(sd_doc + str(pos)) % 900 + 100)}"
        items.append(
            {
                "DOC_NUMBER": sd_doc,
                "ITM_NUMBER": f"{pos * 10:06d}",
                "MATERIAL": matnr,
                "REQ_QTY": f"{pos * 5}.000",
                "SALES_UNIT": "EA",
                "NET_VALUE": f"{pos * 250.00:.2f}",
                "PLANT": "1000",
            }
        )
    return items


class MockSAPConnection:
    """Drop-in stand-in for pyrfc.Connection limited to `.call()`."""

    alive = True

    def call(self, function_name: str, **params) -> dict:
        logger.debug("MOCK RFC call: %s(%s)", function_name, params)
        handler = getattr(self, f"_{function_name.lower()}", None)
        if handler is None:
            logger.warning("Mock RFC has no handler for %s, returning empty RETURN", function_name)
            return {"RETURN": []}
        return handler(**params)

    def close(self) -> None:  # pragma: no cover - nothing to release
        pass

    # -- BAPI handlers -----------------------------------------------------

    def _bapi_customer_getlist(self, MAXROWS: int = 100, **_) -> dict:
        rows = _CUSTOMERS[: int(MAXROWS)] if MAXROWS else _CUSTOMERS
        return {"ADDRESSDATA": rows, "RETURN": []}

    def _bapi_material_get_detail(self, MATERIAL: str, **_) -> dict:
        return {"MATERIAL_GENERAL_DATA": _fake_material(MATERIAL), "RETURN": []}

    def _bapi_salesorder_getlist(
        self, CUSTOMER_NUMBER: str = "", SALES_ORGANIZATION: str = "", **_
    ) -> dict:
        count = 5
        docs = [{"DOC_NUMBER": f"{4500000000 + i:010d}"} for i in range(count)]
        return {"SALES_ORDERS": docs, "RETURN": []}

    def _bapi_salesorder_getdetailedlist(self, SALES_DOCUMENTS: list | None = None, **_) -> dict:
        doc_numbers = [d.get("DOC_NUMBER") if isinstance(d, dict) else d for d in (SALES_DOCUMENTS or [])]
        headers = [_fake_order_header(doc) for doc in doc_numbers]
        items = [item for doc in doc_numbers for item in _fake_order_items(doc)]
        return {"ORDER_HEADERS_OUT": headers, "ORDER_ITEMS_OUT": items, "RETURN": []}

    def _bapi_salesorder_createfromdat2(self, ORDER_HEADER_IN: dict, **_) -> dict:
        new_doc = f"{4600000000 + abs(hash(str(ORDER_HEADER_IN))) % 9999:010d}"
        return {"SALESDOCUMENT": new_doc, "RETURN": []}

    def _bapi_transaction_commit(self, **_) -> dict:
        return {"RETURN": []}

    def _bapi_transaction_rollback(self, **_) -> dict:
        return {"RETURN": []}
