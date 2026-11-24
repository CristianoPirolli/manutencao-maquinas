"""Testes do CRUD, da busca e dos indicadores de manutenções."""

from datetime import date, timedelta

import pytest


def _nova(**sobrescritas) -> dict:
    """Payload válido de manutenção, com campos opcionalmente sobrescritos."""
    dados = {
        "maquina": "Prensa hidráulica",
        "tipo": "preventiva",
        "data_manutencao": "2026-01-15",
        "custo": "500.00",
        "horas_paradas": "2.5",
    }
    dados.update(sobrescritas)
    return dados


# --------------------------------------------------------------------------- #
# Consultas
# --------------------------------------------------------------------------- #


def test_dados_demo_carregados(client, admin_headers):
    response = client.get("/manutencoes", headers=admin_headers)

    assert response.status_code == 200
    assert len(response.json()) == 5


def test_quantidade(client, admin_headers):
    response = client.get("/manutencoes/qtd", headers=admin_headers)
    assert response.json() == {"quantidade_total": 5}


def test_resumo_de_custos(client, admin_headers):
    resumo = client.get("/manutencoes/resumo", headers=admin_headers).json()

    assert resumo == {"custo_total": "20580.50", "horas_paradas_total": "35.0", "moeda": "R$"}


@pytest.mark.parametrize(
    ("params", "ids_esperados"),
    [
        ({"maquina": "Bobinadeira"}, {"1", "5"}),
        ({"tipo": "corretiva"}, {"2", "4", "5"}),
        ({"min_horas": "8"}, {"2", "5"}),
        ({"maquina": "Bobinadeira", "tipo": "corretiva"}, {"5"}),
        ({"maquina": "inexistente"}, set()),
    ],
)
def test_busca_com_filtros(client, admin_headers, params, ids_esperados):
    response = client.get("/manutencoes/busca", params=params, headers=admin_headers)

    assert response.status_code == 200
    assert set(response.json()) == ids_esperados


def test_busca_ordena_da_mais_recente_para_a_mais_antiga(client, admin_headers):
    dados = client.get("/manutencoes/busca", headers=admin_headers).json()
    datas = [item["data_manutencao"] for item in dados.values()]

    assert datas == sorted(datas, reverse=True)


def test_obter_por_id(client, admin_headers):
    response = client.get("/manutencoes/3", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["maquina"] == "Caldeira"


def test_obter_inexistente_retorna_404(client, admin_headers):
    assert client.get("/manutencoes/999", headers=admin_headers).status_code == 404


# --------------------------------------------------------------------------- #
# Criação e validações
# --------------------------------------------------------------------------- #


def test_criar_manutencao(client, usuario_headers):
    response = client.post("/manutencoes", json=_nova(tipo="  Corretiva "), headers=usuario_headers)

    assert response.status_code == 201
    corpo = response.json()
    assert corpo["manutencao"]["tipo"] == "corretiva"  # Normalizado.
    assert corpo["manutencao"]["custo"] == "500.00"
    assert "operador" in corpo["mensagem"]


@pytest.mark.parametrize(
    "invalido",
    [
        {"maquina": "   "},
        {"tipo": "emergencial"},
        {"custo": "0"},
        {"custo": "-10"},
        {"horas_paradas": "-1"},
        {"data_manutencao": (date.today() + timedelta(days=1)).isoformat()},
    ],
)
def test_criar_com_dados_invalidos_retorna_422(client, admin_headers, invalido):
    response = client.post("/manutencoes", json=_nova(**invalido), headers=admin_headers)
    assert response.status_code == 422


# --------------------------------------------------------------------------- #
# Alteração e exclusão
# --------------------------------------------------------------------------- #


def test_atualizar_manutencao(client, usuario_headers):
    response = client.put(
        "/manutencoes/1", json=_nova(maquina="Bobinadeira 01-A"), headers=usuario_headers
    )

    assert response.status_code == 200
    assert response.json()["manutencao"]["maquina"] == "Bobinadeira 01-A"


def test_atualizar_inexistente_retorna_404(client, admin_headers):
    assert client.put("/manutencoes/999", json=_nova(), headers=admin_headers).status_code == 404


def test_admin_exclui_manutencao(client, admin_headers):
    assert client.delete("/manutencoes/1", headers=admin_headers).status_code == 200
    assert client.get("/manutencoes/1", headers=admin_headers).status_code == 404
    assert client.get("/manutencoes/qtd", headers=admin_headers).json()["quantidade_total"] == 4


# --------------------------------------------------------------------------- #
# Auditoria
# --------------------------------------------------------------------------- #


def test_operacoes_sao_auditadas(client, admin_headers):
    client.post("/manutencoes", json=_nova(), headers=admin_headers)
    client.delete("/manutencoes/2", headers=admin_headers)

    logs = client.get("/auditoria", params={"limite": 10}, headers=admin_headers).json()
    operacoes = {(log["operacao"], log["recurso"], log["resultado"]) for log in logs}

    assert ("LOGIN", "autenticacao", "sucesso") in operacoes
    assert ("CREATE", "manutencao", "sucesso") in operacoes
    assert ("DELETE", "manutencao", "sucesso") in operacoes
