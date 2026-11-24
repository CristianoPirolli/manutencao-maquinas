"""Contratos de entrada e saída do app de autenticação."""

from typing import Literal

from sqlmodel import Field, SQLModel

from backend.apps.usuarios.schemas import UsuarioPerfil


class TokenResponse(SQLModel):
    """Par de tokens devolvido por ``/token`` e ``/refresh``."""

    access_token: str
    refresh_token: str
    token_type: Literal["bearer"]
    expires_in: int  # Segundos até o access token expirar.
    refresh_expires_in: int  # Segundos até o refresh token expirar.
    session_idle_seconds: int  # Inatividade máxima tolerada pela sessão.
    usuario: UsuarioPerfil


class RefreshEntrada(SQLModel):
    """Corpo de ``/refresh`` e ``/logout``."""

    refresh_token: str = Field(min_length=1)
