"""Tela de acesso (login e cadastro) e sincronização do perfil com a API."""

from __future__ import annotations

import streamlit as st

from frontend.core.api_client import (
    logout,
    perfil_valido,
    requisitar_api,
    resposta_token_valida,
    validar_resposta_json,
)
from frontend.core.config import CORES_TIPO
from frontend.core.estado import registrar_atividade, salvar_tokens
from frontend.core.estilo import faixa_advertencia

_CAMPOS_TOKEN = (
    "access_token", "refresh_token", "token_type",
    "expires_in", "refresh_expires_in", "session_idle_seconds", "usuario",
)


def _painel_marca() -> None:
    """Painel de apresentação do sistema, à esquerda da tela de acesso."""
    tipos = "".join(
        f'<span><i style="background:{cor}"></i>{tipo.capitalize()}</span>'
        for tipo, cor in CORES_TIPO.items()
    )
    st.markdown(
        '<div class="painel-marca">'
        '<div class="faixa-advertencia" aria-hidden="true"></div>'
        "<h1>Controle de manutenção</h1>"
        "<p>Registre intervenções, acompanhe as horas de máquina parada "
        "e veja onde o custo de manutenção está concentrado.</p>"
        f'<div class="tipos">{tipos}</div>'
        "</div>",
        unsafe_allow_html=True,
    )


def _formulario_login() -> None:
    """Formulário de login via OAuth2 Password Flow (``POST /token``)."""
    with st.form("form_login", border=False):
        username = st.text_input("Usuário", autocomplete="username")
        senha = st.text_input("Senha", type="password", autocomplete="current-password")
        entrar = st.form_submit_button(
            "Entrar", type="primary", icon=":material/login:", width="stretch"
        )

    if not entrar:
        return

    if not username.strip() or not senha:
        st.error("Informe usuário e senha para entrar.")
        return

    response = requisitar_api(
        "POST", "/token",
        verificar_status=False,
        data={"username": username.strip(), "password": senha},  # form-urlencoded
    )
    dados = validar_resposta_json(response, contexto="o login", campos_obrigatorios=_CAMPOS_TOKEN)

    if dados is None:
        return

    if resposta_token_valida(dados):
        salvar_tokens(dados)
        st.rerun()
    else:
        st.error("A API retornou dados de login incompletos. Tente entrar novamente.")


def _formulario_cadastro() -> None:
    """Formulário de criação de conta comum (``POST /usuarios``)."""
    with st.form("form_usuario", border=False, clear_on_submit=True):
        novo_usuario = st.text_input("Usuário", key="cadastro_usuario", autocomplete="off")
        nova_senha = st.text_input(
            "Senha", type="password", key="cadastro_senha",
            help="Mínimo de 6 caracteres.", autocomplete="new-password",
        )
        confirmar = st.text_input(
            "Repita a senha", type="password", key="cadastro_confirmar",
            autocomplete="new-password",
        )
        cadastrar = st.form_submit_button(
            "Criar conta", icon=":material/person_add:", width="stretch"
        )

    if not cadastrar:
        return

    # Validações rápidas no cliente; o backend repete todas elas.
    if not novo_usuario.strip():
        st.error("Informe um nome de usuário.")
    elif nova_senha != confirmar:
        st.error("As senhas digitadas são diferentes.")
    elif len(nova_senha) < 6:
        st.error("Use uma senha com pelo menos 6 caracteres.")
    else:
        response = requisitar_api(
            "POST", "/usuarios",
            verificar_status=False,
            json={"username": novo_usuario.strip(), "senha": nova_senha},
        )
        dados = validar_resposta_json(
            response,
            status_esperado=201,
            contexto="o cadastro do usuário",
            campos_obrigatorios=("mensagem", "id", "username", "role"),
        )
        if dados is not None:
            st.success(f"Conta {dados['username']} criada. Use a aba Entrar para acessar.")


def renderizar_tela_acesso() -> None:
    """Tela pública: painel do sistema à esquerda, acesso à direita."""
    st.write("")
    col_marca, col_acesso = st.columns([1.25, 1], gap="large", vertical_alignment="center")

    with col_marca:
        _painel_marca()

    with col_acesso:
        aba_entrar, aba_criar = st.tabs(["Entrar", "Criar conta"])
        with aba_entrar:
            _formulario_login()
        with aba_criar:
            _formulario_cadastro()


def sincronizar_perfil() -> dict:
    """Valida a sessão na API (``GET /me``) e atualiza o perfil local.

    Executado a cada rerun do painel: se o administrador alterar o perfil de
    um usuário, os novos scopes passam a valer imediatamente na interface.
    Interrompe a renderização (``st.stop``) se a resposta for inválida.
    """
    response = requisitar_api("GET", "/me", autenticada=True, verificar_status=False)
    if response is None:
        st.stop()

    perfil = validar_resposta_json(
        response,
        contexto="o perfil do usuário",
        campos_obrigatorios=("id", "username", "role", "scopes", "sessao_id"),
    )

    if not perfil_valido(perfil):
        st.error("A API retornou um perfil ou uma lista de permissões inválidos.")
        st.stop()

    if st.session_state.get("sessao_id") != perfil["sessao_id"]:
        st.error("A sessão retornada pela API não corresponde à sessão local. Entre novamente.")
        logout()
        st.rerun()

    st.session_state.usuario = perfil
    st.session_state.sessao_id = perfil["sessao_id"]

    # A API confirmou a sessão ativa neste rerun, então o contador local
    # acompanha a atividade que acabou de ser registrada no backend.
    registrar_atividade()
    return perfil
