"""Gráficos Altair do painel, com a paleta de tipos de manutenção."""

from __future__ import annotations

import altair as alt
import pandas as pd

from frontend.core.config import CORES_TIPO, TIPOS_MANUTENCAO

_TINTA = "#10324A"
_TINTA_SUAVE = "#4E6475"
_LINHA = "#C9D2D9"

_ESCALA_TIPO = alt.Scale(domain=list(TIPOS_MANUTENCAO), range=[CORES_TIPO[t] for t in TIPOS_MANUTENCAO])


def _estilizar(grafico: alt.Chart) -> alt.Chart:
    """Aplica tipografia e cores do sistema ao gráfico."""
    return (
        grafico.configure(font="Barlow")
        .configure_view(stroke=None)
        .configure_axis(
            labelColor=_TINTA_SUAVE,
            titleColor=_TINTA_SUAVE,
            labelFontSize=13,
            titleFontSize=13,
            titleFontWeight=500,
            domainColor=_LINHA,
            gridColor=_LINHA,
            gridOpacity=0.6,
            tickColor=_LINHA,
        )
        .configure_legend(
            orient="top",
            title=None,
            labelColor=_TINTA,
            labelFontSize=13,
            symbolType="square",
        )
    )


def horas_por_maquina(df: pd.DataFrame) -> alt.Chart:
    """Barras horizontais de horas paradas por máquina, empilhadas por tipo."""
    ordem = df.groupby("maquina")["horas"].sum().sort_values(ascending=False).index.tolist()

    grafico = (
        alt.Chart(df)
        .mark_bar(cornerRadiusEnd=2)
        .encode(
            y=alt.Y(
                "maquina:N", sort=ordem, title=None, axis=alt.Axis(labelLimit=220),
                scale=alt.Scale(paddingInner=0.4),
            ),
            x=alt.X("sum(horas):Q", title="Horas paradas", axis=alt.Axis(tickMinStep=1)),
            color=alt.Color(
                "tipo:N", scale=_ESCALA_TIPO,
                legend=alt.Legend(labelExpr="upper(slice(datum.label,0,1)) + slice(datum.label,1)"),
            ),
            order=alt.Order("tipo:N"),
            tooltip=[
                alt.Tooltip("maquina:N", title="Máquina"),
                alt.Tooltip("tipo:N", title="Tipo"),
                alt.Tooltip("sum(horas):Q", title="Horas paradas", format=".1f"),
            ],
        )
        # Altura por faixa: o gráfico cresce com o número de máquinas. Uma
        # altura total fixa é dividida também com legenda e eixo, espremendo
        # as barras quando há muitas máquinas.
        .properties(height=alt.Step(44))
    )
    return _estilizar(grafico)


def custo_por_mes(df: pd.DataFrame) -> alt.Chart:
    """Colunas de custo por mês, empilhadas por tipo."""
    dados = df.assign(mes=pd.to_datetime(df["data"]).dt.to_period("M").dt.to_timestamp())

    grafico = (
        alt.Chart(dados)
        .mark_bar(cornerRadiusEnd=2, size=34)
        .encode(
            x=alt.X("yearmonth(mes):T", title=None, axis=alt.Axis(format="%b/%y", labelAngle=0)),
            y=alt.Y("sum(custo):Q", title="Custo (R$)", axis=alt.Axis(format=",.0f")),
            color=alt.Color("tipo:N", scale=_ESCALA_TIPO, legend=None),
            order=alt.Order("tipo:N"),
            tooltip=[
                alt.Tooltip("yearmonth(mes):T", title="Mês", format="%m/%Y"),
                alt.Tooltip("tipo:N", title="Tipo"),
                alt.Tooltip("sum(custo):Q", title="Custo (R$)", format=",.2f"),
            ],
        )
        .properties(height=260)
    )
    return _estilizar(grafico)
