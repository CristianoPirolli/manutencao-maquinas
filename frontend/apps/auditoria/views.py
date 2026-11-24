"""Aba de auditoria, visível apenas para quem possui ``auditoria:read``."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from frontend.core.api_client import requisitar_api, validar_resposta_json
from frontend.core.estado import possui_scope, registrar_atividade

_CAMPOS_LOG = {
    "id", "usuario", "operacao", "recurso", "recurso_id", "data_hora", "resultado", "detalhes",
}

#: Nomes legíveis das operações registradas pelo backend.
_OPERACOES = {
    "LOGIN": "Login",
    "LOGOUT": "Logout",
    "REFRESH": "Renovação de token",
    "CREATE": "Criação",
    "UPDATE": "Edição",
    "DELETE": "Exclusão",
    "SESSION_TIMEOUT": "Sessão expirada por inatividade",
    "SESSION_EXPIRED": "Sessão expirada",
}

_RESULTADOS = ("sucesso", "negado", "falha", "encerrada", "ignorado")


def pode_ver_auditoria() -> bool:
    """Indica se a aba de auditoria deve ser exibida."""
    return possui_scope("auditoria:read")


def _montar_dataframe(logs: list[dict]) -> pd.DataFrame:
    """Converte datas e traduz operações para exibição.

    :raises ValueError: se alguma data não puder ser interpretada.
    """
    df = pd.DataFrame(logs)

    datas = pd.to_datetime(df["data_hora"], utc=True, errors="coerce")
    if datas.isna().any():
        raise ValueError("data inválida")

    df["data_hora"] = datas.dt.tz_convert(None)
    df["operacao"] = df["operacao"].map(lambda op: _OPERACOES.get(op, op))
    df["resultado"] = df["resultado"].str.capitalize()
    # Sem registro (ex.: login), o id vem nulo; um traço evita que a tabela
    # exiba o marcador "None".
    df["recurso_id"] = df["recurso_id"].map(lambda i: "—" if pd.isna(i) else str(int(i)))
    return df


def renderizar_auditoria() -> None:
    """Filtros por resultado e tabela com as operações mais recentes."""
    col_resultado, col_limite = st.columns([3, 1], vertical_alignment="bottom")
    with col_resultado:
        filtro = st.pills(
            "Resultado", _RESULTADOS, selection_mode="multi",
            format_func=str.capitalize, on_change=registrar_atividade,
        )
    with col_limite:
        limite = st.selectbox(
            "Mostrar", [25, 50, 100, 250], index=2,
            format_func=lambda n: f"Últimos {n}", on_change=registrar_atividade,
        )

    response = requisitar_api(
        "GET", "/auditoria", autenticada=True, verificar_status=False, params={"limite": limite}
    )
    logs = validar_resposta_json(response, contexto="a lista de auditoria", tipo_esperado=list)
    if logs is None:
        return

    if not all(isinstance(log, dict) and _CAMPOS_LOG.issubset(log) for log in logs):
        st.error("A API retornou um registro de auditoria incompleto.")
        return

    if filtro:
        logs = [log for log in logs if log["resultado"] in filtro]

    if not logs:
        st.info("Nenhum registro de auditoria para os filtros escolhidos.", icon=":material/history:")
        return

    try:
        df = _montar_dataframe(logs)
    except (TypeError, ValueError, KeyError):
        st.error("A API retornou datas inválidas na auditoria.")
        return

    st.dataframe(
        df,
        hide_index=True,
        width="stretch",
        height=440,
        column_order=["data_hora", "usuario", "operacao", "recurso", "recurso_id", "resultado", "detalhes"],
        column_config={
            "data_hora": st.column_config.DatetimeColumn("Quando (UTC)", format="DD/MM/YYYY HH:mm:ss"),
            "usuario": st.column_config.TextColumn("Usuário"),
            "operacao": st.column_config.TextColumn("Operação"),
            "recurso": st.column_config.TextColumn("Recurso"),
            "recurso_id": st.column_config.TextColumn("Registro", width="small"),
            "resultado": st.column_config.TextColumn("Resultado"),
            "detalhes": st.column_config.TextColumn("Detalhes", width="large"),
        },
    )
