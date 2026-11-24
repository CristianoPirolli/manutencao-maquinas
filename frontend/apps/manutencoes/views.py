"""Telas de manutenções: cabeçalho, visão geral, registros e janelas modais."""

from __future__ import annotations

from datetime import date, datetime
from decimal import InvalidOperation
from html import escape

import pandas as pd
import streamlit as st

from frontend.apps.maquinas.views import listar_maquinas, rotulo_maquina
from frontend.apps.manutencoes import graficos
from frontend.apps.manutencoes.analise import (
    frases_destaque,
    montar_dataframe,
    proporcao_por_tipo,
    tabela_confiabilidade,
)
from frontend.apps.manutencoes.formulario import manutencao_completa, validar_formulario
from frontend.core.api_client import requisitar_api, validar_resposta_json
from frontend.core.config import CAMPOS_MANUTENCAO, CHAVE_TABELA, CORES_TIPO, TIPOS_MANUTENCAO
from frontend.core.crud import (
    Permissoes,
    barra_acoes,
    botoes_confirmacao,
    chave_tabela,
    tabela_selecionavel,
)
from frontend.core.estado import concluir_operacao, possui_scope, registrar_atividade
from frontend.core.estilo import faixa_advertencia
from frontend.core.formatadores import formatar_horas, formatar_moeda, valor_decimal

# --------------------------------------------------------------------------- #
# Acesso à API
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


def _carregar_dataframe(caminho: str, contexto: str, **kwargs) -> pd.DataFrame:
    """Busca ``{id: manutencao}`` e converte em ``DataFrame`` validado."""
    dados = _obter_json(caminho, contexto, **kwargs)
    try:
        return montar_dataframe(dados)
    except (KeyError, TypeError, ValueError, InvalidOperation):
        st.error("A API retornou dados inválidos para uma das manutenções.")
        st.stop()


# --------------------------------------------------------------------------- #
# Cabeçalho
# --------------------------------------------------------------------------- #


def renderizar_cabecalho() -> None:
    """Faixa de advertência, título e ação principal (registrar manutenção)."""
    faixa_advertencia()
    col_titulo, col_acao = st.columns([4, 1.3], vertical_alignment="bottom")

    with col_titulo:
        agora = datetime.now().strftime("%d/%m/%Y às %H:%M")
        st.markdown(
            '<div class="cabecalho"><h1>Controle de manutenção</h1>'
            f"<p>Dados atualizados em {agora}</p></div>",
            unsafe_allow_html=True,
        )

    with col_acao:
        if possui_scope("manutencoes:create") and st.button(
            "Registrar manutenção", type="primary", icon=":material/add:", width="stretch"
        ):
            registrar_atividade()
            _dialogo_nova_manutencao()


# --------------------------------------------------------------------------- #
# Visão geral
# --------------------------------------------------------------------------- #


def _faixa_indicadores(resumo: dict, quantidade: int) -> None:
    """Indicadores de custo e indisponibilidade em uma faixa com divisórias."""
    custo = valor_decimal(resumo["custo_total"])
    horas = valor_decimal(resumo["horas_paradas_total"])
    if custo is None or horas is None:
        st.error("A API retornou o resumo de custos em formato inválido.")
        st.stop()

    moeda = escape(str(resumo["moeda"]))
    custo_medio = formatar_moeda(custo / quantidade, moeda) if quantidade else "—"

    itens = [
        (formatar_moeda(custo, moeda), "custo acumulado"),
        (formatar_horas(horas), "de produção parada"),
        (str(quantidade), "intervenções registradas" if quantidade != 1 else "intervenção registrada"),
        (custo_medio, "custo médio por intervenção"),
    ]
    html = "".join(
        f'<div class="indicador"><div class="valor">{valor}</div>'
        f'<div class="rotulo">{rotulo}</div></div>'
        for valor, rotulo in itens
    )
    st.markdown(f'<div class="indicadores">{html}</div>', unsafe_allow_html=True)


def _fita_tipos(df: pd.DataFrame) -> None:
    """Barra de proporção das intervenções por tipo, com legenda."""
    fatias = proporcao_por_tipo(df)
    if not df.empty:
        segmentos = "".join(
            f'<span style="width:{f.percentual * 100:.2f}%;background:{CORES_TIPO[f.tipo]}"></span>'
            for f in fatias if f.quantidade
        )
        st.markdown(
            f'<div class="fita" role="img" aria-label="Proporção por tipo">{segmentos}</div>',
            unsafe_allow_html=True,
        )

    legenda = "".join(
        f'<span><i style="background:{CORES_TIPO[f.tipo]}"></i>{f.tipo.capitalize()} '
        f"<b>{f.quantidade}</b></span>"
        for f in fatias
    )
    st.markdown(f'<div class="legenda">{legenda}</div>', unsafe_allow_html=True)


