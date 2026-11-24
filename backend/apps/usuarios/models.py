"""Modelo persistente de usuários."""

from sqlmodel import Field, SQLModel

from backend.core.security import PERFIL_USUARIO


class Usuario(SQLModel, table=True):
    """Conta de acesso ao sistema.

    A senha nunca é armazenada em texto puro; apenas o hash Argon2.
    O campo ``role`` define o conjunto de scopes que a conta pode receber.
    """

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True, min_length=3, max_length=50)
    senha_hash: str
    role: str = Field(default=PERFIL_USUARIO)
