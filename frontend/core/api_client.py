"""Cliente HTTP da API com renovação automática de tokens.

Toda comunicação do frontend com o backend passa por :func:`requisitar_api`,
que:

1. Anexa o ``Authorization: Bearer`` nas chamadas protegidas.
2. Ao receber 401, tenta ``/refresh`` uma única vez e repete a chamada.
3. Se a renovação falhar, encerra a sessão local e volta à tela de login.
4. Converte erros de rede em mensagens amigáveis.
"""

from __future__ import annotations

import time
from typing import Any

import requests
import streamlit as st

from frontend.core.config import API_URL, TIMEOUT, TIMEOUT_HEALTH_CHECK
from frontend.core.estado import limpar_sessao, salvar_tokens

_CAMPOS_USUARIO = {"id", "username", "role", "scopes", "sessao_id"}


# --------------------------------------------------------------------------- #
# Validação de payloads
# --------------------------------------------------------------------------- #


def _inteiro_positivo(valor: object) -> bool:
    # ``type(...) is int`` exclui ``bool``, que é subclasse de ``int``.
    return type(valor) is int and valor > 0


def _texto_preenchido(valor: object) -> bool:
    return isinstance(valor, str) and bool(valor)


def perfil_valido(usuario: object) -> bool:
    """Confere a estrutura de um perfil de usuário (``/me`` ou login)."""
    return (
        isinstance(usuario, dict)
        and _CAMPOS_USUARIO.issubset(usuario)
        and type(usuario.get("id")) is int
        and isinstance(usuario.get("username"), str)
        and isinstance(usuario.get("role"), str)
        and isinstance(usuario.get("scopes"), list)
        and all(isinstance(scope, str) for scope in usuario["scopes"])
        and _texto_preenchido(usuario.get("sessao_id"))
    )


def resposta_token_valida(dados: object) -> bool:
    """Confere se a resposta de ``/token`` ou ``/refresh`` está completa."""
    if not isinstance(dados, dict):
        return False

    return (
        _texto_preenchido(dados.get("access_token"))
        and _texto_preenchido(dados.get("refresh_token"))
        and str(dados.get("token_type", "")).lower() == "bearer"
        and _inteiro_positivo(dados.get("expires_in"))
        and _inteiro_positivo(dados.get("refresh_expires_in"))
        and _inteiro_positivo(dados.get("session_idle_seconds"))
        and perfil_valido(dados.get("usuario"))
    )


# --------------------------------------------------------------------------- #
# Erros
# --------------------------------------------------------------------------- #


def detalhe_resposta(response: requests.Response) -> Any:
    """Extrai o campo ``detail`` do corpo de erro (ou o texto bruto)."""
    try:
        corpo = response.json()
    except (ValueError, requests.exceptions.JSONDecodeError):
        return response.text or "A API não retornou detalhes do erro."

    if isinstance(corpo, dict):
        return corpo.get("detail", corpo)
    return corpo


def mostrar_erro_api(response: requests.Response) -> None:
    """Exibe o erro da API com ícone conforme o status HTTP."""
    detalhe = detalhe_resposta(response)

    if response.status_code == 401:
        st.error(f"🔒 {detalhe}")
    elif response.status_code == 403:
        st.error(f"⛔ {detalhe}")
    else:
        st.error(f"Erro {response.status_code}: {detalhe}")


# --------------------------------------------------------------------------- #
# Sessão remota
# --------------------------------------------------------------------------- #


