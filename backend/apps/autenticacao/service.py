"""Regras de negócio de autenticação, sessões e rotação de refresh tokens."""

from __future__ import annotations

import time
from typing import NoReturn, TypedDict
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import update
from sqlmodel import Session, select

from backend.apps.auditoria.service import registrar_auditoria
from backend.apps.autenticacao.models import RefreshToken
from backend.apps.usuarios.models import Usuario
from backend.apps.usuarios.schemas import normalizar_username
from backend.apps.usuarios.service import buscar_por_username
from backend.core.config import settings
from backend.core.security import (
    criar_access_token,
    gerar_refresh_token,
    hash_refresh_token,
    scopes_do_usuario,
    scopes_para_token,
    verificar_senha,
)

_DESAFIO_BEARER = {"WWW-Authenticate": "Bearer"}


class UsuarioAtual(TypedDict):
    """Contexto do usuário autenticado repassado às rotas."""

    id: int
    username: str
    role: str
    scopes: list[str]
    sessao_id: str


# --------------------------------------------------------------------------- #
# Helpers internos
# --------------------------------------------------------------------------- #


def _recusar(
    session: Session,
    *,
    usuario: str,
    detalhes: str,
    detail: str,
    operacao: str = "REFRESH",
    recurso: str = "autenticacao",
    resultado: str = "negado",
) -> NoReturn:
    """Audita a recusa, persiste o log e interrompe com HTTP 401."""
    registrar_auditoria(usuario, operacao, recurso, resultado, detalhes=detalhes, session=session)
    session.commit()

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers=_DESAFIO_BEARER,
    )


def _novo_registro_refresh(
    usuario_id: int, sessao_id: str, scopes: list[str]
) -> tuple[str, RefreshToken]:
    """Cria um refresh token bruto e o registro (com hash) a ser persistido."""
    token = gerar_refresh_token()
    agora = int(time.time())

    registro = RefreshToken(
        usuario_id=usuario_id,
        sessao_id=sessao_id,
        token_hash=hash_refresh_token(token),
        criado_em=agora,
        expira_em=agora + settings.refresh_token_segundos,
        ultima_atividade=agora,
        revogado=False,
        scopes=" ".join(scopes),
    )

    return token, registro


def _emitir_par_tokens(
    session: Session, usuario: Usuario, scopes: list[str], sessao_id: str
) -> dict:
    """Gera access + refresh token e monta o corpo de :class:`TokenResponse`.

    O registro do refresh token é apenas adicionado à sessão; o chamador é
    responsável pelo ``commit``.
    """
    access_token = criar_access_token(usuario.username, usuario.role, scopes, sessao_id)
    refresh_token, registro = _novo_registro_refresh(usuario.id, sessao_id, scopes)
    session.add(registro)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.access_token_segundos,
        "refresh_expires_in": settings.refresh_token_segundos,
        "session_idle_seconds": settings.sessao_inatividade_segundos,
        "usuario": {
            "id": usuario.id,
            "username": usuario.username,
            "role": usuario.role,
            "scopes": scopes,
            "sessao_id": sessao_id,
        },
    }


# --------------------------------------------------------------------------- #
# Sessões
# --------------------------------------------------------------------------- #


def revogar_sessao(session: Session, sessao_id: str) -> int:
    """Revoga todos os refresh tokens ativos da sessão e retorna quantos foram."""
    registros = session.exec(
        select(RefreshToken).where(
            RefreshToken.sessao_id == sessao_id,
            RefreshToken.revogado == False,  # noqa: E712 - comparação SQL
        )
    ).all()

    for registro in registros:
        registro.revogado = True

    return len(registros)


def buscar_sessao_ativa(session: Session, sessao_id: str) -> RefreshToken | None:
    """Retorna o refresh token ativo mais recente da sessão, se houver."""
    return session.exec(
        select(RefreshToken)
        .where(
            RefreshToken.sessao_id == sessao_id,
            RefreshToken.revogado == False,  # noqa: E712 - comparação SQL
        )
        .order_by(RefreshToken.id.desc())
    ).first()


# --------------------------------------------------------------------------- #
# Casos de uso
# --------------------------------------------------------------------------- #


def login(session: Session, username: str, senha: str, scopes_solicitados: list[str]) -> dict:
    """Autentica usuário e senha e abre uma nova sessão.

    :raises HTTPException: 401 para credenciais inválidas; 400 se forem
        solicitados scopes que o perfil não possui.
    """
    username = normalizar_username(username)
    usuario = buscar_por_username(session, username)

    if usuario is None or not verificar_senha(senha, usuario.senha_hash):
        _recusar(
            session,
            usuario=username or "desconhecido",
            operacao="LOGIN",
            detalhes="Usuário ou senha inválidos",
            detail="Usuário ou senha inválidos",
        )

    scopes_concedidos = scopes_para_token(usuario.role, scopes_solicitados)
    sessao_id = uuid4().hex

    resposta = _emitir_par_tokens(session, usuario, scopes_concedidos, sessao_id)

    registrar_auditoria(
        usuario.username, "LOGIN", "autenticacao", "sucesso",
        detalhes=f"Login realizado; sessão {sessao_id}",
        session=session,
    )
    session.commit()

    return resposta


