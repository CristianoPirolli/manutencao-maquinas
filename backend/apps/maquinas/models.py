"""Modelo persistente de máquinas.

Tabela ``maquina``:

=====  ============  ==========================================================
Campo  Tipo          Regra
=====  ============  ==========================================================
id     INTEGER       Chave primária
nome   VARCHAR(100)  Obrigatório e único (sem diferenciar maiúsculas/minúsculas)
setor  VARCHAR(60)   Opcional (ex.: Preparação de massa, Acabamento)
=====  ============  ==========================================================
"""

from pydantic import field_validator
from sqlmodel import Field, SQLModel


class MaquinaBase(SQLModel):
    """Campos editáveis de uma máquina; também é o schema de entrada da API."""

    nome: str = Field(min_length=1, max_length=100)
    setor: str | None = Field(default=None, max_length=60)

    @field_validator("nome")
    @classmethod
    def validar_nome(cls, valor: str) -> str:
        """Remove espaços das pontas e rejeita nomes vazios."""
        valor = valor.strip()
        if not valor:
            raise ValueError("O nome da máquina não pode ficar vazio ou conter apenas espaços.")
        return valor

    @field_validator("setor")
    @classmethod
    def normalizar_setor(cls, valor: str | None) -> str | None:
        """Converte setor em branco para ``None``."""
        if valor is None:
            return None
        return valor.strip() or None


class Maquina(MaquinaBase, table=True):
    """Tabela ``maquina``."""

    id: int | None = Field(default=None, primary_key=True)
    nome: str = Field(min_length=1, max_length=100, unique=True, index=True)
