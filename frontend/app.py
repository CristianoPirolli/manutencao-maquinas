"""Ponto de entrada do frontend Streamlit.

Execução (a partir da raiz do repositório)::

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

from frontend.apps.auditoria.views import renderizar_auditoria  # noqa: E402
from frontend.apps.autenticacao.componentes import (  # noqa: E402
    renderizar_status_api,
    renderizar_usuario,
)
from frontend.apps.autenticacao.views import (  # noqa: E402
    renderizar_tela_acesso,
    sincronizar_perfil,
)
from frontend.apps.manutencoes.views import (  # noqa: E402
    renderizar_aviso_removida,
    renderizar_cadastro,
    renderizar_edicao,
    renderizar_indicadores,
    renderizar_listagem,
)
from frontend.core.estado import inicializar_estado, usuario_logado  # noqa: E402
from frontend.core.estilo import aplicar_estilo  # noqa: E402


def main() -> None:
    """Fluxo de uma execução (rerun) da página."""
    st.set_page_config(page_title="Manutenção de Máquinas", layout="wide")
    aplicar_estilo()
    inicializar_estado()
    renderizar_status_api()

    # Área pública: login e cadastro.
    if not usuario_logado():
        renderizar_tela_acesso()
        st.stop()

    # Área autenticada.
    usuario = sincronizar_perfil()

    st.title("🛠️ Painel de Manutenção de Máquinas")
    renderizar_usuario(usuario)
    renderizar_indicadores()
    renderizar_listagem()
    renderizar_edicao()
    renderizar_aviso_removida()
    renderizar_cadastro()
    renderizar_auditoria()


main()