def renovar_tokens(session: Session, refresh_token: str) -> dict:
    """Troca um refresh token válido por um novo par (rotação).

    Regras aplicadas, nesta ordem:

    1. O token precisa existir, não estar revogado e não estar expirado.
    2. A sessão não pode ter ultrapassado o limite de inatividade.
    3. O usuário ainda precisa existir.
    4. Os scopes são recalculados: interseção entre os concedidos no login e
       os permitidos hoje ao perfil (rebaixar um perfil reduz permissões).
    5. A revogação do token antigo é feita com ``UPDATE ... WHERE revogado =
       false``; se duas requisições usarem o mesmo token ao mesmo tempo,
       apenas uma vence (proteção contra *replay*).
    """
    token_hash = hash_refresh_token(refresh_token)
    agora = int(time.time())
    limite_inatividade = settings.sessao_inatividade_segundos

    registro = session.exec(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    ).first()

    if registro is None:
        _recusar(
            session, usuario="desconhecido",
            detalhes="Refresh token não encontrado",
            detail="Refresh token inválido",
        )

    usuario_db = session.get(Usuario, registro.usuario_id)
    username = usuario_db.username if usuario_db is not None else "desconhecido"

    if registro.revogado:
        # Reuso de token já rotacionado indica possível vazamento: encerra a
        # sessão inteira, invalidando também o token emitido na rotação
        # (detecção de reuso recomendada pela RFC 6819 / OAuth 2.0 BCP).
        if registro.sessao_id:
            revogar_sessao(session, registro.sessao_id)
        _recusar(
            session, usuario=username,
            detalhes="Refresh token revogado ou já utilizado",
            detail="Refresh token revogado ou já utilizado",
        )

    if registro.expira_em <= agora:
        revogar_sessao(session, registro.sessao_id)
        _recusar(
            session, usuario=username,
            detalhes="Refresh token expirado",
            detail="Refresh token expirado",
        )

    if not registro.sessao_id:
        _recusar(
            session, usuario=username,
            detalhes="Sessão sem identificador válido",
            detail="Sessão inválida",
        )

    if agora - registro.ultima_atividade >= limite_inatividade:
        revogar_sessao(session, registro.sessao_id)
        _recusar(
            session, usuario=username,
            operacao="SESSION_TIMEOUT", recurso="sessao", resultado="encerrada",
            detalhes="Refresh recusado após inatividade",
            detail="Sessão encerrada por inatividade",
        )

    if usuario_db is None:
        revogar_sessao(session, registro.sessao_id)
        _recusar(
            session, usuario=username,
            detalhes="Usuário do refresh token não encontrado",
            detail="Usuário não encontrado",
        )

    scopes_atuais = set(scopes_do_usuario(usuario_db.role))
    scopes_guardados = set(registro.scopes.split())
    # Tokens antigos sem scopes registrados recebem apenas os permitidos hoje
    # ao perfil; tokens atuais mantêm o conjunto originalmente concedido.
    scopes_efetivos = (scopes_guardados or scopes_atuais) & scopes_atuais

    if not scopes_efetivos:
        _recusar(
            session, usuario=username,
            detalhes="Nenhum scope válido para renovar",
            detail="Nenhum escopo válido para renovar a sessão",
        )

    sessao_id = registro.sessao_id

    # Revogação condicional e atômica do token usado (ver regra 5).
    resultado = session.exec(
        update(RefreshToken)
        .where(
            RefreshToken.id == registro.id,
            RefreshToken.revogado == False,  # noqa: E712 - comparação SQL
            RefreshToken.expira_em > agora,
            RefreshToken.ultima_atividade > agora - limite_inatividade,
        )
        .values(revogado=True)
    )

    if resultado.rowcount != 1:
        session.rollback()
        # Uso simultâneo do mesmo token também é tratado como reuso: a sessão
        # inteira é revogada, e a auditoria vai na mesma transação.
        revogar_sessao(session, sessao_id)
        registrar_auditoria(
            username, "REFRESH", "autenticacao", "negado",
            detalhes="Refresh token usado simultaneamente ou inválido; sessão revogada",
            session=session,
        )
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token já utilizado ou inválido",
            headers=_DESAFIO_BEARER,
        )

    resposta = _emitir_par_tokens(session, usuario_db, sorted(scopes_efetivos), sessao_id)

    registrar_auditoria(
        usuario_db.username, "REFRESH", "autenticacao", "sucesso",
        detalhes=f"Refresh rotacionado na sessão {sessao_id}",
        session=session,
    )
    session.commit()

    return resposta


def logout(session: Session, refresh_token: str) -> None:
    """Encerra a sessão ligada ao refresh token, revogando todos os seus tokens.

    É idempotente: um token desconhecido ou já revogado não gera erro, apenas
    um registro de auditoria com resultado ``ignorado``.
    """
    token_hash = hash_refresh_token(refresh_token)
    registro = session.exec(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    ).first()

    usuario_nome = "desconhecido"
    tokens_revogados = 0

    if registro is not None:
        usuario_db = session.get(Usuario, registro.usuario_id)
        if usuario_db is not None:
            usuario_nome = usuario_db.username
        if registro.sessao_id:
            tokens_revogados = revogar_sessao(session, registro.sessao_id)

    sessao_encerrada = tokens_revogados > 0

    registrar_auditoria(
        usuario_nome, "LOGOUT", "autenticacao",
        "sucesso" if sessao_encerrada else "ignorado",
        detalhes=(
            "Sessão encerrada"
            if sessao_encerrada
            else "Refresh token não encontrado ou sem sessão"
        ),
        session=session,
    )
    session.commit()
