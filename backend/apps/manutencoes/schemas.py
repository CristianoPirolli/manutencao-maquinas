"""Contratos de saída do app de manutenções.

A entrada (``POST``/``PUT``) usa :class:`backend.apps.manutencoes.models.ManutencaoBase`.
"""

from datetime import date
from decimal import Decimal

from sqlmodel import SQLModel


class ManutencaoBuscaItem(SQLModel):
    """Item das listagens (o ``id`` é a chave do dicionário de resposta)."""

    maquina: str
    tipo: str
    data_manutencao: date
    custo: Decimal
    horas_paradas: Decimal


class ManutencaoSaida(ManutencaoBuscaItem):
    """Manutenção completa, incluindo o ``id``."""

    id: int


class ManutencaoOperacaoResponse(SQLModel):
    """Confirmação de criação ou alteração."""

    mensagem: str
    manutencao: ManutencaoSaida


class QuantidadeManutencoesResponse(SQLModel):
    """Total de manutenções cadastradas."""

    quantidade_total: int


class ResumoCustosResponse(SQLModel):
    """Indicadores agregados de custo e indisponibilidade."""

    custo_total: Decimal
    horas_paradas_total: Decimal
    moeda: str
