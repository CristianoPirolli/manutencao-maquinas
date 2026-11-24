"""Fixtures compartilhadas pelos testes.

O banco de testes é um SQLite temporário, configurado via ``DATABASE_URL``
**antes** de qualquer import do pacote ``backend`` (a engine é criada no import).
"""

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

_DIRETORIO_TEMP = Path(tempfile.mkdtemp(prefix="manutencao-testes-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_DIRETORIO_TEMP / 'teste.db').as_posix()}"
os.environ.setdefault("ADMIN_USERNAME", "admin")
os.environ.setdefault("ADMIN_INITIAL_PASSWORD", "admin123")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402

from backend.core.database import engine  # noqa: E402
from backend.main import app  # noqa: E402

ADMIN = ("admin", "admin123")


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Cliente HTTP com banco recriado do zero (dados demo + admin) a cada teste."""
    SQLModel.metadata.drop_all(engine)
    with TestClient(app) as cliente:  # O ``with`` dispara o lifespan (inicialização).
        yield cliente


def autenticar(client: TestClient, username: str, senha: str) -> dict:
    """Faz login e devolve o corpo de ``/token``."""
    response = client.post("/token", data={"username": username, "password": senha})
    assert response.status_code == 200, response.text
    return response.json()


def bearer(tokens: dict) -> dict[str, str]:
    """Monta o cabeçalho Authorization a partir do corpo de ``/token``."""
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture
def admin_headers(client: TestClient) -> dict[str, str]:
    """Cabeçalhos de um administrador autenticado."""
    return bearer(autenticar(client, *ADMIN))


@pytest.fixture
def usuario_headers(client: TestClient) -> dict[str, str]:
    """Cabeçalhos de um usuário comum recém-cadastrado e autenticado."""
    response = client.post("/usuarios", json={"username": "operador", "senha": "senha123"})
    assert response.status_code == 201, response.text
    return bearer(autenticar(client, "operador", "senha123"))
