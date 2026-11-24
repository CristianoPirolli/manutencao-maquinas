"""Ponto de entrada do frontend Streamlit.

Execução (a partir da raiz do repositório, para que o tema em
``.streamlit/config.toml`` seja aplicado)::

    streamlit run frontend/app.py

O Streamlit re-executa este script do início ao fim a cada interação do
usuário. Este arquivo apenas orquestra a ordem das telas; a lógica de cada
uma fica em ``frontend/apps``.
"""

import sys
from pathlib import Path

# ``streamlit run frontend/app.py`` adiciona apenas ``frontend/`` ao sys.path.
# Incluímos a raiz do repositório para permitir imports absolutos ``frontend.*``.
_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

import streamlit as st  # noqa: E402

from frontend.apps.auditoria.views import pode_ver_auditoria, renderizar_auditoria  # noqa: E402
from frontend.apps.autenticacao.componentes import (  # noqa: E402
    renderizar_status_api,
    renderizar_usuario,
)
from frontend.apps.autenticacao.views import (  # noqa: E402
    renderizar_tela_acesso,
    sincronizar_perfil,
)
from frontend.apps.manutencoes.views import (  # noqa: E402
    renderizar_cabecalho,
    renderizar_registros,
    renderizar_visao_geral,
)
from frontend.core.estado import inicializar_estado, usuario_logado  # noqa: E402
from frontend.core.estilo import aplicar_estilo  # noqa: E402


def main() -> None:
    """Fluxo de uma execução (rerun) da página."""
    st.set_page_config(
        page_title="Controle de manutenção",
        page_icon=":material/precision_manufacturing:",
        layout="wide",
    )
    aplicar_estilo()
    inicializar_estado()
    renderizar_status_api()

    # Área pública: login e cadastro.
    if not usuario_logado():
        renderizar_tela_acesso()
        st.stop()

    # Área autenticada.
    usuario = sincronizar_perfil()
    renderizar_usuario(usuario)
    renderizar_cabecalho()

    nomes_abas = ["Visão geral", "Registros"]
    if pode_ver_auditoria():
        nomes_abas.append("Auditoria")
    abas = st.tabs(nomes_abas)

    with abas[0]:
        renderizar_visao_geral()
    with abas[1]:
        renderizar_registros()
    if len(abas) > 2:
        with abas[2]:
            renderizar_auditoria()


main()
