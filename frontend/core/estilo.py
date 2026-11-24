"""Identidade visual: CSS complementar ao tema de ``.streamlit/config.toml``.

O tema define fontes e cores-base; este módulo cuida dos elementos próprios
do painel: faixa de advertência, cabeçalho, frase de destaque, faixa de
indicadores e a "fita" de proporção por tipo de manutenção.
"""

from __future__ import annotations

import streamlit as st

_CSS = """
<style>
:root {
    --tinta: #10324A;
    --tinta-suave: #4E6475;
    --aco: #E8ECEF;
    --linha: #C9D2D9;
    --seguranca: #F2B705;
}

.block-container {
    padding-top: 1.5rem;
    padding-bottom: 2rem;
    max-width: 1280px;
}

/* Faixa de advertência (amarelo/tinta), assinatura visual do sistema. */
.faixa-advertencia {
    height: 10px;
    border-radius: 2px;
    background: repeating-linear-gradient(
        -45deg, var(--seguranca) 0 14px, var(--tinta) 14px 28px
    );
    margin-bottom: 1.1rem;
}

/* Cabeçalho do painel */
.cabecalho h1 {
    font-family: "Barlow Condensed", sans-serif;
    font-weight: 700;
    font-size: 2.1rem;
    line-height: 1.05;
    letter-spacing: -0.01em;
    margin: 0;
    padding: 0;
}
.cabecalho p {
    color: var(--tinta-suave);
    margin: 0.2rem 0 0;
    font-size: 0.95rem;
}

/* Frase de destaque gerada a partir dos dados */
.destaque {
    font-family: "Barlow Condensed", sans-serif;
    font-weight: 600;
    font-size: clamp(1.6rem, 3.2vw, 2.5rem);
    line-height: 1.1;
    max-width: 30ch;
    margin: 0.4rem 0 0.35rem;
    color: var(--tinta);
}
.destaque-apoio {
    color: var(--tinta-suave);
    font-size: 1.05rem;
    max-width: 62ch;
    margin: 0 0 1.4rem;
}

/* Faixa de indicadores: valores separados por divisórias, sem cartões. */
.indicadores {
    display: flex;
    flex-wrap: wrap;
    border-top: 2px solid var(--tinta);
    border-bottom: 1px solid var(--linha);
    margin-bottom: 1.2rem;
}
.indicador {
    flex: 1 1 160px;
    padding: 0.75rem 1.1rem 0.8rem 0;
    margin-right: 1.1rem;
    border-right: 1px solid var(--linha);
}
.indicador:last-child { border-right: none; margin-right: 0; }
.indicador .valor {
    font-family: "Barlow Condensed", sans-serif;
    font-weight: 600;
    font-size: 1.85rem;
    line-height: 1.1;
    font-variant-numeric: tabular-nums;
}
.indicador .rotulo {
    color: var(--tinta-suave);
    font-size: 0.9rem;
}

/* Fita de proporção por tipo */
.fita {
    display: flex;
    height: 14px;
    border-radius: 2px;
    overflow: hidden;
    margin: 0.2rem 0 0.5rem;
}
.fita span { display: block; height: 100%; }
.legenda {
    display: flex;
    flex-wrap: wrap;
    gap: 1.25rem;
    font-size: 0.92rem;
    color: var(--tinta-suave);
    margin-bottom: 1.6rem;
}
.legenda i {
    display: inline-block;
    width: 0.75rem;
    height: 0.75rem;
    border-radius: 2px;
    margin-right: 0.4rem;
    vertical-align: -0.05rem;
}
.legenda b { color: var(--tinta); font-weight: 600; }

/* Tela de acesso */
.painel-marca {
    background: var(--tinta);
    color: var(--aco);
    border-radius: 0.25rem;
    padding: 2.2rem 2rem 2.4rem;
}
.painel-marca h1 {
    font-family: "Barlow Condensed", sans-serif;
    font-weight: 700;
    font-size: clamp(2.2rem, 4.5vw, 3.4rem);
    line-height: 1;
    color: #FFFFFF;
    margin: 1.4rem 0 0.8rem;
    padding: 0;
}
.painel-marca p {
    color: #C9D6DF;
    font-size: 1.08rem;
    max-width: 38ch;
    margin: 0 0 0.6rem;
}
.painel-marca .tipos {
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
    margin-top: 1.6rem;
    font-size: 0.95rem;
}
.painel-marca .tipos i {
    display: inline-block;
    width: 0.7rem;
    height: 0.7rem;
    border-radius: 2px;
    margin-right: 0.35rem;
}

/* Barra lateral */
.status-api { font-size: 0.9rem; margin: 0 0 0.8rem; }
.status-api i {
    display: inline-block;
    width: 0.55rem;
    height: 0.55rem;
    border-radius: 50%;
    margin-right: 0.4rem;
}
.usuario-nome {
    font-family: "Barlow Condensed", sans-serif;
    font-size: 1.5rem;
    font-weight: 600;
    line-height: 1.1;
    margin: 0;
}
.usuario-perfil { opacity: 0.8; font-size: 0.92rem; margin: 0.1rem 0 0.9rem; }
.sessao-tempo {
    font-family: "Barlow Condensed", sans-serif;
    font-size: 2rem;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    line-height: 1;
}

@media (prefers-reduced-motion: reduce) {
    * { transition: none !important; animation: none !important; }
}
</style>
"""


def aplicar_estilo() -> None:
    """Injeta o CSS do sistema (executado uma vez por rerun)."""
    st.markdown(_CSS, unsafe_allow_html=True)


def faixa_advertencia() -> None:
    """Desenha a faixa amarela/azul de advertência."""
    st.markdown('<div class="faixa-advertencia" aria-hidden="true"></div>', unsafe_allow_html=True)
