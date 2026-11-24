"""Gerenciamento do ``st.session_state``.

Centraliza as chaves usadas pelo frontend para que nenhuma tela precise
conhecer detalhes de inicialização ou limpeza de estado.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import streamlit as st

from frontend.core.config import SESSION_IDLE_SECONDS

#: Estado inicial de cada chave controlada pelo app.
_ESTADO_INICIAL = {
    "token": None,
    "refresh_token": None,
    "usuario": None,
    "sessao_id": None,
    "access_expira_em": None,
    "refresh_expira_em": None,
    "horario_expiracao": None,
    "session_idle_seconds": SESSION_IDLE_SECONDS,
    # Muda a ``key`` da tabela de registros para descartar seleções antigas.
    "geracao_tabela": 0,
    # Id da manutenção cuja janela de edição deve abrir neste rerun.
    "editar_id": None,
    # Mensagem a exibir como toast no próximo rerun (ex.: após salvar).
    "aviso_pendente": None,
}


def inicializar_estado() -> None:
    """Cria as chaves ausentes e exibe o aviso deixado pelo rerun anterior."""
    for chave, valor in _ESTADO_INICIAL.items():
        st.session_state.setdefault(chave, valor)

    aviso = st.session_state.aviso_pendente
    if aviso:
        st.toast(aviso, icon=":material/check_circle:")
        st.session_state.aviso_pendente = None


def concluir_operacao(mensagem: str) -> None:
    """Agenda o aviso de sucesso, renova a tabela e recarrega a página.

    O ``st.rerun`` completo também fecha a janela modal que originou a ação.
    """
    st.session_state.aviso_pendente = mensagem
    st.session_state.geracao_tabela += 1
    st.rerun()


# --------------------------------------------------------------------------- #
# Sessão do usuário
# --------------------------------------------------------------------------- #


def usuario_logado() -> bool:
    """Indica se existe um access token na sessão local."""
    return bool(st.session_state.get("token"))


def possui_scope(scope: str) -> bool:
    """Verifica se o usuário atual possui o scope informado."""
    usuario = st.session_state.get("usuario") or {}
    return scope in usuario.get("scopes", [])


def registrar_atividade() -> None:
    """Reinicia o contador local de inatividade (espelho do backend)."""
    if not st.session_state.get("token"):
        return

    st.session_state.horario_expiracao = datetime.now(timezone.utc) + timedelta(
        seconds=st.session_state.session_idle_seconds
    )


def salvar_tokens(dados: dict) -> None:
    """Armazena o par de tokens e os prazos retornados por ``/token`` ou ``/refresh``."""
    agora = datetime.now(timezone.utc)

    st.session_state.token = dados["access_token"]
    st.session_state.refresh_token = dados["refresh_token"]
    st.session_state.usuario = dados["usuario"]
    st.session_state.sessao_id = dados["usuario"]["sessao_id"]
    st.session_state.access_expira_em = agora + timedelta(seconds=int(dados["expires_in"]))
    st.session_state.refresh_expira_em = agora + timedelta(
        seconds=int(dados["refresh_expires_in"])
    )
    st.session_state.session_idle_seconds = int(dados["session_idle_seconds"])
    registrar_atividade()


def limpar_sessao() -> None:
    """Descarta tokens e dados do usuário (logout local)."""
    for chave in (
        "token", "refresh_token", "usuario", "sessao_id",
        "access_expira_em", "refresh_expira_em", "horario_expiracao", "editar_id",
    ):
        st.session_state[chave] = None
    st.session_state.session_idle_seconds = SESSION_IDLE_SECONDS
