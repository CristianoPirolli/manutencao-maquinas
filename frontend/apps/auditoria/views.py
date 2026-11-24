"""Tabela de auditoria, visível apenas para quem possui ``auditoria:read``."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from frontend.core.api_client import requisitar_api, validar_resposta_json
from frontend.core.estado import possui_scope, registrar_atividade

_CAMPOS_LOG = {
    "id", "usuario", "operacao", "recurso", "recurso_id", "data_hora", "resultado", "detalhes",
}

#: Renomeação das colunas da API para os rótulos exibidos (na ordem de exibição).
_COLUNAS = {
    "id": "ID",
    "data_hora": "Data/Hora (UTC)",
    "usuario": "Usuário",
    "operacao": "Operação",
    "recurso": "Recurso",
    "recurso_id": "ID Recurso",
    "resultado": "Resultado",
    "detalhes": "Detalhes",
}


def _montar_dataframe(logs: list[dict]) -> pd.DataFrame:
    """Formata as datas e renomeia/ordena as colunas.

    :raises ValueError: se alguma data não puder ser interpretada.
    """
    df = pd.DataFrame(logs)

    datas = pd.to_datetime(df["data_hora"], utc=True, errors="coerce")
    if datas.isna().any():
        raise ValueError("data inválida")

    df["data_hora"] = datas.dt.strftime("%d/%m/%Y %H:%M:%S")
    return df.rename(columns=_COLUNAS)[list(_COLUNAS.values())]


def renderizar_auditoria() -> None:
    """Seletor de quantidade, botão de atualização e tabela de logs."""
    if not possui_scope("auditoria:read"):
        return

    st.markdown("### 🧾 Auditoria")
    col_limite, col_atualizar = st.columns([1, 4])

    with col_limite:
        limite = st.selectbox(
            "Registros", [25, 50, 100, 250], index=2,
            key="limite_auditoria", on_change=registrar_atividade,
        )

    with col_atualizar:
        st.write("")
        st.write("")
        # O clique apenas provoca um rerun, que recarrega os dados abaixo.
        st.button("🔄 Atualizar auditoria", key="atualizar_auditoria", on_click=registrar_atividade)

    response = requisitar_api(
        "GET", "/auditoria", autenticada=True, verificar_status=False, params={"limite": limite}
    )
    logs = validar_resposta_json(response, contexto="a lista de auditoria", tipo_esperado=list)

    if logs is None:
        return

    if not all(isinstance(log, dict) and _CAMPOS_LOG.issubset(log) for log in logs):
        st.error("A API retornou um registro de auditoria incompleto ou inválido.")
        return

    if not logs:
        st.info("Ainda não existem registros de auditoria.")
        return

    try:
        st.dataframe(_montar_dataframe(logs), hide_index=True, width="stretch", height=300)
    except (TypeError, ValueError, KeyError):
        st.error("A API retornou datas ou dados inválidos na auditoria.")
