"""Painel de manutenções: indicadores, busca, tabela, edição e cadastro."""

from __future__ import annotations

import time
from datetime import date
from decimal import InvalidOperation

import pandas as pd
import streamlit as st

from frontend.apps.manutencoes.formulario import (
    DadosManutencao,
    manutencao_completa,
    validar_formulario,
)
from frontend.core.api_client import requisitar_api, validar_resposta_json
from frontend.core.config import CAMPOS_MANUTENCAO, CHAVE_TABELA, TIPOS_MANUTENCAO
from frontend.core.estado import (
    agendar_limpeza_edicao,
    limpar_edicao,
    limpar_selecao,
    possui_scope,
    registrar_atividade,
)
from frontend.core.formatadores import formatar_horas, formatar_moeda, valor_decimal

_TODOS_OS_TIPOS = "Todos os tipos"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _obter_json(caminho: str, contexto: str, campos: tuple[str, ...] = (), **kwargs) -> dict:
    """GET autenticado que interrompe a página se a resposta for inválida."""
    response = requisitar_api("GET", caminho, autenticada=True, verificar_status=False, **kwargs)
    if response is None:
        st.stop()

    dados = validar_resposta_json(response, contexto=contexto, campos_obrigatorios=campos)
    if dados is None:
        st.stop()

    return dados


def _enviar_manutencao(
    metodo: str,
    caminho: str,
    dados: DadosManutencao,
    *,
    status_esperado: int,
    contexto: str,
    operacao: str,
) -> None:
    """Envia ``POST``/``PUT``, exibe o resultado e recarrega a tabela em caso de sucesso.

    :param contexto: usado nas mensagens de erro de formato (ex.: "a confirmação da edição").
    :param operacao: nome da operação confirmada (ex.: "a edição").
    """
    response = requisitar_api(
        metodo, caminho, autenticada=True, verificar_status=False, json=dados.para_payload()
    )
    resultado = validar_resposta_json(
        response,
        status_esperado=status_esperado,
        contexto=contexto,
        campos_obrigatorios=("mensagem", "manutencao"),
    )

    if resultado is None:
        return

    if not manutencao_completa(resultado["manutencao"]):
        st.error(f"A API confirmou {operacao}, mas retornou a manutenção incompleta.")
        return

    st.success(resultado["mensagem"])
    _recarregar_tabela(espera=1)


def _recarregar_tabela(espera: float) -> None:
    """Força a recriação da tabela (nova ``key``) e limpa a seleção atual."""
    st.session_state.geracao_tabela += 1
    agendar_limpeza_edicao()
    time.sleep(espera)  # Dá tempo de o usuário ler a mensagem de sucesso.
    st.rerun()


def _alinhar_botao() -> None:
    """Espaçamento para alinhar botões de formulário com os inputs ao lado."""
    st.write("")
    st.write("")


# --------------------------------------------------------------------------- #
# Indicadores
# --------------------------------------------------------------------------- #


def renderizar_indicadores() -> None:
    """Métricas de custo total, horas paradas e quantidade, na barra lateral."""
    resumo = _obter_json(
        "/manutencoes/resumo",
        "o resumo de custos",
        ("custo_total", "horas_paradas_total", "moeda"),
    )

    custo_total = valor_decimal(resumo["custo_total"])
    horas_total = valor_decimal(resumo["horas_paradas_total"])
    if custo_total is None or horas_total is None:
        st.error("A API retornou o resumo de custos em formato inválido.")
        st.stop()

    st.sidebar.metric("Custo Total", formatar_moeda(custo_total, resumo["moeda"]))
    st.sidebar.metric("Horas Paradas", formatar_horas(horas_total))

    quantidade = _obter_json(
        "/manutencoes/qtd", "a quantidade de manutenções", ("quantidade_total",)
    )
    try:
        total = int(quantidade["quantidade_total"])
    except (TypeError, ValueError):
        st.error("A API retornou a quantidade de manutenções em formato inválido.")
        st.stop()

    st.sidebar.metric("Total de Manutenções", total)


# --------------------------------------------------------------------------- #
# Busca e tabela
# --------------------------------------------------------------------------- #


def _filtros_busca() -> dict[str, str]:
    """Desenha os filtros e devolve os parâmetros de ``GET /manutencoes/busca``."""
    col_maquina, col_tipo, col_horas = st.columns([3, 1.4, 1.2])

    with col_maquina:
        maquina = st.text_input(
            "Filtrar por máquina",
            label_visibility="collapsed",
            placeholder="🔎 Filtrar por nome da máquina",
            on_change=registrar_atividade,
        )
    with col_tipo:
        tipo = st.selectbox(
            "Tipo",
            [_TODOS_OS_TIPOS, *TIPOS_MANUTENCAO],
            label_visibility="collapsed",
            format_func=lambda t: t if t == _TODOS_OS_TIPOS else t.capitalize(),
            on_change=registrar_atividade,
        )
    with col_horas:
        min_horas = st.number_input(
            "Horas paradas mínimas",
            min_value=0.0, value=0.0, step=1.0, format="%.1f",
            label_visibility="collapsed",
            help="Horas paradas mínimas",
            on_change=registrar_atividade,
        )

    params: dict[str, str] = {}
    if maquina.strip():
        params["maquina"] = maquina.strip()
    if tipo in TIPOS_MANUTENCAO:
        params["tipo"] = tipo
    if min_horas > 0:
        params["min_horas"] = f"{min_horas:.1f}"
    return params


