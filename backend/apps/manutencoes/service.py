"""Regras de negócio do app de manutenções."""

from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlmodel import Session, select

from backend.apps.auditoria.service import registrar_auditoria
from backend.apps.maquinas.models import Maquina
from backend.apps.manutencoes.models import Manutencao, ManutencaoBase, TipoManutencao
from backend.apps.manutencoes.schemas import ManutencaoSaida

_RECURSO = "manutencao"
_NAO_ENCONTRADA = "Manutenção não encontrada"


# --------------------------------------------------------------------------- #
# Conversões
# --------------------------------------------------------------------------- #


def para_item(manutencao: Manutencao, nome_maquina: str) -> dict:
    """Converte a entidade no formato usado pelas listagens (sem ``id``)."""
    return {
        "maquina_id": manutencao.maquina_id,
        "maquina": nome_maquina,
        "tipo": manutencao.tipo,
        "data_manutencao": manutencao.data_manutencao,
        "custo": manutencao.custo,
        "horas_paradas": manutencao.horas_paradas,
    }


def para_saida(manutencao: Manutencao, nome_maquina: str) -> ManutencaoSaida:
    """Converte a entidade no schema completo de saída."""
    return ManutencaoSaida(id=manutencao.id, **para_item(manutencao, nome_maquina))


def indexar_por_id(linhas: list[tuple[Manutencao, str]]) -> dict[int, dict]:
    """Monta o dicionário ``{id: manutencao}`` devolvido pelas listagens.

    O formato de dicionário foi mantido por compatibilidade com o roteiro
    original (``GET /vendas`` também retornava ``{id: venda}``).
    """
    return {m.id: para_item(m, nome) for m, nome in linhas}


# --------------------------------------------------------------------------- #
# Consultas
# --------------------------------------------------------------------------- #


def _com_nome_maquina():
    """``SELECT`` base: cada manutenção acompanhada do nome da sua máquina."""
    return select(Manutencao, Maquina.nome).join(Maquina, Maquina.id == Manutencao.maquina_id)


def listar(session: Session) -> list[tuple[Manutencao, str]]:
    """Retorna todas as manutenções em ordem de ``id``."""
    return list(session.exec(_com_nome_maquina().order_by(Manutencao.id)).all())


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
    maquina_id: int | None = None,
    tipo: TipoManutencao | None = None,
    min_horas: Decimal | None = None,
) -> list[tuple[Manutencao, str]]:
    """Filtra manutenções; os filtros informados são combinados com ``AND``.

    :param maquina: trecho do nome da máquina (busca por "contém").
    :param maquina_id: máquina exata.
    :param tipo: tipo exato da manutenção.
    :param min_horas: mínimo de horas paradas.
    :returns: pares (manutenção, nome da máquina), da mais recente para a mais antiga.
    """
    comando = _com_nome_maquina()

    if maquina and maquina.strip():
        comando = comando.where(Maquina.nome.contains(maquina.strip()))

    if maquina_id is not None:
        comando = comando.where(Manutencao.maquina_id == maquina_id)

    if tipo is not None:
        comando = comando.where(Manutencao.tipo == tipo)

    if min_horas is not None:
        comando = comando.where(Manutencao.horas_paradas >= min_horas)

    comando = comando.order_by(Manutencao.data_manutencao.desc(), Manutencao.id)
    return list(session.exec(comando).all())


def obter(session: Session, id_manutencao: int) -> tuple[Manutencao, str]:
    """Busca uma manutenção (e o nome da máquina) pelo ``id``.

    :raises HTTPException: 404 se não existir.
    """
    linha = session.exec(_com_nome_maquina().where(Manutencao.id == id_manutencao)).first()
    if linha is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NAO_ENCONTRADA)
    return linha


# --------------------------------------------------------------------------- #
# Comandos (todos auditados)
# --------------------------------------------------------------------------- #


def _maquina_ou_422(session: Session, maquina_id: int, username: str, operacao: str,
                    recurso_id: int | None = None) -> Maquina:
    """Garante que a máquina referenciada existe (422 caso contrário)."""
    maquina = session.get(Maquina, maquina_id)
    if maquina is None:
        detalhe = f"Máquina {maquina_id} não cadastrada"
        registrar_auditoria(username, operacao, _RECURSO, "falha", recurso_id, detalhe, session=session)
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Máquina não cadastrada. Cadastre a máquina antes de registrar a manutenção.",
        )
    return maquina


def _obter_ou_auditar_falha(
    session: Session, id_manutencao: int, username: str, operacao: str
) -> Manutencao:
    """Busca a manutenção ou registra a tentativa malsucedida na auditoria."""
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
    """Registra uma nova manutenção para uma máquina cadastrada."""
    maquina = _maquina_ou_422(session, dados.maquina_id, username, "CREATE")

    nova = Manutencao(**dados.model_dump())
    session.add(nova)
    session.flush()  # Gera o ``id`` antes do commit, para a auditoria.

    saida = para_saida(nova, maquina.nome)
    registrar_auditoria(
        username, "CREATE", _RECURSO, "sucesso", nova.id,
        f"Máquina: {maquina.nome} ({nova.tipo})",
        session=session,
    )
    session.commit()
    return saida


def atualizar(
    session: Session, id_manutencao: int, dados: ManutencaoBase, username: str
) -> ManutencaoSaida:
    """Substitui todos os campos de uma manutenção existente (semântica PUT)."""
    manutencao = _obter_ou_auditar_falha(session, id_manutencao, username, "UPDATE")
    maquina = _maquina_ou_422(session, dados.maquina_id, username, "UPDATE", id_manutencao)

    for campo, valor in dados.model_dump().items():
        setattr(manutencao, campo, valor)
    session.flush()

    saida = para_saida(manutencao, maquina.nome)
    registrar_auditoria(
        username, "UPDATE", _RECURSO, "sucesso", id_manutencao,
        f"Máquina: {maquina.nome} ({dados.tipo})",
        session=session,
    )
    session.commit()
    return saida


def excluir(session: Session, id_manutencao: int, username: str) -> None:
    """Remove uma manutenção existente."""
    manutencao = _obter_ou_auditar_falha(session, id_manutencao, username, "DELETE")
    maquina = session.get(Maquina, manutencao.maquina_id)
    nome = maquina.nome if maquina else f"#{manutencao.maquina_id}"

    session.delete(manutencao)
    registrar_auditoria(
        username, "DELETE", _RECURSO, "sucesso", id_manutencao, f"Máquina: {nome}",
        session=session,
    )
    session.commit()