def renderizar_visao_geral() -> None:
    """Manchete gerada dos dados, indicadores, proporção por tipo e gráficos."""
    resumo = _obter_json(
        "/manutencoes/resumo", "o resumo de custos", ("custo_total", "horas_paradas_total", "moeda")
    )
    qtd = _obter_json("/manutencoes/qtd", "a quantidade de manutenções", ("quantidade_total",))
    try:
        quantidade = int(qtd["quantidade_total"])
    except (TypeError, ValueError):
        st.error("A API retornou a quantidade de manutenções em formato inválido.")
        st.stop()

    df = _carregar_dataframe("/manutencoes", "a lista de manutenções")

    manchete, apoio = frases_destaque(df)
    st.markdown(
        f'<p class="destaque">{escape(manchete)}</p><p class="destaque-apoio">{escape(apoio)}</p>',
        unsafe_allow_html=True,
    )
    _faixa_indicadores(resumo, quantidade)
    _fita_tipos(df)

    if df.empty:
        return

    col_horas, col_custo = st.columns([1.15, 1], gap="large")
    with col_horas:
        st.subheader("Horas paradas por máquina")
        st.altair_chart(graficos.horas_por_maquina(df), width="stretch")
    with col_custo:
        st.subheader("Custo por mês")
        st.altair_chart(graficos.custo_por_mes(df), width="stretch")

    if possui_scope("maquinas:read"):
        _confiabilidade()


def _confiabilidade() -> None:
    """MTTR, MTBF e disponibilidade por máquina (só corretivas contam como falha)."""
    response = requisitar_api("GET", "/maquinas/indicadores", autenticada=True, verificar_status=False)
    indicadores = validar_resposta_json(
        response, contexto="os indicadores de confiabilidade", tipo_esperado=list
    )
    if indicadores is None:
        return
    try:
        df = tabela_confiabilidade(indicadores)
    except (KeyError, TypeError, ValueError):
        st.error("A API retornou indicadores de confiabilidade em formato inválido.")
        return

    st.subheader("Confiabilidade por máquina")
    if df.empty:
        st.info(
            "Nenhuma manutenção corretiva registrada. MTTR e MTBF são calculados a partir das falhas.",
            icon=":material/verified:",
        )
        return

    st.caption(
        "Só as manutenções corretivas contam como falha. A máquina menos disponível aparece primeiro."
    )
    st.dataframe(
        df,
        hide_index=True,
        width="stretch",
        height=min(420, 38 + 35 * len(df)),
        row_height=35,
        column_config={
            "maquina": st.column_config.TextColumn("Máquina", width="large"),
            "falhas": st.column_config.NumberColumn(
                "Falhas", format="%d", help="Quantidade de manutenções corretivas."
            ),
            "mttr": st.column_config.NumberColumn(
                "MTTR", format="%.1f h",
                help="Tempo médio de reparo: horas paradas nas falhas ÷ número de falhas.",
            ),
            "mtbf": st.column_config.NumberColumn(
                "MTBF", format="%.1f h",
                help="Tempo médio entre falhas: média das horas de funcionamento entre duas "
                     "corretivas seguidas. Precisa de pelo menos duas falhas.",
            ),
            "disponibilidade": st.column_config.ProgressColumn(
                "Disponibilidade", format="%.1f%%", min_value=0.0, max_value=100.0,
                help="MTBF ÷ (MTBF + MTTR). Precisa de pelo menos duas falhas.",
            ),
        },
    )


# --------------------------------------------------------------------------- #
# Registros
# --------------------------------------------------------------------------- #


def _filtros() -> dict[str, str]:
    """Filtros de busca; devolve os parâmetros de ``GET /manutencoes/busca``."""
    col_maquina, col_tipo, col_horas = st.columns([2.2, 2, 1.1], vertical_alignment="bottom")

    maquinas = listar_maquinas() or []
    rotulos = {m["id"]: rotulo_maquina(m) for m in maquinas}

    with col_maquina:
        maquina_id = st.selectbox(
            "Máquina", [None, *rotulos],
            format_func=lambda i: "Todas as máquinas" if i is None else rotulos[i],
            on_change=registrar_atividade, key="filtro_maquina",
        )
    with col_tipo:
        tipo = st.pills(
            "Tipo", TIPOS_MANUTENCAO, format_func=str.capitalize, on_change=registrar_atividade
        )
    with col_horas:
        min_horas = st.number_input(
            "Parada mínima (h)", min_value=0.0, value=0.0, step=1.0, format="%.1f",
            on_change=registrar_atividade,
        )

    params: dict[str, str] = {}
    if maquina_id is not None:
        params["maquina_id"] = str(maquina_id)
    if tipo:
        params["tipo"] = tipo
    if min_horas > 0:
        params["min_horas"] = f"{min_horas:.1f}"
    return params


