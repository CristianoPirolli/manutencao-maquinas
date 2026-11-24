"""Ajustes visuais globais aplicados via CSS."""

import streamlit as st

_CSS = """
<style>
.block-container {
    padding-top: 2.2rem;
    padding-bottom: 0.8rem;
}

h1 {
    font-size: 1.75rem !important;
    margin-top: 0 !important;
    margin-bottom: 0.4rem !important;
}

h2, h3 {
    font-size: 1.25rem !important;
    margin-top: 0.5rem !important;
    margin-bottom: 0.35rem !important;
}

div[data-testid="stVerticalBlock"] {
    gap: 0.45rem;
}
</style>
"""


def aplicar_estilo() -> None:
    """Compacta espaçamentos e títulos para caber mais informação na tela."""
    st.markdown(_CSS, unsafe_allow_html=True)
