"""Aba de máquinas: CRUD com barra de ações, busca e janelas modais.

Também expõe :func:`listar_maquinas` e :func:`rotulo_maquina`, usadas pelo
formulário de manutenção para montar a lista suspensa de máquinas.
"""

from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from frontend.core.api_client import requisitar_api, validar_resposta_json
from frontend.core.config import CHAVE_TABELA_MAQUINAS
from frontend.core.crud import (
    Permissoes,
    barra_acoes,
    botoes_confirmacao,
    chave_tabela,
    tabela_selecionavel,
)
from frontend.core.estado import concluir_operacao, possui_scope, registrar_atividade

_CAMPOS_MAQUINA = ("id", "nome", "setor", "total_manutencoes")


# --------------------------------------------------------------------------- #
# Dados
# --------------------------------------------------------------------------- #


def listar_maquinas() -> list[dict] | None:
    """Busca as máquinas cadastradas (ordem alfabética) ou ``None`` em caso de erro."""
    response = requisitar_api("GET", "/maquinas", autenticada=True, verificar_status=False)
    maquinas = validar_resposta_json(response, contexto="a lista de máquinas", tipo_esperado=list)
    if maquinas is None:
        return None

    if not all(isinstance(m, dict) and set(_CAMPOS_MAQUINA).issubset(m) for m in maquinas):
        st.error("A API retornou uma máquina com dados incompletos.")
        return None
    return maquinas


def rotulo_maquina(maquina: dict) -> str:
    """Texto exibido na lista suspensa: nome e, se houver, o setor."""
    setor = maquina.get("setor")
    return f"{maquina['nome']} ({setor})" if setor else maquina["nome"]


# --------------------------------------------------------------------------- #
# Aba
# --------------------------------------------------------------------------- #


def _filtrar(maquinas: list[dict], termo: str) -> list[dict]:
    """Filtra por trecho do nome ou do setor, sem diferenciar maiúsculas."""
    termo = termo.strip().casefold()
    if not termo:
        return maquinas
    return [
        m for m in maquinas
        if termo in m["nome"].casefold() or termo in (m.get("setor") or "").casefold()
    ]


def renderizar_maquinas() -> None:
    """CRUD de máquinas: barra de ações, busca e tabela selecionável."""
    permissoes = Permissoes(
        criar=possui_scope("maquinas:create"),
        editar=possui_scope("maquinas:update"),
        excluir=possui_scope("maquinas:delete"),
    )

    st.markdown(
        "Equipamentos que podem receber manutenção. Uma máquina cadastrada aqui "
        "aparece na lista ao registrar uma parada."
    )
    area_acoes = st.container(border=True)

    maquinas = listar_maquinas()
    if maquinas is None:
        return

    termo = st.text_input(
        "Buscar", placeholder="Nome ou setor da máquina", icon=":material/search:",
        label_visibility="collapsed", on_change=registrar_atividade, key="busca_maquina",
    )
    encontradas = _filtrar(maquinas, termo)

    selecionada: dict | None = None
    if not maquinas:
        st.info(
            "Nenhuma máquina cadastrada. Use Nova máquina para cadastrar a primeira."
            if permissoes.criar
            else "Nenhuma máquina cadastrada. Peça a um administrador para cadastrar as máquinas.",
            icon=":material/precision_manufacturing:",
        )
    elif not encontradas:
        st.info("Nenhuma máquina corresponde à busca.", icon=":material/search_off:")
    else:
        df = pd.DataFrame(encontradas)[list(_CAMPOS_MAQUINA)]
        total = len(df)
        st.caption(
            f"{total} de {len(maquinas)} {'máquina' if len(maquinas) == 1 else 'máquinas'}."
        )
        id_selecionado = tabela_selecionavel(
            df,
            chave_tabela(CHAVE_TABELA_MAQUINAS, df["id"].tolist()),
            column_order=["nome", "setor", "total_manutencoes"],
            column_config={
                "nome": st.column_config.TextColumn("Máquina", width="large"),
                "setor": st.column_config.TextColumn("Setor"),
                "total_manutencoes": st.column_config.ProgressColumn(
                    "Manutenções registradas", format="%d", min_value=0,
                    max_value=max(int(df["total_manutencoes"].max()), 1),
                ),
            },
        )
        selecionada = next((m for m in encontradas if m["id"] == id_selecionado), None)

    total_hist = int(selecionada["total_manutencoes"]) if selecionada else 0
    acao = barra_acoes(
        area_acoes,
        rotulo_novo="Nova máquina",
        selecionado=rotulo_maquina(selecionada) if selecionada else None,
        permissoes=permissoes,
        chave="acoes_maquina",
        motivo_sem_exclusao=(
            f"Esta máquina tem {total_hist} "
            f"{'manutenção registrada' if total_hist == 1 else 'manutenções registradas'} "
            "e não pode ser excluída. Renomeie-a se precisar corrigir o cadastro."
            if total_hist else None
        ),
    )

    if acao == "novo":
        _dialogo_nova_maquina()
    elif acao == "editar" and selecionada:
        _dialogo_editar_maquina(selecionada["id"])
    elif acao == "excluir" and selecionada:
        _dialogo_excluir_maquina(selecionada["id"])


