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
from frontend.core.estado import registrar_atividade, salvar_tokens

_CAMPOS_TOKEN = (
    "access_token", "refresh_token", "token_type",
    "expires_in", "refresh_expires_in", "session_idle_seconds", "usuario",
)


def _formulario_login() -> None:
    """Formulário de login via OAuth2 Password Flow (``POST /token``)."""
    st.subheader("Entrar")

    with st.form("form_login"):
        username = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")
        entrar = st.form_submit_button("🔐 Entrar", type="primary", width="stretch")

    if not entrar:
        return

    if not username.strip() or not senha:
        st.error("Informe usuário e senha.")
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
        st.error("A API retornou dados de login incompletos ou inválidos.")


def _formulario_cadastro() -> None:
    """Formulário de criação de conta comum (``POST /usuarios``)."""
    st.subheader("Criar usuário")

    with st.form("form_usuario"):
        novo_usuario = st.text_input("Novo usuário")
        nova_senha = st.text_input("Nova senha", type="password")
        confirmar = st.text_input("Confirmar senha", type="password")
        cadastrar = st.form_submit_button("➕ Criar usuário", width="stretch")

    if not cadastrar:
        return

    # Validações rápidas no cliente; o backend repete todas elas.
    if not novo_usuario.strip():
        st.error("Informe o nome do usuário.")
    elif nova_senha != confirmar:
        st.error("As senhas não coincidem.")
    elif len(nova_senha) < 6:
        st.error("A senha deve possuir pelo menos 6 caracteres.")
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
            st.success(dados["mensagem"])


def renderizar_tela_acesso() -> None:
    """Desenha a tela pública com login e cadastro lado a lado."""
    st.title("🔐 Sistema de Manutenção de Máquinas")
    col_login, col_cadastro = st.columns(2)

    with col_login:
        _formulario_login()

    with col_cadastro:
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