def _descrever(linha: pd.Series) -> str:
    """Resumo de uma manutenção para a barra de ações e a janela de exclusão."""
    return (
        f"nº {linha['id']}, {linha['maquina']}, {linha['tipo']} em "
        f"{linha['data']:%d/%m/%Y}"
    )


def renderizar_registros() -> None:
    """CRUD de manutenções: barra de ações, filtros e tabela selecionável."""
    permissoes = Permissoes(
        criar=possui_scope("manutencoes:create"),
        editar=possui_scope("manutencoes:update"),
        excluir=possui_scope("manutencoes:delete"),
    )
    area_acoes = st.container(border=True)

    params = _filtros()
    df = _carregar_dataframe("/manutencoes/busca", "a lista de manutenções", params=params)

    selecionada: pd.Series | None = None
    if df.empty:
        st.info(
            "Nenhuma manutenção corresponde aos filtros. Ajuste a busca ou limpe o tipo selecionado.",
            icon=":material/search_off:",
        )
    else:
        total = len(df)
        st.caption(f"{total} {'manutenção encontrada' if total == 1 else 'manutenções encontradas'}.")

        id_selecionado = tabela_selecionavel(
            df.assign(tipo=df["tipo"].str.capitalize()),
            chave_tabela(CHAVE_TABELA, df["id"].tolist()),
            column_order=["data", "maquina", "tipo", "custo", "horas", "id"],
            column_config={
                "id": st.column_config.NumberColumn("Nº", width="small"),
                "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY", width="small"),
                "maquina": st.column_config.TextColumn("Máquina", width="large"),
                "tipo": st.column_config.TextColumn("Tipo", width="small"),
                "custo": st.column_config.NumberColumn("Custo (R$)", format="%.2f"),
                "horas": st.column_config.ProgressColumn(
                    "Horas paradas", format="%.1f h", min_value=0.0,
                    max_value=max(float(df["horas"].max()), 1.0),
                ),
            },
        )
        if id_selecionado is not None:
            selecionada = df.loc[df["id"] == id_selecionado].iloc[0]

    acao = barra_acoes(
        area_acoes,
        rotulo_novo="Nova manutenção",
        selecionado=f"manutenção {_descrever(selecionada)}" if selecionada is not None else None,
        permissoes=permissoes,
        chave="acoes_manutencao",
    )

    if acao == "novo":
        _dialogo_nova_manutencao()
    elif acao == "editar" and selecionada is not None:
        _dialogo_edicao(int(selecionada["id"]))
    elif acao == "excluir" and selecionada is not None:
        _dialogo_exclusao(int(selecionada["id"]), _descrever(selecionada), selecionada["maquina"])


# --------------------------------------------------------------------------- #
# Formulário e janelas modais
# --------------------------------------------------------------------------- #


def _campos_formulario(maquinas: list[dict], atual: dict | None = None) -> tuple:
    """Desenha os campos de manutenção dentro de um ``st.form``.

    :param maquinas: máquinas cadastradas, para a lista suspensa.
    :param atual: valores atuais (edição) ou ``None`` (novo registro).
    :returns: ``(maquina_id, tipo, data, custo, horas)`` informados.
    """
    atual = atual or {}
    tipo_atual = atual.get("tipo", "corretiva")

    rotulos = {m["id"]: rotulo_maquina(m) for m in maquinas}
    ids = list(rotulos)
    id_atual = atual.get("maquina_id")
    maquina_id = st.selectbox(
        "Máquina", ids,
        index=ids.index(id_atual) if id_atual in ids else None,
        format_func=rotulos.get,
        placeholder="Escolha ou digite para buscar",
    )
    tipo = st.segmented_control(
        "Tipo de manutenção", TIPOS_MANUTENCAO, default=tipo_atual,
        format_func=str.capitalize, width="stretch",
    )

    col_data, col_custo, col_horas = st.columns(3)
    with col_data:
        data_manut = st.date_input(
            "Data", value=atual.get("data", date.today()),
            max_value=date.today(), format="DD/MM/YYYY",
        )
    with col_custo:
        custo = st.number_input(
            "Custo (R$)", min_value=0.01, value=float(atual.get("custo", 100.0)),
            step=50.0, format="%.2f",
        )
    with col_horas:
        horas = st.number_input(
            "Horas paradas", min_value=0.0, value=float(atual.get("horas", 0.0)),
            step=0.5, format="%.1f",
        )
    return maquina_id, tipo, data_manut, custo, horas


