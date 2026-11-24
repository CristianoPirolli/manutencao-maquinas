"""Contratos de entrada e saída do app de usuários."""

from __future__ import annotations

from pydantic import field_validator
from sqlmodel import Field, SQLModel


def normalizar_username(username: str) -> str:
    """Padroniza o login: sem espaços nas pontas e em minúsculas."""
    return username.strip().lower()


class UsuarioCadastro(SQLModel):
    """Dados enviados para criar uma conta comum."""

    username: str = Field(min_length=3, max_length=50)
    senha: str = Field(min_length=6)

    @field_validator("username", mode="before")
    @classmethod
    def validar_username(cls, valor: object) -> object:
        """Normaliza o login e rejeita valores vazios ou só com espaços."""
        if not isinstance(valor, str):
            return valor

        normalizado = normalizar_username(valor)
        if not normalizado:
            raise ValueError("O nome de usuário não pode ficar vazio ou conter apenas espaços.")

        return normalizado


class UsuarioCadastroResponse(SQLModel):
    """Confirmação de cadastro."""

    mensagem: str
    id: int
    username: str
    role: str


class UsuarioPerfil(SQLModel):
    """Perfil do usuário autenticado, com os scopes efetivos da sessão."""

    id: int
    username: str
    role: str
    scopes: list[str]
    sessao_id: str | None = None
