"""Testes de cadastro de usuários e permissões do perfil comum."""


def test_cadastro_de_usuario_comum(client):
    response = client.post("/usuarios", json={"username": "  Maria ", "senha": "segredo1"})

    assert response.status_code == 201
    corpo = response.json()
    assert corpo["username"] == "maria"  # Normalizado.
    assert corpo["role"] == "usuario"


def test_cadastro_duplicado_retorna_409(client):
    dados = {"username": "joao", "senha": "segredo1"}
    assert client.post("/usuarios", json=dados).status_code == 201
    assert client.post("/usuarios", json=dados).status_code == 409


def test_cadastro_com_username_em_branco_retorna_422(client):
    response = client.post("/usuarios", json={"username": "   ", "senha": "segredo1"})
    assert response.status_code == 422


def test_cadastro_com_senha_curta_retorna_422(client):
    response = client.post("/usuarios", json={"username": "ana", "senha": "123"})
    assert response.status_code == 422


def test_usuario_comum_nao_possui_scopes_de_admin(client, usuario_headers):
    perfil = client.get("/me", headers=usuario_headers).json()

    assert perfil["role"] == "usuario"
    assert "manutencoes:delete" not in perfil["scopes"]
    assert "auditoria:read" not in perfil["scopes"]


def test_usuario_comum_nao_exclui_manutencao(client, usuario_headers):
    response = client.delete("/manutencoes/1", headers=usuario_headers)

    assert response.status_code == 403
    assert "manutencoes:delete" in response.json()["detail"]


def test_usuario_comum_nao_acessa_auditoria(client, usuario_headers):
    assert client.get("/auditoria", headers=usuario_headers).status_code == 403
