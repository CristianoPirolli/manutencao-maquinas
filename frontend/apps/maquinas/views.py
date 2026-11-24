"""Aba de máquinas: lista, cadastro, edição e exclusão (janelas modais).

Também expõe :func:`listar_maquinas` e :func:`rotulo_maquina`, usadas pelo
formulário de manutenção para montar a lista suspensa de máquinas.
"""

from __future__ import annotations

from functools import partial

import pandas as pd
import streamlit as st

from frontend.core.api_client import requisitar_api, validar_resposta_json
from frontend.core.config import CHAVE_TABELA_MAQUINAS
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


def _ao_selecionar(chave: str, ids: list[int]) -> None:
    """Callback da tabela: agenda a janela de edição da máquina clicada."""
    linhas = st.session_state[chave].selection.rows
    if linhas:
        st.session_state.editar_maquina_id = ids[linhas[0]]
        st.session_state.geracao_tabela += 1
        registrar_atividade()


def renderizar_maquinas() -> None:
    """Lista de máquinas com o total de manutenções de cada uma."""
    pode_criar = possui_scope("maquinas:create")
    pode_gerenciar = possui_scope("maquinas:update") or possui_scope("maquinas:delete")

    col_texto, col_acao = st.columns([4, 1.3], vertical_alignment="center")
    with col_texto:
        st.markdown(
            "Equipamentos que podem receber manutenção. Uma máquina cadastrada aqui "
            "aparece na lista ao registrar uma parada."
        )
    with col_acao:
        if pode_criar and st.button(
            "Cadastrar máquina", icon=":material/add:", width="stretch", key="btn_nova_maquina"
        ):
            registrar_atividade()
            _dialogo_nova_maquina()

    maquinas = listar_maquinas()
    if maquinas is None:
        return

    if not maquinas:
        st.info(
            "Nenhuma máquina cadastrada. Cadastre a primeira para começar a registrar manutenções."
            if pode_criar
            else "Nenhuma máquina cadastrada. Peça a um administrador para cadastrar as máquinas.",
            icon=":material/precision_manufacturing:",
        )
        return

    df = pd.DataFrame(maquinas)[list(_CAMPOS_MAQUINA)]
    total = len(df)
    st.caption(
        f"{total} {'máquina cadastrada' if total == 1 else 'máquinas cadastradas'}."
        + (" Clique em uma linha para editar." if pode_gerenciar else "")
    )

    chave = f"{CHAVE_TABELA_MAQUINAS}_{st.session_state.geracao_tabela}"
    selecao = (
        {"on_select": partial(_ao_selecionar, chave, df["id"].tolist()), "selection_mode": "single-row"}
        if pode_gerenciar
        else {}
    )
    st.dataframe(
        df,
        key=chave,
        hide_index=True,
        width="stretch",
        height=min(420, 38 + 35 * total),
        row_height=35,
        column_order=["nome", "setor", "total_manutencoes"],
        column_config={
            "nome": st.column_config.TextColumn("Máquina", width="large"),
            "setor": st.column_config.TextColumn("Setor"),
            "total_manutencoes": st.column_config.ProgressColumn(
                "Manutenções registradas", format="%d", min_value=0,
                max_value=max(int(df["total_manutencoes"].max()), 1),
            ),
        },
        **selecao,
    )

    id_editar = st.session_state.get("editar_maquina_id")
    if id_editar is not None:
        st.session_state.editar_maquina_id = None  # Abre uma única vez por clique.
        _dialogo_editar_maquina(id_editar)


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
    """Janela de edição; a exclusão só é oferecida para máquinas sem histórico."""
    response = requisitar_api("GET", f"/maquinas/{id_maquina}", autenticada=True, verificar_status=False)
    if response is not None and response.status_code == 404:
        st.warning("Esta máquina foi excluída por outro usuário. Feche a janela e atualize a lista.")
        return
    atual = validar_resposta_json(response, contexto="a máquina", campos_obrigatorios=_CAMPOS_MAQUINA)
    if atual is None:
        return

    with st.form(f"form_editar_maquina_{id_maquina}", border=False):
        nome, setor = _campos(atual)
        salvar = st.form_submit_button(
            "Salvar alterações", type="primary", icon=":material/save:", width="stretch",
            disabled=not possui_scope("maquinas:update"),
        )
    if salvar:
        registrar_atividade()
        _enviar("PUT", f"/maquinas/{id_maquina}", nome, setor, 200)

    if not possui_scope("maquinas:delete"):
        return

    st.divider()
    total = int(atual["total_manutencoes"])
    if total:
        st.caption(
            f"{atual['nome']} tem {total} {'manutenção registrada' if total == 1 else 'manutenções registradas'} "
            "e por isso não pode ser excluída. Renomeie-a se precisar corrigir o cadastro."
        )
        return

    confirmar = st.checkbox(f"Confirmo a exclusão definitiva de {atual['nome']}")
    if st.button("Excluir máquina", icon=":material/delete:", disabled=not confirmar, width="stretch"):
        registrar_atividade()
        response = requisitar_api(
            "DELETE", f"/maquinas/{id_maquina}", autenticada=True, verificar_status=False
        )
        resultado = validar_resposta_json(
            response, contexto="a exclusão da máquina", campos_obrigatorios=("mensagem",)
        )
        if resultado is not None:
            concluir_operacao(resultado["mensagem"])
