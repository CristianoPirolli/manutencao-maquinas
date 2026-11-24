"""Componentes da barra lateral: status da API, usuário e sessão."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from html import escape

import streamlit as st

from frontend.core.api_client import api_online, logout
from frontend.core.formatadores import formatar_tempo

_AVISO_EXPIRACAO_SEGUNDOS = 5 * 60

#: Descrição legível de cada scope, exibida na lista de permissões.
_DESCRICAO_SCOPES = {
    "maquinas:read": "Consultar máquinas",
    "maquinas:create": "Cadastrar máquinas",
    "maquinas:update": "Editar máquinas",
    "maquinas:delete": "Excluir máquinas",
    "manutencoes:read": "Consultar manutenções",
    "manutencoes:create": "Registrar manutenções",
    "manutencoes:update": "Editar manutenções",
    "manutencoes:delete": "Excluir manutenções",
    "auditoria:read": "Consultar auditoria",
}


def renderizar_status_api() -> None:
    """Indicador discreto de disponibilidade da API na barra lateral."""
    if api_online():
        cor, texto = "#2E8B57", "API conectada"
    else:
        cor, texto = "#C8332B", "API indisponível. Verifique se o backend está rodando."

    st.sidebar.markdown(
        f'<p class="status-api"><i style="background:{cor}"></i>{texto}</p>',
        unsafe_allow_html=True,
    )


def renderizar_usuario(usuario: dict) -> None:
    """Nome, perfil, contador de sessão, permissões e botão Sair."""
    perfil = "Administrador" if usuario.get("role") == "admin" else "Usuário comum"

    with st.sidebar:
        st.markdown(
            f'<p class="usuario-nome">{escape(str(usuario.get("username", "—")))}</p>'
            f'<p class="usuario-perfil">{perfil}</p>',
            unsafe_allow_html=True,
        )

        painel_expiracao()

        with st.expander("Permissões desta sessão"):
            for scope in usuario.get("scopes", []):
                st.markdown(f":material/check: {_DESCRICAO_SCOPES.get(scope, scope)}")

        if st.button("Sair", icon=":material/logout:", width="stretch"):
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
    restante = (horario_expiracao - agora).total_seconds()
    access_expira_em = st.session_state.get("access_expira_em")
    restante_access = (access_expira_em - agora).total_seconds() if access_expira_em else 0

    st.caption("Sessão encerra por inatividade em")
    st.markdown(
        f'<div class="sessao-tempo">{formatar_tempo(restante)}</div>', unsafe_allow_html=True
    )
    st.caption(
        f"Token de acesso renova sozinho em {formatar_tempo(restante_access)}."
        if restante_access > 0
        else "Token de acesso será renovado na próxima ação."
    )

    if 0 < restante <= _AVISO_EXPIRACAO_SEGUNDOS:
        st.warning("Menos de 5 minutos de sessão. Interaja com o painel para continuar.")

    if restante <= 0:
        st.error("Sessão encerrada por inatividade. Entre novamente.")
        time.sleep(2)
        logout()
        st.rerun()