def _headers_jwt() -> dict[str, str]:
    token = st.session_state.get("token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def api_online() -> bool:
    """Health check rápido em ``GET /``, sem depender de autenticação."""
    try:
        return requests.get(API_URL, timeout=TIMEOUT_HEALTH_CHECK).status_code == 200
    except requests.exceptions.RequestException:
        return False


def _logout_backend() -> None:
    """Revoga a sessão no servidor; falhas de rede são ignoradas."""
    refresh_token = st.session_state.get("refresh_token")
    if not refresh_token:
        return

    try:
        requests.post(f"{API_URL}/logout", json={"refresh_token": refresh_token}, timeout=TIMEOUT)
    except requests.exceptions.RequestException:
        pass


def logout() -> None:
    """Encerra a sessão no backend e, em qualquer caso, limpa a sessão local."""
    try:
        _logout_backend()
    finally:
        limpar_sessao()


def renovar_token() -> requests.Response | None:
    """Chama ``/refresh`` e, se o payload for válido, salva o novo par de tokens.

    Devolve o objeto HTTP para preservar o status e o detalhe da falha, ou
    ``None`` se não houver refresh token ou ocorrer erro de rede.
    """
    refresh_token = st.session_state.get("refresh_token")
    if not refresh_token:
        return None

    try:
        response = requests.post(
            f"{API_URL}/refresh", json={"refresh_token": refresh_token}, timeout=TIMEOUT
        )
    except requests.exceptions.RequestException:
        return None

    if response.status_code == 200:
        try:
            dados = response.json()
        except (ValueError, requests.exceptions.JSONDecodeError):
            return response

        if resposta_token_valida(dados):
            salvar_tokens(dados)

    return response


def _detalhe_falha_renovacao(
    renovou: bool, response: requests.Response, resposta_refresh: requests.Response | None
) -> Any:
    """Escolhe a mensagem mais útil para explicar por que a sessão caiu."""
    if renovou:
        return detalhe_resposta(response)
    if resposta_refresh is None:
        return "Não foi possível obter resposta do endpoint /refresh."
    if resposta_refresh.status_code == 200:
        return (
            "O endpoint /refresh respondeu 200, mas o payload de tokens "
            "estava inválido ou incompleto."
        )
    return detalhe_resposta(resposta_refresh)


# --------------------------------------------------------------------------- #
# Requisição genérica
# --------------------------------------------------------------------------- #


def requisitar_api(
    metodo: str,
    caminho: str,
    *,
    autenticada: bool = False,
    verificar_status: bool = True,
    **kwargs: Any,
) -> requests.Response | None:
    """Envia uma requisição à API.

    :param metodo: verbo HTTP (``GET``, ``POST``...).
    :param caminho: path relativo, ex. ``/manutencoes``.
    :param autenticada: anexa o Bearer token e habilita a renovação automática.
    :param verificar_status: exibe o erro automaticamente se ``response.ok`` for falso.
    :param kwargs: repassados ao :func:`requests.request` (``json``, ``params``...).
    :returns: a resposta, ou ``None`` em caso de falha de rede.
    """
    cabecalhos_base = dict(kwargs.pop("headers", {}) or {})

    def enviar() -> requests.Response:
        cabecalhos = dict(cabecalhos_base)
        if autenticada:
            cabecalhos.update(_headers_jwt())
        return requests.request(
            metodo, f"{API_URL}{caminho}", headers=cabecalhos, timeout=TIMEOUT, **kwargs
        )

    try:
        response = enviar()

        if autenticada and response.status_code == 401:
            token_anterior = st.session_state.get("token")
            resposta_refresh = renovar_token()

            renovou = (
                resposta_refresh is not None
                and resposta_refresh.status_code == 200
                and st.session_state.get("token") != token_anterior
            )

            if renovou:
                response = enviar()

            if not renovou or response.status_code == 401:
                detalhe = _detalhe_falha_renovacao(renovou, response, resposta_refresh)
                logout()
                st.error(
                    "🔒 Sua sessão expirou, o refresh token foi invalidado ou "
                    "a conta não está mais disponível. "
                    f"Detalhe da API: {detalhe}. Você será desconectado."
                )
                time.sleep(2)
                st.rerun()
    except requests.exceptions.ConnectionError:
        st.error("Não foi possível conectar à API.")
        return None
    except requests.exceptions.Timeout:
        st.error("A API demorou muito para responder.")
        return None
    except requests.exceptions.RequestException as erro:
        st.error(f"Erro de comunicação com a API: {erro}")
        return None

    if verificar_status and not response.ok:
        mostrar_erro_api(response)

    return response


def validar_resposta_json(
    response: requests.Response | None,
    status_esperado: int = 200,
    *,
    contexto: str = "a resposta da API",
    campos_obrigatorios: tuple[str, ...] = (),
    tipo_esperado: type | None = dict,
) -> Any:
    """Valida status, JSON e estrutura mínima de uma resposta.

    Em caso de problema, exibe a mensagem adequada e retorna ``None``; em caso
    de sucesso, retorna o JSON já decodificado.
    """
    if response is None:
        return None

    if response.status_code != status_esperado:
        mostrar_erro_api(response)
        return None

    try:
        dados = response.json()
    except (ValueError, requests.exceptions.JSONDecodeError):
        st.error(f"A API retornou JSON inválido para {contexto}.")
        return None

    if tipo_esperado is not None and not isinstance(dados, tipo_esperado):
        st.error(f"A API retornou um formato inesperado para {contexto}.")
        return None

    if isinstance(dados, dict):
        ausentes = [campo for campo in campos_obrigatorios if campo not in dados]
        if ausentes:
            st.error(f"A resposta de {contexto} está incompleta; faltam: {', '.join(ausentes)}.")
            return None

    return dados
