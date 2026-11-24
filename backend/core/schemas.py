"""Schemas genéricos compartilhados por vários apps."""

from sqlmodel import SQLModel


class MensagemResponse(SQLModel):
    """Resposta simples contendo apenas uma mensagem legível."""

    mensagem: str


class StatusAPIResponse(SQLModel):
    """Resposta do health check em ``GET /``."""

    mensagem: str
    versao: str
