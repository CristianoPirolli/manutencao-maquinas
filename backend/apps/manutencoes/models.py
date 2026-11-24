"""Modelo de domínio de manutenções de máquinas.

MER da tabela ``manutencao`` (substitui a tabela ``venda`` do roteiro original):

==================  ===============  ===========================================
Campo               Tipo             Regra
==================  ===============  ===========================================
id                  INTEGER          Chave primária
maquina             VARCHAR(100)     Obrigatório, não pode ser só espaços
tipo                VARCHAR          preventiva, corretiva ou preditiva
data_manutencao     DATE             Não pode estar no futuro
custo               NUMERIC(10,2)    Maior que zero
horas_paradas       NUMERIC(6,1)     Zero ou mais
==================  ===============  ===========================================
"""

from datetime import date
from decimal import Decimal
from typing import Literal, get_args

from pydantic import field_validator
from sqlalchemy import String
from sqlmodel import Field, SQLModel

TipoManutencao = Literal["preventiva", "corretiva", "preditiva"]

#: Tupla com os tipos válidos, derivada do ``Literal`` para não haver duplicação.
TIPOS_MANUTENCAO: tuple[str, ...] = get_args(TipoManutencao)

_CENTAVOS = Decimal("0.01")
_DECIMO = Decimal("0.1")


class ManutencaoBase(SQLModel):
    """Campos e validações de uma manutenção.

    Serve tanto de base para a tabela quanto de schema de entrada para
    ``POST`` e ``PUT``, garantindo que as mesmas regras valham nos dois casos.
    """

    maquina: str = Field(min_length=1, max_length=100)
    tipo: TipoManutencao = Field(sa_type=String)
    data_manutencao: date
    custo: Decimal = Field(gt=Decimal("0"), max_digits=10, decimal_places=2)
    horas_paradas: Decimal = Field(ge=Decimal("0"), max_digits=6, decimal_places=1)

    @field_validator("maquina")
    @classmethod
    def validar_maquina(cls, valor: str) -> str:
        """Remove espaços das pontas e rejeita nomes vazios."""
        valor = valor.strip()
        if not valor:
            raise ValueError("O nome da máquina não pode ficar vazio ou conter apenas espaços.")
        return valor

    @field_validator("tipo", mode="before")
    @classmethod
    def normalizar_tipo(cls, valor: object) -> object:
        """Aceita o tipo com qualquer capitalização (ex.: ``Corretiva``)."""
        if isinstance(valor, str):
            return valor.strip().lower()
        return valor

    @field_validator("custo")
    @classmethod
    def arredondar_custo(cls, valor: Decimal) -> Decimal:
        """Normaliza o custo para duas casas decimais."""
        return valor.quantize(_CENTAVOS)

    @field_validator("horas_paradas")
    @classmethod
    def arredondar_horas(cls, valor: Decimal) -> Decimal:
        """Normaliza as horas paradas para uma casa decimal."""
        return valor.quantize(_DECIMO)

    @field_validator("data_manutencao")
    @classmethod
    def validar_data(cls, valor: date) -> date:
        """Impede o registro de manutenções com data futura."""
        if valor > date.today():
            raise ValueError("A data da manutenção não pode estar no futuro.")
        return valor


class Manutencao(ManutencaoBase, table=True):
    """Tabela ``manutencao``."""

    id: int | None = Field(default=None, primary_key=True)
