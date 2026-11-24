"""Primitivas de segurança: hash de senha, scopes, JWT e refresh tokens.

Este módulo não conhece rotas nem banco de dados; ele apenas oferece funções
puras reutilizadas pelos apps ``autenticacao`` e ``usuarios``.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import HTTPException, status
from pwdlib import PasswordHash

from backend.core.config import settings

# --------------------------------------------------------------------------- #
# Perfis e scopes (OAuth2)
# --------------------------------------------------------------------------- #

PERFIL_ADMIN = "admin"
PERFIL_USUARIO = "usuario"

#: Catálogo de scopes exibido no Swagger e usado para validar os tokens.
SCOPES: dict[str, str] = {
    "manutencoes:read": "Consultar manutenções",
    "manutencoes:create": "Registrar manutenções",
    "manutencoes:update": "Alterar manutenções",
    "manutencoes:delete": "Excluir manutenções",
    "auditoria:read": "Consultar registros de auditoria",
}

#: Scopes do perfil comum: pode consultar, criar e alterar, mas não excluir
#: nem consultar a auditoria.
_SCOPES_USUARIO_COMUM = ["manutencoes:read", "manutencoes:create", "manutencoes:update"]


def scopes_do_usuario(role: str) -> list[str]:
    """Retorna todos os scopes que um perfil pode receber."""
    if role == PERFIL_ADMIN:
        return list(SCOPES)

    return list(_SCOPES_USUARIO_COMUM)


def scopes_para_token(role: str, solicitados: list[str]) -> list[str]:
    """Define os scopes que irão no token emitido no login.

    Se o cliente não pedir scopes, recebe todos os permitidos ao perfil. Se
    pedir algum scope que o perfil não possui, o login é recusado com 400.
    """
    permitidos = set(scopes_do_usuario(role))
    pedidos = set(solicitados)

    if not pedidos:
        return sorted(permitidos)

    negados = pedidos - permitidos
    if negados:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Escopos não permitidos para este perfil: "
                f"{', '.join(sorted(negados))}"
            ),
        )

    return sorted(pedidos)


# --------------------------------------------------------------------------- #
# Senhas
# --------------------------------------------------------------------------- #

#: Hasher recomendado pelo pwdlib (Argon2id).
password_hash = PasswordHash.recommended()


def gerar_hash_senha(senha: str) -> str:
    """Gera o hash Argon2 de uma senha em texto puro."""
    return password_hash.hash(senha)


def verificar_senha(senha: str, senha_hash: str) -> bool:
    """Confere uma senha em texto puro contra o hash armazenado."""
    return password_hash.verify(senha, senha_hash)


# --------------------------------------------------------------------------- #
# Access token (JWT)
# --------------------------------------------------------------------------- #


def criar_access_token(username: str, role: str, scopes: list[str], sessao_id: str) -> str:
    """Assina um JWT de curta duração com usuário, perfil, scopes e sessão.

    O claim ``sid`` amarra o token a uma sessão do servidor; assim, um logout
    ou timeout invalida também os access tokens ainda não expirados.
    """
    expiracao = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutos)

    payload = {
        "sub": username,
        "role": role,
        "scope": " ".join(scopes),
        "sid": sessao_id,
        "exp": expiracao,
    }

    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algoritmo)


def decodificar_access_token(token: str) -> dict[str, Any]:
    """Valida assinatura e expiração do JWT e devolve o payload.

    Propaga ``jwt.ExpiredSignatureError`` e ``jwt.InvalidTokenError`` para que
    o chamador decida como responder a cada caso.
    """
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algoritmo])


# --------------------------------------------------------------------------- #
# Refresh token (opaco)
# --------------------------------------------------------------------------- #


def gerar_refresh_token() -> str:
    """Gera um refresh token aleatório e opaco (não é JWT)."""
    return secrets.token_urlsafe(64)


def hash_refresh_token(token: str) -> str:
    """Calcula o SHA-256 do refresh token.

    Apenas o hash é persistido: um vazamento do banco não expõe tokens válidos.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