# --------------------------------------------------------------------------- #
# Janelas modais
# --------------------------------------------------------------------------- #


def _campos(atual: dict | None = None) -> tuple[str, str]:
    """Campos de nome e setor dentro de um ``st.form``."""
    atual = atual or {}
    nome = st.text_input(
        "Nome da máquina", value=atual.get("nome", ""), max_chars=100,
        placeholder="Ex.: Prensa hidráulica PH-4",
    )
    setor = st.text_input(
        "Setor (opcional)", value=atual.get("setor") or "", max_chars=60,
        placeholder="Ex.: Acabamento",
    )
    return nome, setor


def _enviar(metodo: str, caminho: str, nome: str, setor: str, status_esperado: int) -> None:
    """Valida e envia ``POST``/``PUT``; em caso de sucesso fecha a janela com aviso."""
    if not nome.strip():
        st.error("Informe o nome da máquina.")
        return

    response = requisitar_api(
        metodo, caminho, autenticada=True, verificar_status=False,
        json={"nome": nome.strip(), "setor": setor.strip() or None},
    )
    resultado = validar_resposta_json(
        response,
        status_esperado=status_esperado,
        contexto="a confirmação da máquina",
        campos_obrigatorios=("mensagem", "maquina"),
    )
    if resultado is not None:
        concluir_operacao(resultado["mensagem"])


@st.dialog("Cadastrar máquina")
def _dialogo_nova_maquina() -> None:
    """Janela de cadastro de máquina."""
    with st.form("form_nova_maquina", border=False):
        nome, setor = _campos()
        salvar = st.form_submit_button(
            "Cadastrar máquina", type="primary", icon=":material/add:", width="stretch"
        )
    if salvar:
        registrar_atividade()
        _enviar("POST", "/maquinas", nome, setor, 201)


@st.dialog("Editar máquina")
def _dialogo_editar_maquina(id_maquina: int) -> None:
    """Janela de edição de nome e setor."""
    response = requisitar_api("GET", f"/maquinas/{id_maquina}", autenticada=True, verificar_status=False)
    if response is not None and response.status_code == 404:
        st.warning("Esta máquina foi excluída por outro usuário. Feche a janela e atualize a lista.")
        return
    atual = validar_resposta_json(response, contexto="a máquina", campos_obrigatorios=_CAMPOS_MAQUINA)
    if atual is None:
        return

    total = int(atual["total_manutencoes"])
    if total:
        st.caption(
            f"O novo nome aparece nas {total} manutenções já registradas desta máquina."
            if total > 1 else "O novo nome aparece na manutenção já registrada desta máquina."
        )

    with st.form(f"form_editar_maquina_{id_maquina}", border=False):
        nome, setor = _campos(atual)
        salvar = st.form_submit_button(
            "Salvar alterações", type="primary", icon=":material/save:", width="stretch",
        )
    if salvar:
        registrar_atividade()
        _enviar("PUT", f"/maquinas/{id_maquina}", nome, setor, 200)


@st.dialog("Excluir máquina")
def _dialogo_excluir_maquina(id_maquina: int) -> None:
    """Confirmação de exclusão; a API recusa (409) máquinas com histórico."""
    response = requisitar_api("GET", f"/maquinas/{id_maquina}", autenticada=True, verificar_status=False)
    if response is not None and response.status_code == 404:
        st.warning("Esta máquina já foi excluída por outro usuário. Feche a janela e atualize a lista.")
        return
    atual = validar_resposta_json(response, contexto="a máquina", campos_obrigatorios=_CAMPOS_MAQUINA)
    if atual is None:
        return

    st.markdown(f"Excluir **{escape(rotulo_maquina(atual))}** do cadastro?")
    st.caption("A exclusão é definitiva. Ela fica registrada na auditoria.")

    if botoes_confirmacao("Excluir máquina", f"excluir_maquina_{id_maquina}"):
        response = requisitar_api(
            "DELETE", f"/maquinas/{id_maquina}", autenticada=True, verificar_status=False
        )
        resultado = validar_resposta_json(
            response, contexto="a exclusão da máquina", campos_obrigatorios=("mensagem",)
        )
        if resultado is not None:
            concluir_operacao(resultado["mensagem"])
