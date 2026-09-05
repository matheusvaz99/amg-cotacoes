"""Configuracao de testes: banco SQLite temporario e TestClient."""

import os
import re
import tempfile

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("ADMIN_USER", "admin@amg.test")
os.environ.setdefault("ADMIN_PASS", "senha-teste")
os.environ.setdefault("RESEND_API_KEY", "")
os.environ.setdefault("BASE_URL", "http://testserver")
os.environ.setdefault("ENV", "dev")

_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.close(_db_fd)
os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402

CSRF_RE = re.compile(r'name="csrf_token" value="([^"]+)"')


@pytest.fixture(autouse=True)
def _fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def csrf_from(html: str) -> str:
    m = CSRF_RE.search(html)
    assert m, "csrf_token nao encontrado na pagina"
    return m.group(1)


def teardown_module():  # pragma: no cover
    try:
        os.unlink(_db_path)
    except OSError:
        pass
