"""Dependências FastAPI de autenticação e autorização por scopes.

Uso típico nas rotas::

    @router.get("/recurso")
    def rota(usuario: UsuarioAtual = Security(obter_usuario_atual, scopes=["x:read"])):
        ...
"""

from __future__ import annotations

import time
from typing import NoReturn

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from sqlmodel import Session, select

from backend.apps.auditoria.service import registrar_auditoria
from backend.apps.autenticacao.service import (
    UsuarioAtual,
    buscar_sessao_ativa,
    revogar_sessao,
)
from backend.apps.usuarios.models import Usuario
from backend.core.config import settings
from backend.core.database import get_session
from backend.core.security import SCOPES, decodificar_access_token, scopes_do_usuario

__all__ = ["UsuarioAtual", "obter_usuario_atual", "oauth2_scheme"]

# ``auto_error=False`` permite auditar a ausência de token antes de responder.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", scopes=SCOPES, auto_error=False)


def _desafio_bearer(security_scopes: SecurityScopes) -> str:
    """Monta o cabeçalho ``WWW-Authenticate`` exigido pela RFC 6750."""
    desafio = "Bearer"
    if security_scopes.scopes:
        desafio += f' scope="{security_scopes.scope_str}"'
    return desafio


def _negar(
    session: Session,
    request: Request,
    *,
    usuario: str,
    detalhes: str,
    detail: str,
    desafio: str,
    operacao: str | None = None,
    recurso: str | None = None,
    resultado: str = "negado",
) -> NoReturn:
    """Audita a negação de acesso e lança HTTP 401.

    Por padrão a operação/recurso auditados são o método e o path da requisição.
    """
    registrar_auditoria(
        usuario,
        operacao or request.method,
        recurso or request.url.path,
        resultado,
        detalhes=detalhes,
        session=session,
    )
    session.commit()

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": desafio},
    )


def obter_usuario_atual(
    request: Request,
    security_scopes: SecurityScopes,
    token: str | None = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> UsuarioAtual:
    """Valida o access token, a sessão e os scopes exigidos pela rota.

    Etapas:

    1. Decodifica o JWT (assinatura, expiração e claims ``sub``/``sid``/``scope``).
    2. Confere se a sessão (``sid``) ainda está ativa, sem expiração absoluta
       nem timeout por inatividade.
    3. Recalcula os scopes efetivos (token ∩ perfil atual do usuário).
    4. Verifica se os scopes exigidos pela rota estão presentes (senão, 403).
    5. Atualiza ``ultima_atividade`` da sessão (renova o timeout).
    """
    desafio = _desafio_bearer(security_scopes)

    if token is None:
        _negar(
            session, request,
            usuario="desconhecido",
            detalhes="Token de acesso não informado",
            detail="Token não informado",
            desafio=desafio,
        )

    # 1. JWT -------------------------------------------------------------- #
    try:
        payload = decodificar_access_token(token)
        username = payload.get("sub")
        sessao_id = payload.get("sid")
        scope_claim = payload.get("scope", "")

        if (
            not isinstance(username, str) or not username
            or not isinstance(sessao_id, str) or not sessao_id
            or not isinstance(scope_claim, str)
        ):
            raise InvalidTokenError("Token sem claims válidos")

        token_scopes = set(scope_claim.split())
    except ExpiredSignatureError:
        # A expiração normal do access token é esperada; não a registramos como
        # tentativa negada para evitar poluir a auditoria a cada renovação.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token expirado",
            headers={"WWW-Authenticate": desafio},
        )
    except InvalidTokenError:
        _negar(
            session, request,
            usuario="desconhecido",
            detalhes="Access token inválido ou com claims incompletas",
            detail="Access token inválido",
            desafio=desafio,
        )

    # 2. Sessão ----------------------------------------------------------- #
    agora = int(time.time())
    registro = buscar_sessao_ativa(session, sessao_id)

    if registro is None:
        _negar(
            session, request,
            usuario=username,
            detalhes="Sessão inexistente ou revogada",
            detail="Sessão inexistente ou encerrada",
            desafio=desafio,
        )

    if registro.expira_em <= agora:
        revogar_sessao(session, sessao_id)
        _negar(
            session, request,
            usuario=username,
            operacao="SESSION_EXPIRED", recurso="sessao", resultado="encerrada",
            detalhes="Refresh token expirado",
            detail="Refresh token expirado",
            desafio=desafio,
        )

    if agora - registro.ultima_atividade >= settings.sessao_inatividade_segundos:
        revogar_sessao(session, sessao_id)
        _negar(
            session, request,
            usuario=username,
            operacao="SESSION_TIMEOUT", recurso="sessao", resultado="encerrada",
            detalhes="Sessão encerrada por inatividade",
            detail="Sessão encerrada por inatividade",
            desafio=desafio,
        )

    usuario = session.exec(select(Usuario).where(Usuario.username == username)).first()

    # A sessão precisa pertencer ao mesmo usuário do claim ``sub``. Sem esta
    # checagem, um JWT forjado poderia combinar o ``sid`` de uma sessão válida
    # com o ``sub`` de outra conta (ex.: admin).
    if usuario is not None and registro.usuario_id != usuario.id:
        revogar_sessao(session, sessao_id)
        _negar(
            session, request,
            usuario=username,
            detalhes="Sessão não pertence ao usuário do token",
            detail="Access token inválido",
            desafio=desafio,
        )

    if usuario is None:
        revogar_sessao(session, sessao_id)
        _negar(
            session, request,
            usuario=username,
            detalhes="Usuário do token não encontrado",
            detail="Usuário do token não encontrado",
            desafio=desafio,
        )

    # 3 e 4. Scopes ------------------------------------------------------- #
    # O perfil atual pode reduzir as permissões de tokens já emitidos.
    scopes_efetivos = token_scopes & set(scopes_do_usuario(usuario.role))
    faltantes = set(security_scopes.scopes) - scopes_efetivos

    if faltantes:
        registrar_auditoria(
            username, request.method, request.url.path, "negado",
            detalhes=f"Scopes ausentes: {', '.join(sorted(faltantes))}",
            session=session,
        )
        session.commit()

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permissão insuficiente. Requer: {', '.join(sorted(faltantes))}",
            headers={
                "WWW-Authenticate": (
                    'Bearer error="insufficient_scope", '
                    f'scope="{security_scopes.scope_str}"'
                )
            },
        )

    # 5. Atividade -------------------------------------------------------- #
    registro.ultima_atividade = agora
    session.add(registro)
    session.commit()

    return UsuarioAtual(
        id=usuario.id,
        username=usuario.username,
        role=usuario.role,
        scopes=sorted(scopes_efetivos),
        sessao_id=sessao_id,
    )
