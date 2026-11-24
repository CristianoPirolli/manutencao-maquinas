"""Contratos de saída do app de máquinas.

A entrada (``POST``/``PUT``) usa :class:`backend.apps.maquinas.models.MaquinaBase`.
"""

from decimal import Decimal

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


class IndicadoresMaquina(SQLModel):
    """MTTR, MTBF e disponibilidade de uma máquina.

    Os indicadores ficam ``null`` quando não há falhas suficientes: o MTTR
    precisa de uma corretiva; o MTBF e a disponibilidade, de duas.
    """

    maquina_id: int
    maquina: str
    setor: str | None
    falhas: int
    mttr_horas: Decimal | None
    mtbf_horas: Decimal | None
    disponibilidade: Decimal | None
