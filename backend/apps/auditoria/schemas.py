"""Contratos de saída do app de auditoria."""

from datetime import datetime

from sqlmodel import SQLModel


class AuditoriaSaida(SQLModel):
    """Representação pública de um :class:`LogAuditoria`."""

    id: int
    usuario: str
    operacao: str
    recurso: str
    recurso_id: int | None
    data_hora: datetime
    resultado: str
    detalhes: str | None
