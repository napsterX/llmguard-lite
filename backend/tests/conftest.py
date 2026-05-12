from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_db():
    """Override get_db with a MagicMock session. Configure chained query methods
    to return sensible defaults so generic queries don't raise AttributeError."""
    db = MagicMock()

    db.query.return_value.count.return_value = 0
    db.query.return_value.all.return_value = []
    db.query.return_value.first.return_value = None
    db.query.return_value.filter.return_value.count.return_value = 0
    db.query.return_value.filter.return_value.all.return_value = []
    db.query.return_value.filter.return_value.first.return_value = None
    db.query.return_value.filter.return_value.is_.return_value.count.return_value = 0
    db.query.return_value.order_by.return_value.count.return_value = 0
    db.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
    db.query.return_value.filter.return_value.order_by.return_value.count.return_value = 0
    db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
    db.query.return_value.filter.return_value.isnot.return_value.all.return_value = []

    def _override():
        yield db

    app.dependency_overrides[get_db] = _override
    yield db
    app.dependency_overrides.pop(get_db, None)
