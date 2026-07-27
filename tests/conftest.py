import os

os.environ.setdefault("SAP_MOCK_MODE", "true")
os.environ.setdefault("POSTGRES_DB", "sap_middleware_test")
os.environ.setdefault("API_KEY", "test-api-key")

import pytest

from app.config import get_settings
from app.db.database import Base, engine


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    get_settings.cache_clear()
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _clean_tables():
    yield
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
