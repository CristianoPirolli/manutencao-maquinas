"""Testes de login, sessão, refresh token, logout e autorização por scopes."""

import time

from sqlalchemy import update
from sqlmodel import Session

from backend.apps.autenticacao.models import RefreshToken
from backend.core.config import settings
from backend.core.database import engine
from backend.core.security import SCOPES, criar_access_token
from tests.conftest import ADMIN, autenticar, bearer


def test_health_check(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"mensagem": "API está no ar!", "versao": "9"}


def test_login_admin_recebe_todos_os_scopes(client):
    tokens = autenticar(client, *ADMIN)

    assert tokens["token_type"] == "bearer"
    assert tokens["usuario"]["role"] == "admin"
    assert set(tokens["usuario"]["scopes"]) == set(SCOPES)
    assert tokens["expires_in"] == settings.access_token_segundos
    assert tokens["session_idle_seconds"] == settings.sessao_inatividade_segundos


def test_login_ignora_caixa_e_espacos_no_usuario(client):
    response = client.post("/token", data={"username": "  ADMIN ", "password": "admin123"})
    assert response.status_code == 200


def test_login_com_senha_errada_retorna_401(client):
    response = client.post("/token", data={"username": "admin", "password": "errada"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Usuário ou senha inválidos"


def test_usuario_comum_nao_pode_pedir_scope_de_admin(client, usuario_headers):
    response = client.post(
        "/token",
        data={"username": "operador", "password": "senha123", "scope": "manutencoes:delete"},
    )
    assert response.status_code == 400


def test_login_com_subconjunto_de_scopes(client, usuario_headers):
    response = client.post(
        "/token",
        data={"username": "operador", "password": "senha123", "scope": "manutencoes:read"},
    )
    assert response.status_code == 200
    headers = bearer(response.json())

    assert client.get("/manutencoes", headers=headers).status_code == 200
    novo = {
        "maquina": "Prensa", "tipo": "corretiva", "data_manutencao": "2026-01-10",
        "custo": "10.00", "horas_paradas": "1.0",
    }
    assert client.post("/manutencoes", json=novo, headers=headers).status_code == 403


def test_rota_protegida_sem_token_retorna_401(client):
    response = client.get("/me")
    assert response.status_code == 401
    assert response.headers["www-authenticate"].startswith("Bearer")


def test_token_invalido_retorna_401(client):
    response = client.get("/me", headers={"Authorization": "Bearer nao-e-um-jwt"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Access token inválido"


def test_me_retorna_perfil_e_sessao(client):
    tokens = autenticar(client, *ADMIN)
    perfil = client.get("/me", headers=bearer(tokens)).json()

    assert perfil["username"] == "admin"
    assert perfil["sessao_id"] == tokens["usuario"]["sessao_id"]


def test_refresh_rotaciona_e_invalida_token_anterior(client):
    tokens = autenticar(client, *ADMIN)

    renovado = client.post("/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert renovado.status_code == 200
    novos = renovado.json()
    assert novos["refresh_token"] != tokens["refresh_token"]
    assert novos["usuario"]["sessao_id"] == tokens["usuario"]["sessao_id"]

    # Reutilizar o refresh token antigo é recusado (proteção contra replay).
    reuso = client.post("/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert reuso.status_code == 401


def test_reuso_de_refresh_token_revoga_a_sessao_inteira(client):
    tokens = autenticar(client, *ADMIN)
    novos = client.post("/refresh", json={"refresh_token": tokens["refresh_token"]}).json()

    # Um atacante reapresenta o token antigo (já rotacionado)...
    client.post("/refresh", json={"refresh_token": tokens["refresh_token"]})

    # ...e a sessão é encerrada: nem o token novo nem o JWT novo valem mais.
    assert client.post("/refresh", json={"refresh_token": novos["refresh_token"]}).status_code == 401
    assert client.get("/me", headers=bearer(novos)).status_code == 401


def test_refresh_token_desconhecido_retorna_401(client):
    response = client.post("/refresh", json={"refresh_token": "inexistente"})
    assert response.status_code == 401


def test_logout_revoga_sessao_e_access_token(client):
    tokens = autenticar(client, *ADMIN)
    headers = bearer(tokens)

    response = client.post("/logout", json={"refresh_token": tokens["refresh_token"]})
    assert response.status_code == 200

    # O access token ainda não expirou, mas a sessão (sid) foi encerrada.
    assert client.get("/me", headers=headers).status_code == 401
    assert client.post("/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401


def test_token_forjado_com_sessao_de_outro_usuario_e_recusado(client, usuario_headers):
    # Sessão legítima de um usuário comum...
    sessao_operador = client.get("/me", headers=usuario_headers).json()["sessao_id"]

    # ...reaproveitada em um token assinado com ``sub`` de administrador.
    forjado = criar_access_token("admin", "admin", sorted(SCOPES), sessao_operador)
    response = client.get("/auditoria", headers={"Authorization": f"Bearer {forjado}"})

    assert response.status_code == 401


def test_sessao_expira_por_inatividade(client):
    tokens = autenticar(client, *ADMIN)
    sessao_id = tokens["usuario"]["sessao_id"]

    # Simula a passagem do tempo recuando a última atividade da sessão.
    passado = int(time.time()) - settings.sessao_inatividade_segundos - 1
    with Session(engine) as session:
        session.exec(
            update(RefreshToken)
            .where(RefreshToken.sessao_id == sessao_id)
            .values(ultima_atividade=passado)
        )
        session.commit()

    response = client.get("/me", headers=bearer(tokens))
    assert response.status_code == 401
    assert response.json()["detail"] == "Sessão encerrada por inatividade"
