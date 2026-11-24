"""Componentes compartilhados pelas telas de cadastro (CRUD).

As abas Registros e Máquinas seguem o mesmo padrão visual:

1. uma barra de ações fixa acima da tabela (Novo, Editar, Excluir);
2. uma tabela com seleção de uma linha;
3. Editar e Excluir ficam desabilitados até que uma linha seja selecionada.

Assim as quatro operações ficam sempre à vista, em vez de escondidas no
clique da linha.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd
import streamlit as st

from frontend.core.estado import registrar_atividade

Acao = Literal["novo", "editar", "excluir"]


@dataclass(frozen=True)
class Permissoes:
    """O que o usuário pode fazer na tela (derivado dos scopes)."""

    criar: bool
    editar: bool
    excluir: bool


def chave_tabela(prefixo: str, ids: list[int]) -> str:
    """Chave da tabela que muda quando os dados ou a geração mudam.

    Trocar a ``key`` descarta a seleção anterior. Isso evita que, depois de
    filtrar ou salvar, a linha selecionada passe a apontar para outro registro.
    """
    return f"{prefixo}_{st.session_state.geracao_tabela}_{hash(tuple(ids))}"


def tabela_selecionavel(df: pd.DataFrame, chave: str, **kwargs) -> int | None:
    """Desenha a tabela com seleção de uma linha e devolve o ``id`` selecionado."""
    evento = st.dataframe(
        df,
        key=chave,
        hide_index=True,
        width="stretch",
        height=min(420, 38 + 35 * len(df)),
        row_height=35,
        on_select="rerun",
        selection_mode="single-row",
        **kwargs,
    )
    linhas = evento.selection.rows
    if not linhas or linhas[0] >= len(df):
        return None
    return int(df.iloc[linhas[0]]["id"])


def barra_acoes(
    area: st.delta_generator.DeltaGenerator,
    *,
    rotulo_novo: str,
    selecionado: str | None,
    permissoes: Permissoes,
    chave: str,
    motivo_sem_exclusao: str | None = None,
) -> Acao | None:
    """Barra com Novo / Editar / Excluir desenhada dentro de ``area``.

    ``area`` é um ``st.container`` criado *antes* da tabela: a barra aparece
    acima dela, mas é preenchida depois, quando a seleção já é conhecida.

    :param rotulo_novo: texto do botão de cadastro (ex.: "Nova máquina").
    :param selecionado: descrição do registro selecionado, ou ``None``.
    :param motivo_sem_exclusao: se informado, Excluir fica desabilitado e o
        motivo aparece como dica do botão.
    :returns: a ação clicada neste rerun, ou ``None``.
    """
    sem_selecao = selecionado is None
    acao: Acao | None = None

    with area:
        col_info, col_novo, col_editar, col_excluir = st.columns(
            [3, 1.25, 1, 1], vertical_alignment="center"
        )
        with col_info:
            if sem_selecao:
                st.caption("Selecione uma linha da tabela para editar ou excluir.")
            else:
                st.markdown(f"**Selecionado:** {selecionado}")

        with col_novo:
            if permissoes.criar and st.button(
                rotulo_novo,
                type="primary", icon=":material/add:", width="stretch", key=f"{chave}_novo",
            ):
                acao = "novo"

        with col_editar:
            if st.button(
                "Editar", icon=":material/edit:", width="stretch", key=f"{chave}_editar",
                disabled=sem_selecao or not permissoes.editar,
                help=None if permissoes.editar else "Seu perfil não pode editar.",
            ):
                acao = "editar"

        with col_excluir:
            if st.button(
                "Excluir", icon=":material/delete:", width="stretch", key=f"{chave}_excluir",
                disabled=sem_selecao or not permissoes.excluir or motivo_sem_exclusao is not None,
                help=(
                    "Seu perfil não pode excluir." if not permissoes.excluir
                    else motivo_sem_exclusao
                ),
            ):
                acao = "excluir"

    if acao:
        registrar_atividade()
    return acao


def botoes_confirmacao(rotulo: str, chave: str) -> bool:
    """Par Cancelar / confirmar usado nas janelas de exclusão.

    Cancelar fecha a janela com um ``st.rerun()``. Devolve ``True`` quando o
    usuário confirma.
    """
    col_cancelar, col_confirmar = st.columns(2)
    with col_cancelar:
        if st.button("Cancelar", width="stretch", key=f"{chave}_cancelar"):
            st.rerun()
    with col_confirmar:
        confirmado = st.button(
            rotulo, type="primary", icon=":material/delete:", width="stretch",
            key=f"{chave}_confirmar",
        )
    if confirmado:
        registrar_atividade()
    return confirmado
