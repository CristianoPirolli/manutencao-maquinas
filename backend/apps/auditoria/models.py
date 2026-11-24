"""Modelo persistente da trilha de auditoria."""

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class LogAuditoria(SQLModel, table=True):
    """Registro imutável de uma operação (login, CRUD, acesso negado, etc.)."""

    id: int | None = Field(default=None, primary_key=True)
    usuario: str = Field(index=True)
    operacao: str  # Ex.: LOGIN, REFRESH, CREATE, UPDATE, DELETE, SESSION_TIMEOUT.
    recurso: str  # Ex.: autenticacao, manutencao, usuario ou o path HTTP.
    recurso_id: int | None = None
    data_hora: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resultado: str  # sucesso, negado, falha, encerrada ou ignorado.
    detalhes: str | None = None
