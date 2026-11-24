"""Funções puras de conversão e formatação (sem dependência do Streamlit)."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENTAVOS = Decimal("0.01")


def valor_decimal(valor: object) -> Decimal | None:
    """Converte qualquer valor em ``Decimal`` com duas casas.

    Retorna ``None`` se o valor não for numérico ou não for finito (NaN/inf),
    permitindo que a tela trate respostas inválidas da API sem exceções.
    """
    try:
        resultado = Decimal(str(valor)).quantize(CENTAVOS, rounding=ROUND_HALF_UP)
        return resultado if resultado.is_finite() else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def formatar_moeda(valor: Decimal | float, moeda: str = "R$") -> str:
    """Formata no padrão brasileiro: ``R$ 1.234,56``."""
    texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{moeda} {texto}"


def formatar_horas(valor: Decimal | float) -> str:
    """Formata horas com uma casa decimal e vírgula: ``12,5 h``."""
    return f"{valor:.1f} h".replace(".", ",")


def formatar_tempo(segundos: float) -> str:
    """Formata uma duração como ``MM:SS`` ou ``HH:MM:SS`` (nunca negativa)."""
    segundos = max(0, int(segundos))
    horas, resto = divmod(segundos, 3600)
    minutos, segundos = divmod(resto, 60)

    if horas:
        return f"{horas:02d}:{minutos:02d}:{segundos:02d}"
    return f"{minutos:02d}:{segundos:02d}"
