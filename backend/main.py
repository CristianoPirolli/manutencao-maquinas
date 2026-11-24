"""Ponto de entrada da API.

Execução (a partir da raiz do repositório)::

    uvicorn backend.main:app --reload

Documentação interativa: http://127.0.0.1:8000/docs
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.apps.auditoria.router import router as auditoria_router
from backend.apps.autenticacao.router import router as autenticacao_router
from backend.apps.maquinas.router import router as maquinas_router
from backend.apps.manutencoes.router import router as manutencoes_router
from backend.apps.usuarios.router import router as usuarios_router
from backend.core.compat import configurar_event_loop_windows
from backend.core.config import settings
from backend.core.inicializacao import inicializar_banco
from backend.core.schemas import StatusAPIResponse

configurar_event_loop_windows()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Prepara o banco antes de a API começar a aceitar requisições."""
    inicializar_banco()
    yield


def criar_app() -> FastAPI:
    """Fábrica da aplicação: configura middlewares e registra os apps."""
    aplicacao = FastAPI(
        title=settings.nome_api,
        description=(
            "FastAPI + SQLModel + SQLite + OAuth2 Password Flow + JWT + Scopes "
            "+ Refresh Tokens + Sessões + Auditoria"
        ),
        version=settings.versao_api,
        lifespan=lifespan,
    )

    aplicacao.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origens),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    aplicacao.include_router(autenticacao_router)
    aplicacao.include_router(usuarios_router)
    aplicacao.include_router(maquinas_router)
    aplicacao.include_router(manutencoes_router)
    aplicacao.include_router(auditoria_router)

    @aplicacao.get("/", response_model=StatusAPIResponse, tags=["Status"])
    def home():
        """Health check usado pelo frontend para exibir o status da API."""
        return {"mensagem": "API está no ar!", "versao": "9"}

    return aplicacao


app = criar_app()