def _montar_dataframe(dados: dict) -> pd.DataFrame:
    """Converte ``{id: manutencao}`` em DataFrame formatado para exibição.

    :raises ValueError: se algum registro vier com estrutura ou valor inválido.
    """
    linhas = []

    for id_manutencao, item in dados.items():
        if not isinstance(item, dict):
            raise ValueError("estrutura inválida")

        custo = valor_decimal(item["custo"])
        horas = valor_decimal(item["horas_paradas"])
        if custo is None or horas is None:
            raise ValueError("valor inválido")

        data_manut = date.fromisoformat(str(item["data_manutencao"]))

        linhas.append({
            "ID": int(id_manutencao),
            "Data": data_manut.strftime("%d/%m/%Y"),
            "Máquina": str(item["maquina"]),
            "Tipo": str(item["tipo"]).capitalize(),
            "Custo (R$)": float(custo),
            "Horas Paradas": float(horas),
        })

    return pd.DataFrame(linhas)


def renderizar_listagem() -> None:
    """Filtros + tabela clicável; o clique em uma linha seleciona a manutenção."""
    st.markdown("### 🔍 Manutenções Registradas")
    params = _filtros_busca()

    dados = _obter_json("/manutencoes/busca", "a lista de manutenções", params=params)

    total = len(dados)
    st.caption(f"{total} {'registro encontrado' if total == 1 else 'registros encontrados'}")

    if not dados:
        st.warning("Nenhum registro encontrado.")
        limpar_selecao()
        st.session_state.chave_tabela_anterior = None
        return

    try:
        df = _montar_dataframe(dados)
    except (KeyError, TypeError, ValueError, InvalidOperation):
        st.error("A API retornou dados inválidos para uma das manutenções.")
        st.stop()

    # A ``key`` da tabela muda quando o conjunto de IDs ou a geração muda;
    # isso descarta seleções "fantasmas" de linhas que não existem mais.
    ids_visiveis = [int(v) for v in df["ID"].tolist()]
    chave_tabela = (
        f"{CHAVE_TABELA}_{'_'.join(map(str, ids_visiveis))}_{st.session_state.geracao_tabela}"
    )

    if st.session_state.chave_tabela_anterior != chave_tabela:
        if st.session_state.id_selecionado not in ids_visiveis:
            limpar_selecao()
        st.session_state.chave_tabela_anterior = chave_tabela

    evento = st.dataframe(
        df,
        key=chave_tabela,
        width="stretch",
        height=210,
        row_height=32,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-cell",
        column_config={
            "ID": st.column_config.NumberColumn("ID", width="small"),
            "Data": st.column_config.TextColumn("Data", width="small"),
            "Máquina": st.column_config.TextColumn("Máquina", width="large"),
            "Tipo": st.column_config.TextColumn("Tipo", width="small"),
            "Custo (R$)": st.column_config.NumberColumn("Custo (R$)", format="R$ %.2f"),
            "Horas Paradas": st.column_config.NumberColumn("Horas Paradas", format="%.1f h"),
        },
    )

    celulas = evento.selection.cells
    if not celulas:
        return

    indice = celulas[0][0]
    if isinstance(indice, int) and 0 <= indice < len(df):
        id_clicado = int(df.iloc[indice]["ID"])
        if st.session_state.id_selecionado != id_clicado:
            st.session_state.id_selecionado = id_clicado
            limpar_edicao()
            registrar_atividade()


# --------------------------------------------------------------------------- #
# Edição / exclusão
# --------------------------------------------------------------------------- #


def _carregar_formulario_edicao(id_selecionado: int, atual: dict) -> None:
    """Preenche os widgets de edição com os dados atuais (uma vez por seleção)."""
    if st.session_state.get("id_carregado_formulario") == id_selecionado:
        return

    custo = valor_decimal(atual.get("custo"))
    horas = valor_decimal(atual.get("horas_paradas"))
    tipo = atual.get("tipo")
    try:
        data_manut = date.fromisoformat(str(atual["data_manutencao"]))
    except (TypeError, ValueError):
        data_manut = None

    if custo is None or horas is None or data_manut is None or tipo not in TIPOS_MANUTENCAO:
        st.error("A API retornou valores inválidos para a manutenção selecionada.")
        st.stop()

    st.session_state.id_carregado_formulario = id_selecionado
    st.session_state.edit_maquina = atual.get("maquina", "")
    st.session_state.edit_tipo = tipo
    st.session_state.edit_data = data_manut
    st.session_state.edit_custo = float(custo)
    st.session_state.edit_horas = float(horas)


