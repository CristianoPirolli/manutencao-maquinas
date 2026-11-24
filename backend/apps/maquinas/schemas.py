"""Contratos de saída do app de máquinas.

A entrada (``POST``/``PUT``) usa :class:`backend.apps.maquinas.models.MaquinaBase`.
"""

from sqlmodel import SQLModel


class MaquinaSaida(SQLModel):
    """Máquina com a quantidade de manutenções registradas para ela."""

    id: int
    nome: str
    setor: str | None
    total_manutencoes: int


class MaquinaOperacaoResponse(SQLModel):
    """Confirmação de criação ou alteração."""

    mensagem: str
    maquina: MaquinaSaida
