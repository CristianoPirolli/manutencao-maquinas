"""Gerenciamento do ``st.session_state``.

Centraliza as chaves usadas pelo frontend para que nenhuma tela precise
conhecer detalhes de inicialização ou limpeza de estado.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import streamlit as st

from frontend.core.config import SESSION_IDLE_SECONDS

#: Chaves dos widgets do formulário de edição.
_CHAVES_EDICAO = ("edit_maquina", "edit_tipo", "edit_data", "edit_custo", "edit_horas")

#: Estado inicial de cada chave controlada pelo app.
_ESTADO_INICIAL = {
    "token": None,
    "refresh_token": None,
    "usuario": None,
    "sessao_id": None,
    "id_selecionado": None,
    "id_carregado_formulario": None,
    "limpar_edicao_pendente": False,
    "geracao_tabela": 0,
    "chave_tabela_anterior": None,
    "access_expira_em": None,
    "refresh_expira_em": None,
    "horario_expiracao": None,
    "session_idle_seconds": SESSION_IDLE_SECONDS,
}


def inicializar_estado() -> None:
    """Cria as chaves ausentes e aplica limpezas agendadas no rerun anterior.

    Widgets com ``key`` não podem ter o valor alterado depois de criados no
    mesmo rerun; por isso a limpeza do formulário é *agendada* e executada
    aqui, antes de qualquer widget ser desenhado.
    """
    for chave, valor in _ESTADO_INICIAL.items():
        st.session_state.setdefault(chave, valor)

    if st.session_state.limpar_edicao_pendente:
        limpar_edicao()
        st.session_state.limpar_edicao_pendente = False


# --------------------------------------------------------------------------- #
# Seleção / edição de manutenções
# --------------------------------------------------------------------------- #


def limpar_edicao() -> None:
    """Remove os valores do formulário de edição."""
    st.session_state.id_carregado_formulario = None
    for chave in _CHAVES_EDICAO:
        st.session_state.pop(chave, None)


def limpar_selecao() -> None:
    """Desmarca a manutenção selecionada e limpa o formulário."""
    st.session_state.id_selecionado = None
    limpar_edicao()


def agendar_limpeza_edicao() -> None:
    """Desmarca a seleção e limpa os widgets no início do próximo rerun."""
    st.session_state.id_selecionado = None
    st.session_state.limpar_edicao_pendente = True


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
    st.session_state.token = None
    st.session_state.refresh_token = None
    st.session_state.usuario = None
    st.session_state.sessao_id = None
    st.session_state.id_selecionado = None
    st.session_state.access_expira_em = None
    st.session_state.refresh_expira_em = None
    st.session_state.horario_expiracao = None
    st.session_state.session_idle_seconds = SESSION_IDLE_SECONDS
    st.session_state.id_carregado_formulario = None
    st.session_state.limpar_edicao_pendente = True