def _excluir(id_selecionado: int) -> None:
    """Exclui a manutenção selecionada (requer ``manutencoes:delete``)."""
    response = requisitar_api(
        "DELETE", f"/manutencoes/{id_selecionado}", autenticada=True, verificar_status=False
    )
    resultado = validar_resposta_json(
        response, contexto="a confirmação da exclusão", campos_obrigatorios=("mensagem",)
    )
    if resultado is not None:
        st.success(resultado["mensagem"])
        _recarregar_tabela(espera=3)


def renderizar_edicao() -> None:
    """Formulário de alteração/exclusão da manutenção selecionada na tabela."""
    id_selecionado = st.session_state.get("id_selecionado")

    if id_selecionado is None:
        st.caption("Selecione uma manutenção na tabela para editar ou excluir.")
        return

    response = requisitar_api(
        "GET", f"/manutencoes/{id_selecionado}", autenticada=True, verificar_status=False
    )
    if response is None:
        st.stop()

    if response.status_code == 404:
        # Outro usuário pode ter excluído o registro entre dois reruns.
        agendar_limpeza_edicao()
        st.session_state.aviso_manutencao_removida = True
        st.rerun()

    atual = validar_resposta_json(
        response,
        contexto="a manutenção selecionada",
        campos_obrigatorios=tuple(CAMPOS_MANUTENCAO),
    )
    if atual is None:
        st.stop()

    _carregar_formulario_edicao(id_selecionado, atual)

    st.markdown(f"### ✏️ Alterar Manutenção — ID {id_selecionado}")
    pode_excluir = possui_scope("manutencoes:delete")

    with st.form("form_edicao"):
        c1, c2, c3 = st.columns([3, 1.4, 1.4])
        with c1:
            maquina = st.text_input("Máquina", key="edit_maquina")
        with c2:
            tipo = st.selectbox(
                "Tipo", TIPOS_MANUTENCAO, key="edit_tipo", format_func=str.capitalize
            )
        with c3:
            data_manut = st.date_input(
                "Data", key="edit_data", max_value=date.today(), format="DD/MM/YYYY"
            )

        colunas = st.columns([1.4, 1.4, 1.15, 1.15] if pode_excluir else [1.4, 1.4, 1.3])
        with colunas[0]:
            custo = st.number_input(
                "Custo (R$)", min_value=0.01, step=50.0, format="%.2f", key="edit_custo"
            )
        with colunas[1]:
            horas = st.number_input(
                "Horas paradas", min_value=0.0, step=0.5, format="%.1f", key="edit_horas"
            )
        with colunas[2]:
            _alinhar_botao()
            salvar = st.form_submit_button(
                "💾 Salvar", type="primary", width="stretch",
                disabled=not possui_scope("manutencoes:update"),
            )

        excluir = False
        if pode_excluir:
            with colunas[3]:
                _alinhar_botao()
                excluir = st.form_submit_button("🗑️ Excluir", width="stretch")

    if salvar:
        registrar_atividade()
        dados, erro = validar_formulario(maquina, tipo, data_manut, custo, horas)
        if erro:
            st.error(erro)
        else:
            _enviar_manutencao(
                "PUT", f"/manutencoes/{id_selecionado}", dados,
                status_esperado=200,
                contexto="a confirmação da edição",
                operacao="a edição",
            )

    if excluir:
        registrar_atividade()
        _excluir(id_selecionado)


def renderizar_aviso_removida() -> None:
    """Avisa, após o rerun, que a manutenção selecionada deixou de existir."""
    if st.session_state.get("aviso_manutencao_removida"):
        st.warning("A manutenção selecionada foi removida. Selecione outra.")
        st.session_state.aviso_manutencao_removida = False


# --------------------------------------------------------------------------- #
# Cadastro
# --------------------------------------------------------------------------- #


def renderizar_cadastro() -> None:
    """Formulário de nova manutenção (visível apenas com ``manutencoes:create``)."""
    if not possui_scope("manutencoes:create"):
        return

    st.markdown("### ➕ Nova Manutenção")

    with st.form("form_cadastro", clear_on_submit=True):
        c1, c2, c3 = st.columns([3, 1.4, 1.4])
        with c1:
            maquina = st.text_input("Máquina")
        with c2:
            tipo = st.selectbox("Tipo", TIPOS_MANUTENCAO, format_func=str.capitalize)
        with c3:
            data_manut = st.date_input(
                "Data", value=date.today(), max_value=date.today(), format="DD/MM/YYYY"
            )

        c4, c5, c6 = st.columns([1.4, 1.4, 1.3])
        with c4:
            custo = st.number_input(
                "Custo (R$)", min_value=0.01, value=100.00, step=50.0, format="%.2f"
            )
        with c5:
            horas = st.number_input(
                "Horas paradas", min_value=0.0, value=0.0, step=0.5, format="%.1f"
            )
        with c6:
            _alinhar_botao()
            cadastrar = st.form_submit_button("➕ Registrar", type="primary", width="stretch")

    if not cadastrar:
        return

    registrar_atividade()
    dados, erro = validar_formulario(maquina, tipo, data_manut, custo, horas)
    if erro:
        st.error(erro)
        return

    _enviar_manutencao(
        "POST", "/manutencoes", dados,
        status_esperado=201,
        contexto="a confirmação do registro da manutenção",
        operacao="o registro",
    )
