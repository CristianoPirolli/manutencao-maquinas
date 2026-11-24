"""Endpoints do app de auditoria."""

from fastapi import APIRouter, Query, Security

from backend.apps.auditoria import service
from backend.apps.auditoria.schemas import AuditoriaSaida
from backend.apps.autenticacao.dependencies import UsuarioAtual, obter_usuario_atual
from backend.core.database import SessionDep

router = APIRouter(prefix="/auditoria", tags=["Auditoria"])


@router.get("", response_model=list[AuditoriaSaida])
def listar_auditoria(
    session: SessionDep,
    limite: int = Query(100, ge=1, le=500, description="Quantidade máxima de registros"),
    _usuario: UsuarioAtual = Security(obter_usuario_atual, scopes=["auditoria:read"]),
):
    """Lista os registros de auditoria mais recentes (somente administradores)."""
    return service.listar_ultimos(session, limite)
