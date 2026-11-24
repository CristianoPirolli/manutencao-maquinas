"""Endpoints de autenticação: login, renovação de tokens e logout."""

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from backend.apps.autenticacao import service
from backend.apps.autenticacao.schemas import RefreshEntrada, TokenResponse
from backend.core.database import SessionDep
from backend.core.schemas import MensagemResponse

router = APIRouter(tags=["Autenticação"])


@router.post("/token", response_model=TokenResponse)
def gerar_tokens(session: SessionDep, form_data: OAuth2PasswordRequestForm = Depends()):
    """Login via OAuth2 Password Flow (``application/x-www-form-urlencoded``).

    Opcionalmente, o cliente pode pedir um subconjunto de scopes no campo
    ``scope`` (separados por espaço).
    """
    return service.login(session, form_data.username, form_data.password, form_data.scopes)


@router.post("/refresh", response_model=TokenResponse)
def renovar_tokens(dados: RefreshEntrada, session: SessionDep):
    """Troca o refresh token atual por um novo par de tokens (rotação)."""
    return service.renovar_tokens(session, dados.refresh_token)


@router.post("/logout", response_model=MensagemResponse)
def logout(dados: RefreshEntrada, session: SessionDep):
    """Encerra a sessão e revoga todos os seus refresh tokens."""
    service.logout(session, dados.refresh_token)
    return {"mensagem": "Logout realizado com sucesso."}
