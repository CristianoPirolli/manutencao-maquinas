"""Componentes da barra lateral: status da API, usuário e sessão."""

from __future__ import annotations

import time
from datetime import datetime, timezone

import streamlit as st

from frontend.core.api_client import api_online, logout
from frontend.core.formatadores import formatar_tempo

_AVISO_EXPIRACAO_SEGUNDOS = 5 * 60


def renderizar_status_api() -> None:
    """Indicador visual de disponibilidade da API."""
    if api_online():
        st.sidebar.success("🟢 API online")
    else:
        st.sidebar.error("🔴 API indisponível")


def renderizar_usuario(usuario: dict) -> None:
    """Mostra login, perfil, permissões, contador de sessão e botão Sair."""
    st.sidebar.header("👤 Usuário")
    st.sidebar.write(f"**Login:** {usuario.get('username', '—')}")
    st.sidebar.write(f"**Perfil:** {usuario.get('role', '—')}")

    if usuario.get("role") == "admin":
        st.sidebar.success("Administrador")
    else:
        st.sidebar.info("Usuário comum")

    st.sidebar.markdown("**Permissões:**")
    for scope in usuario.get("scopes", []):
        st.sidebar.write(f"✓ {scope}")

    with st.sidebar:
        painel_expiracao()

    if st.sidebar.button("🚪 Sair", width="stretch"):
        logout()
        st.rerun()


@st.fragment(run_every="10s")
def painel_expiracao() -> None:
    """Contador da sessão, atualizado a cada 10 s sem recarregar a página.

    ``st.fragment`` re-executa apenas esta função, então o restante do painel
    (e as chamadas à API) não são refeitos a cada atualização do contador.
    """
    if not st.session_state.get("token"):
        return

    horario_expiracao = st.session_state.get("horario_expiracao")
    if horario_expiracao is None:
        return

    agora = datetime.now(timezone.utc)
    restante_inatividade = (horario_expiracao - agora).total_seconds()

    access_expira_em = st.session_state.get("access_expira_em")
    refresh_expira_em = st.session_state.get("refresh_expira_em")
    restante_access = (access_expira_em - agora).total_seconds() if access_expira_em else 0
    restante_refresh = (refresh_expira_em - agora).total_seconds() if refresh_expira_em else 0

    st.markdown("### ⏳ Sessão")
    st.metric("Expira por inatividade em", formatar_tempo(restante_inatividade))

    if restante_access > 0:
        st.caption(
            f"🔑 Access token expira em {formatar_tempo(restante_access)} — "
            "renovação automática na próxima chamada protegida."
        )
    else:
        st.caption("🔑 Access token expirado. Será renovado na próxima chamada protegida.")

    st.caption(f"🔄 Refresh token: {max(0, restante_refresh / 86400):.1f} dias restantes.")

    if 0 < restante_inatividade <= _AVISO_EXPIRACAO_SEGUNDOS:
        st.warning("A sessão será encerrada em menos de 5 minutos.")

    if restante_inatividade <= 0:
        st.error("🔒 Sessão encerrada por inatividade. Redirecionando...")
        time.sleep(2)
        logout()
        st.rerun()
