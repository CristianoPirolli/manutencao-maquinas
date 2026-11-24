"""Regras de negócio do app de manutenções."""

from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlmodel import Session, select

from backend.apps.auditoria.service import registrar_auditoria
from backend.apps.manutencoes.models import Manutencao, ManutencaoBase, TipoManutencao
from backend.apps.manutencoes.schemas import ManutencaoSaida

_RECURSO = "manutencao"
_NAO_ENCONTRADA = "Manutenção não encontrada"


# --------------------------------------------------------------------------- #
# Conversões
# --------------------------------------------------------------------------- #


def para_item(manutencao: Manutencao) -> dict:
    """Converte a entidade no formato usado pelas listagens (sem ``id``)."""
    return {
        "maquina": manutencao.maquina,
        "tipo": manutencao.tipo,
        "data_manutencao": manutencao.data_manutencao,
        "custo": manutencao.custo,
        "horas_paradas": manutencao.horas_paradas,
    }


def para_saida(manutencao: Manutencao) -> ManutencaoSaida:
    """Converte a entidade no schema completo de saída."""
    return ManutencaoSaida(id=manutencao.id, **para_item(manutencao))


def indexar_por_id(manutencoes: list[Manutencao]) -> dict[int, dict]:
    """Monta o dicionário ``{id: manutencao}`` devolvido pelas listagens.

    O formato de dicionário foi mantido por compatibilidade com o roteiro
    original (``GET /vendas`` também retornava ``{id: venda}``).
    """
    return {m.id: para_item(m) for m in manutencoes}


# --------------------------------------------------------------------------- #
# Consultas
# --------------------------------------------------------------------------- #


def listar(session: Session) -> list[Manutencao]:
    """Retorna todas as manutenções em ordem de ``id``."""
    return list(session.exec(select(Manutencao).order_by(Manutencao.id)).all())


def contar(session: Session) -> int:
    """Retorna a quantidade total de manutenções."""
    return session.exec(select(func.count()).select_from(Manutencao)).one()


def resumir_custos(session: Session) -> dict:
    """Soma custo total e horas paradas.

    A soma é feita em Python com :class:`~decimal.Decimal` porque o SQLite
    converte ``NUMERIC`` em ponto flutuante, o que geraria erros de centavos.
    """
    manutencoes = session.exec(select(Manutencao)).all()

    custo_total = sum((m.custo for m in manutencoes), start=Decimal("0.00"))
    horas_total = sum((m.horas_paradas for m in manutencoes), start=Decimal("0.0"))

    return {
        "custo_total": custo_total.quantize(Decimal("0.01")),
        "horas_paradas_total": horas_total.quantize(Decimal("0.1")),
        "moeda": "R$",
    }


def buscar(
    session: Session,
    *,
    maquina: str | None = None,
    tipo: TipoManutencao | None = None,
    min_horas: Decimal | None = None,
) -> list[Manutencao]:
    """Filtra manutenções; os filtros informados são combinados com ``AND``.

    :param maquina: trecho do nome da máquina (busca por "contém").
    :param tipo: tipo exato da manutenção.
    :param min_horas: mínimo de horas paradas.
    :returns: manutenções da mais recente para a mais antiga.
    """
    comando = select(Manutencao)

    if maquina and maquina.strip():
        comando = comando.where(Manutencao.maquina.contains(maquina.strip()))

    if tipo is not None:
        comando = comando.where(Manutencao.tipo == tipo)

    if min_horas is not None:
        comando = comando.where(Manutencao.horas_paradas >= min_horas)

    comando = comando.order_by(Manutencao.data_manutencao.desc(), Manutencao.id)
    return list(session.exec(comando).all())


def obter(session: Session, id_manutencao: int) -> Manutencao:
    """Busca uma manutenção pelo ``id``.

    :raises HTTPException: 404 se não existir.
    """
    manutencao = session.get(Manutencao, id_manutencao)
    if manutencao is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NAO_ENCONTRADA)
    return manutencao


# --------------------------------------------------------------------------- #
# Comandos (todos auditados)
# --------------------------------------------------------------------------- #


def _obter_ou_auditar_falha(
    session: Session, id_manutencao: int, username: str, operacao: str
) -> Manutencao:
    """Como :func:`obter`, mas registra a tentativa malsucedida na auditoria."""
    manutencao = session.get(Manutencao, id_manutencao)

    if manutencao is None:
        registrar_auditoria(
            username, operacao, _RECURSO, "falha", id_manutencao, _NAO_ENCONTRADA,
            session=session,
        )
        session.commit()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NAO_ENCONTRADA)

    return manutencao


def criar(session: Session, dados: ManutencaoBase, username: str) -> ManutencaoSaida:
    """Registra uma nova manutenção."""
    nova = Manutencao(**dados.model_dump())
    session.add(nova)
    session.flush()  # Gera o ``id`` antes do commit, para a auditoria.

    saida = para_saida(nova)

    registrar_auditoria(
        username, "CREATE", _RECURSO, "sucesso", nova.id,
        f"Máquina: {nova.maquina} ({nova.tipo})",
        session=session,
    )
    session.commit()

    return saida


def atualizar(
    session: Session, id_manutencao: int, dados: ManutencaoBase, username: str
) -> ManutencaoSaida:
    """Substitui todos os campos de uma manutenção existente (semântica PUT)."""
    manutencao = _obter_ou_auditar_falha(session, id_manutencao, username, "UPDATE")

    for campo, valor in dados.model_dump().items():
        setattr(manutencao, campo, valor)
    session.flush()

    saida = para_saida(manutencao)

    registrar_auditoria(
        username, "UPDATE", _RECURSO, "sucesso", id_manutencao,
        f"Máquina: {dados.maquina} ({dados.tipo})",
        session=session,
    )
    session.commit()

    return saida


def excluir(session: Session, id_manutencao: int, username: str) -> None:
    """Remove uma manutenção existente."""
    manutencao = _obter_ou_auditar_falha(session, id_manutencao, username, "DELETE")
    maquina = manutencao.maquina

    session.delete(manutencao)

    registrar_auditoria(
        username, "DELETE", _RECURSO, "sucesso", id_manutencao, f"Máquina: {maquina}",
        session=session,
    )
    session.commit()
