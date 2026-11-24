"""Validação e serialização dos formulários de manutenção (funções puras)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from frontend.core.config import CAMPOS_MANUTENCAO
from frontend.core.formatadores import valor_decimal


@dataclass(frozen=True)
class DadosManutencao:
    """Valores do formulário já validados e normalizados."""

    maquina_id: int
    tipo: str
    data_manutencao: date
    custo: Decimal
    horas_paradas: Decimal

    def para_payload(self) -> dict:
        """Serializa no formato JSON esperado por ``POST``/``PUT /manutencoes``.

        Valores decimais são enviados como texto para não perder precisão.
        """
        return {
            "maquina_id": self.maquina_id,
            "tipo": self.tipo,
            "data_manutencao": self.data_manutencao.isoformat(),
            "custo": format(self.custo, ".2f"),
            "horas_paradas": format(self.horas_paradas.quantize(Decimal("0.1")), ".1f"),
        }


def validar_formulario(
    maquina_id: int | None, tipo: str | None, data_manutencao: date, custo: object, horas: object
) -> tuple[DadosManutencao | None, str | None]:
    """Valida os campos no cliente (o backend repete todas as regras).

    :returns: ``(dados, None)`` se válido, ou ``(None, mensagem_de_erro)``.
    """
    custo_decimal = valor_decimal(custo)
    horas_decimal = valor_decimal(horas)

    if maquina_id is None:
        return None, "Escolha a máquina que recebeu a manutenção."
    if not tipo:
        return None, "Escolha o tipo de manutenção."
    if custo_decimal is None or custo_decimal <= 0:
        return None, "Informe um custo válido maior que zero."
    if horas_decimal is None or horas_decimal < 0:
        return None, "Informe as horas paradas (zero ou mais)."
    if data_manutencao > date.today():
        return None, "A data da manutenção não pode estar no futuro."

    return DadosManutencao(maquina_id, tipo, data_manutencao, custo_decimal, horas_decimal), None


def manutencao_completa(dados: object) -> bool:
    """Confere se a API devolveu todos os campos de uma manutenção."""
    return isinstance(dados, dict) and CAMPOS_MANUTENCAO.issubset(dados)
