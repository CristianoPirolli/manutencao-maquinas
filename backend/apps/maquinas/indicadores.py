"""Indicadores de confiabilidade: MTTR, MTBF e disponibilidade.

Funções puras (sem banco nem FastAPI), para que as fórmulas possam ser lidas
e testadas isoladamente.

Definições adotadas
-------------------
Só as manutenções **corretivas** contam como falha. Preventivas e preditivas
são paradas planejadas e não entram nos indicadores.

* **MTTR** (*Mean Time To Repair*, tempo médio de reparo):
  soma das horas paradas nas falhas ÷ número de falhas.
* **MTBF** (*Mean Time Between Failures*, tempo médio entre falhas):
  média do tempo de funcionamento entre duas falhas consecutivas. Para cada
  par de falhas, o tempo de funcionamento é o intervalo entre as datas (em
  horas) menos as horas que a máquina ficou parada na primeira delas.
  Exige pelo menos duas falhas.
* **Disponibilidade** (inerente): MTBF ÷ (MTBF + MTTR), entre 0 e 1.

Arredondamento: meio para cima (7,25 h vira 7,3 h), como na conta feita à
mão; o padrão do ``Decimal`` arredondaria para o par mais próximo (7,2 h).

Limitação: o cadastro guarda a data da manutenção, não a hora. Por isso o
intervalo entre falhas é contado em dias inteiros (× 24 h), o que é preciso o
bastante para máquinas que falham com dias ou semanas de distância.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

_HORAS_POR_DIA = Decimal(24)
_DECIMO = Decimal("0.1")
_MILESIMO = Decimal("0.001")


@dataclass(frozen=True)
class Falha:
    """Uma manutenção corretiva: quando ocorreu e quanto tempo a máquina parou."""

    data: date
    horas_paradas: Decimal


@dataclass(frozen=True)
class Indicadores:
    """Resultado do cálculo; ``None`` quando não há dados suficientes."""

    falhas: int
    mttr_horas: Decimal | None
    mtbf_horas: Decimal | None
    disponibilidade: Decimal | None


def calcular_mttr(falhas: list[Falha]) -> Decimal | None:
    """Horas paradas médias por falha (``None`` sem falhas)."""
    if not falhas:
        return None
    total = sum((f.horas_paradas for f in falhas), Decimal(0))
    return (total / len(falhas)).quantize(_DECIMO, ROUND_HALF_UP)


def calcular_mtbf(falhas: list[Falha]) -> Decimal | None:
    """Horas médias de funcionamento entre falhas consecutivas.

    Retorna ``None`` com menos de duas falhas, pois não há intervalo a medir.
    """
    if len(falhas) < 2:
        return None

    ordenadas = sorted(falhas, key=lambda f: f.data)
    intervalos = [
        # Uma parada maior que o intervalo (duas falhas no mesmo dia, por
        # exemplo) não pode gerar tempo de funcionamento negativo.
        max(Decimal(0), (posterior.data - anterior.data).days * _HORAS_POR_DIA - anterior.horas_paradas)
        for anterior, posterior in zip(ordenadas, ordenadas[1:])
    ]
    return (sum(intervalos, Decimal(0)) / len(intervalos)).quantize(_DECIMO, ROUND_HALF_UP)


def calcular_disponibilidade(mtbf: Decimal | None, mttr: Decimal | None) -> Decimal | None:
    """Fração do tempo em que a máquina esteve disponível: MTBF ÷ (MTBF + MTTR)."""
    if mtbf is None or mttr is None or mtbf + mttr == 0:
        return None
    return (mtbf / (mtbf + mttr)).quantize(_MILESIMO, ROUND_HALF_UP)


def calcular(falhas: list[Falha]) -> Indicadores:
    """Calcula os três indicadores de uma máquina a partir das suas falhas."""
    mttr = calcular_mttr(falhas)
    mtbf = calcular_mtbf(falhas)
    return Indicadores(
        falhas=len(falhas),
        mttr_horas=mttr,
        mtbf_horas=mtbf,
        disponibilidade=calcular_disponibilidade(mtbf, mttr),
    )
