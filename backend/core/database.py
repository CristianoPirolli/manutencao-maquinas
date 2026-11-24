"""Conexão com o banco de dados e fábrica de sessões.

A engine é criada uma única vez por processo. As rotas recebem uma sessão por
requisição através da dependência :data:`SessionDep`, que garante o fechamento
da sessão ao final do request.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlmodel import Session, create_engine

from backend.core.config import settings

# ``check_same_thread=False`` é necessário porque o FastAPI executa rotas
# síncronas em um pool de threads, e a mesma conexão SQLite pode ser reutilizada.
_connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

engine = create_engine(settings.database_url, connect_args=_connect_args)


def get_session() -> Iterator[Session]:
    """Abre uma sessão para a requisição atual e a fecha ao final."""
    with Session(engine) as session:
        yield session


#: Atalho tipado para injetar a sessão nas rotas: ``session: SessionDep``.
SessionDep = Annotated[Session, Depends(get_session)]