def _maquinas_para_formulario() -> list[dict] | None:
    """Máquinas da lista suspensa; orienta o usuário se não houver nenhuma."""
    maquinas = listar_maquinas()
    if maquinas is None:
        return None
    if not maquinas:
        st.info(
            "Nenhuma máquina cadastrada ainda. Cadastre a máquina na aba Máquinas "
            "e depois registre a manutenção.",
            icon=":material/precision_manufacturing:",
        )
        return None
    return maquinas


def _enviar(metodo: str, caminho: str, campos: tuple, *, status_esperado: int, acao: str) -> None:
    """Valida, envia ``POST``/``PUT`` e, se der certo, fecha a janela com aviso.

    :param acao: particípio usado no aviso de sucesso (ex.: "registrada").
    """
    dados, erro = validar_formulario(*campos)
    if erro:
        st.error(erro)
        return

    response = requisitar_api(
        metodo, caminho, autenticada=True, verificar_status=False, json=dados.para_payload()
    )
    resultado = validar_resposta_json(
        response,
        status_esperado=status_esperado,
        contexto="a confirmação da operação",
        campos_obrigatorios=("mensagem", "manutencao"),
    )
    if resultado is None:
        return
    if not manutencao_completa(resultado["manutencao"]):
        st.error("A API confirmou a operação, mas devolveu a manutenção incompleta.")
        return

    concluir_operacao(f"Manutenção de {resultado['manutencao']['maquina']} {acao}.")


@st.dialog("Registrar manutenção", width="large")
def _dialogo_nova_manutencao() -> None:
    """Janela de cadastro de uma nova manutenção."""
    maquinas = _maquinas_para_formulario()
    if maquinas is None:
        return

    with st.form("form_nova_manutencao", border=False):
        campos = _campos_formulario(maquinas)
        registrar = st.form_submit_button(
            "Registrar manutenção", type="primary", icon=":material/add:", width="stretch"
        )

    if registrar:
        registrar_atividade()
        _enviar("POST", "/manutencoes", campos, status_esperado=201, acao="registrada")


def _carregar_para_edicao(id_manutencao: int) -> dict | None:
    """Busca a manutenção e converte para os tipos usados no formulário."""
    response = requisitar_api(
        "GET", f"/manutencoes/{id_manutencao}", autenticada=True, verificar_status=False
    )
    if response is None:
        return None
    if response.status_code == 404:
        st.warning("Esta manutenção foi excluída por outro usuário. Feche a janela e atualize a lista.")
        return None

    atual = validar_resposta_json(
        response, contexto="a manutenção selecionada", campos_obrigatorios=tuple(CAMPOS_MANUTENCAO)
    )
    if atual is None:
        return None

    try:
        return montar_dataframe({atual["id"]: atual}).iloc[0].to_dict()
    except (KeyError, TypeError, ValueError, InvalidOperation):
        st.error("A API retornou valores inválidos para a manutenção selecionada.")
        return None


@st.dialog("Excluir manutenção")
def _dialogo_exclusao(id_manutencao: int, descricao: str, maquina: str) -> None:
    """Confirmação de exclusão (somente com ``manutencoes:delete``)."""
    st.markdown(f"Excluir a manutenção {escape(descricao)}?")
    st.caption(
        "A exclusão é definitiva e reduz os totais de custo e de horas paradas. "
        "Ela fica registrada na auditoria."
    )

    if botoes_confirmacao("Excluir manutenção", f"excluir_manutencao_{id_manutencao}"):
        response = requisitar_api(
            "DELETE", f"/manutencoes/{id_manutencao}", autenticada=True, verificar_status=False
        )
        if response is not None and response.status_code == 404:
            st.warning("Esta manutenção já foi excluída por outro usuário. Feche a janela.")
            return
        resultado = validar_resposta_json(
            response, contexto="a confirmação da exclusão", campos_obrigatorios=("mensagem",)
        )
        if resultado is not None:
            concluir_operacao(f"Manutenção de {maquina} excluída.")


@st.dialog("Editar manutenção", width="large")
def _dialogo_edicao(id_manutencao: int) -> None:
    """Janela de edição de uma manutenção."""
    atual = _carregar_para_edicao(id_manutencao)
    if atual is None:
        return
    maquinas = _maquinas_para_formulario()
    if maquinas is None:
        return

    st.caption(f"Registro nº {id_manutencao}")

    with st.form(f"form_edicao_{id_manutencao}", border=False):
        campos = _campos_formulario(maquinas, atual)
        salvar = st.form_submit_button(
            "Salvar alterações", type="primary", icon=":material/save:", width="stretch",
        )

    if salvar:
        registrar_atividade()
        _enviar("PUT", f"/manutencoes/{id_manutencao}", campos, status_esperado=200, acao="salva")
