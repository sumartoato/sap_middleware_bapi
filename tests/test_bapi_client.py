from app.config import get_settings
from app.sap.bapi_client import BAPIClient


def _client() -> BAPIClient:
    return BAPIClient(get_settings())


def test_get_customers_returns_mapped_rows():
    customers = _client().get_customers(max_rows=2)
    assert len(customers) == 2
    assert set(customers[0]) == {
        "kunnr",
        "name1",
        "city",
        "postal_code",
        "country",
        "region",
        "street",
        "telephone",
    }


def test_get_material_details_maps_fields():
    materials = _client().get_material_details(["MAT-100", "MAT-200"])
    assert [m["matnr"] for m in materials] == ["MAT-100", "MAT-200"]
    assert all(m["description"] for m in materials)


def test_get_sales_orders_returns_headers_and_items():
    headers, items = _client().get_sales_orders(customer_number="1000000000")
    assert len(headers) == 5
    assert all(h["vbeln"] for h in headers)
    assert items
    assert all(i["vbeln"] in {h["vbeln"] for h in headers} for i in items)


def test_create_sales_order_commits_and_returns_doc_number():
    doc_number = _client().create_sales_order(
        header={"DOC_TYPE": "OR", "SALES_ORG": "1000"},
        items=[{"MATERIAL": "MAT-100", "TARGET_QTY": "1"}],
    )
    assert doc_number
