"""Modelo persistente de refresh tokens / sessões."""

from sqlmodel import Field, SQLModel


class RefreshToken(SQLModel, table=True):
    """Refresh token emitido para uma sessão.

    Uma *sessão* (``sessao_id``) nasce no login e sobrevive às renovações:
    cada ``/refresh`` revoga o token atual e cria outro com o mesmo
    ``sessao_id`` (rotação). Logout e timeout revogam todos os tokens da sessão.

    Os instantes são guardados como *epoch* em segundos (UTC).
    """

    id: int | None = Field(default=None, primary_key=True)
    usuario_id: int = Field(foreign_key="usuario.id", index=True)
    sessao_id: str = Field(index=True)
    token_hash: str = Field(index=True, unique=True)  # SHA-256 do token bruto.
    criado_em: int
    expira_em: int
    ultima_atividade: int  # Base do timeout por inatividade.
    revogado: bool = Field(default=False)
    # Preserva o conjunto de scopes concedido no login durante cada rotação.
    scopes: str = Field(default="")
