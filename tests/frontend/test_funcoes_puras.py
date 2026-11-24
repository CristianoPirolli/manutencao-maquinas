"""Testes das funções puras do frontend (não exigem servidor nem navegador)."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from frontend.apps.manutencoes.formulario import manutencao_completa, validar_formulario
from frontend.core.api_client import resposta_token_valida
from frontend.core.formatadores import (
    formatar_horas,
    formatar_moeda,
    formatar_tempo,
    valor_decimal,
)

# --------------------------------------------------------------------------- #
# Formatadores
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [("10", Decimal("10.00")), (2.345, Decimal("2.35")), ("abc", None), ("NaN", None), (None, None)],
)
def test_valor_decimal(entrada, esperado):
    assert valor_decimal(entrada) == esperado


def test_formatar_moeda_no_padrao_brasileiro():
    assert formatar_moeda(Decimal("20580.5")) == "R$ 20.580,50"


def test_formatar_horas():
    assert formatar_horas(Decimal("35.0")) == "35,0 h"


@pytest.mark.parametrize(
    ("segundos", "esperado"), [(65, "01:05"), (3725, "01:02:05"), (-10, "00:00")]
)
def test_formatar_tempo(segundos, esperado):
    assert formatar_tempo(segundos) == esperado


# --------------------------------------------------------------------------- #
# Formulário de manutenção
# --------------------------------------------------------------------------- #


def test_formulario_valido_gera_payload():
    dados, erro = validar_formulario(" Caldeira ", "preditiva", date(2026, 1, 2), 150.0, 1.26)

    assert erro is None
    assert dados.para_payload() == {
        "maquina": "Caldeira",
        "tipo": "preditiva",
        "data_manutencao": "2026-01-02",
        "custo": "150.00",
        "horas_paradas": "1.3",
    }


@pytest.mark.parametrize(
    ("maquina", "custo", "horas", "data_manut"),
    [
        ("  ", 10, 0, date(2026, 1, 1)),
        ("Prensa", 0, 0, date(2026, 1, 1)),
        ("Prensa", 10, -1, date(2026, 1, 1)),
        ("Prensa", 10, 0, date.today() + timedelta(days=1)),
    ],
)
def test_formulario_invalido_retorna_erro(maquina, custo, horas, data_manut):
    dados, erro = validar_formulario(maquina, "corretiva", data_manut, custo, horas)

    assert dados is None
    assert erro


def test_manutencao_completa():
    completa = {
        "id": 1, "maquina": "x", "tipo": "corretiva",
        "data_manutencao": "2026-01-01", "custo": "1", "horas_paradas": "0",
    }
    assert manutencao_completa(completa)
    assert not manutencao_completa({"id": 1})


# --------------------------------------------------------------------------- #
# Validação da resposta de login
# --------------------------------------------------------------------------- #


def _resposta_token(**sobrescritas) -> dict:
    dados = {
        "access_token": "a",
        "refresh_token": "r",
        "token_type": "bearer",
        "expires_in": 900,
        "refresh_expires_in": 604800,
        "session_idle_seconds": 1800,
        "usuario": {
            "id": 1, "username": "admin", "role": "admin",
            "scopes": ["manutencoes:read"], "sessao_id": "abc",
        },
    }
    dados.update(sobrescritas)
    return dados


def test_resposta_token_valida():
    assert resposta_token_valida(_resposta_token())


@pytest.mark.parametrize(
    "invalido",
    [{"access_token": ""}, {"token_type": "mac"}, {"expires_in": True}, {"usuario": {"id": 1}}],
)
def test_resposta_token_invalida(invalido):
    assert not resposta_token_valida(_resposta_token(**invalido))
