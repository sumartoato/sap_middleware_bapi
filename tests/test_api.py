from fastapi.testclient import TestClient

from app.main import app


def test_health():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["sap_mock_mode"] is True


def test_sync_requires_api_key():
    with TestClient(app) as client:
        response = client.post("/sync/customers")
    assert response.status_code == 401


def test_sync_customers_then_list():
    with TestClient(app) as client:
        sync_response = client.post(
            "/sync/customers", headers={"X-API-Key": "test-api-key"}
        )
        assert sync_response.status_code == 200
        assert sync_response.json()["status"] == "SUCCESS"

        list_response = client.get("/customers")
        assert list_response.status_code == 200
        assert len(list_response.json()) == sync_response.json()["records_synced"]
