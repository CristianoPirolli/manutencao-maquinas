"""Transformações e análises dos dados de manutenção (funções puras).

Converte a resposta da API em ``DataFrame`` e calcula os textos e números
do painel. Não depende do Streamlit, o que facilita testes e reuso.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from frontend.core.config import TIPOS_MANUTENCAO
from frontend.core.formatadores import valor_decimal

COLUNAS = ["id", "data", "maquina_id", "maquina", "tipo", "custo", "horas"]


def montar_dataframe(dados: dict) -> pd.DataFrame:
    """Converte ``{id: manutencao}`` (formato da API) em ``DataFrame``.

    :raises ValueError: se algum registro vier com estrutura ou valor inválido.
    """
    linhas = []

    for id_manutencao, item in dados.items():
        if not isinstance(item, dict):
            raise ValueError("estrutura inválida")

        custo = valor_decimal(item["custo"])
        horas = valor_decimal(item["horas_paradas"])
        tipo = str(item["tipo"])
        if custo is None or horas is None or tipo not in TIPOS_MANUTENCAO:
            raise ValueError("valor inválido")

        linhas.append({
            "id": int(id_manutencao),
            "data": date.fromisoformat(str(item["data_manutencao"])),
            "maquina_id": int(item["maquina_id"]),
            "maquina": str(item["maquina"]),
            "tipo": tipo,
            "custo": float(custo),
            "horas": float(horas),
        })

    return pd.DataFrame(linhas, columns=COLUNAS)


def _percentual(parte: float, total: float) -> str:
    return f"{round(100 * parte / total)}%" if total else "0%"


def frases_destaque(df: pd.DataFrame) -> tuple[str, str]:
    """Gera a manchete do painel e uma frase de apoio a partir dos dados.

    A manchete aponta a máquina que mais acumulou horas paradas; a frase de
    apoio mostra o peso das corretivas no custo, um indicador clássico de
    maturidade da manutenção (quanto menor, mais planejada é a operação).
    """
    if df.empty:
        return (
            "Nenhuma manutenção registrada ainda.",
            "Registre a primeira intervenção para acompanhar paradas e custos por máquina.",
        )

    horas_por_maquina = df.groupby("maquina")["horas"].sum().sort_values(ascending=False)
    total_horas = horas_por_maquina.sum()
    custo_total = df["custo"].sum()
    custo_corretivo = df.loc[df["tipo"] == "corretiva", "custo"].sum()

    if total_horas > 0:
        maquina = horas_por_maquina.index[0]
        manchete = (
            f"{maquina} concentra {_percentual(horas_por_maquina.iloc[0], total_horas)} "
            "das horas paradas."
        )
    else:
        manchete = "Nenhuma intervenção registrada parou a produção."

    apoio = (
        f"Manutenções corretivas representam {_percentual(custo_corretivo, custo_total)} "
        f"do custo acumulado, em {len(df)} intervenções registradas."
    )
    return manchete, apoio


@dataclass(frozen=True)
class FatiaTipo:
    """Participação de um tipo de manutenção no total de intervenções."""

    tipo: str
    quantidade: int
    percentual: float


def proporcao_por_tipo(df: pd.DataFrame) -> list[FatiaTipo]:
    """Quantidade e percentual de intervenções de cada tipo (ordem fixa)."""
    total = len(df)
    contagem = df["tipo"].value_counts() if total else pd.Series(dtype=int)

    return [
        FatiaTipo(tipo, int(contagem.get(tipo, 0)), (contagem.get(tipo, 0) / total) if total else 0.0)
        for tipo in TIPOS_MANUTENCAO
    ]
