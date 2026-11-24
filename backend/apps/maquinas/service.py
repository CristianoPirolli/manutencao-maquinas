"""Regras de negócio do app de máquinas."""

from __future__ import annotations

from typing import NoReturn

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlmodel import Session, select

from backend.apps.auditoria.service import registrar_auditoria
from backend.apps.maquinas.indicadores import Falha, calcular
from backend.apps.maquinas.models import Maquina, MaquinaBase
from backend.apps.maquinas.schemas import IndicadoresMaquina, MaquinaSaida
from backend.apps.manutencoes.models import Manutencao

_RECURSO = "maquina"
_NAO_ENCONTRADA = "Máquina não encontrada"


# --------------------------------------------------------------------------- #
# Consultas
# --------------------------------------------------------------------------- #


def _total_manutencoes(session: Session, id_maquina: int) -> int:
    return session.exec(
        select(func.count()).select_from(Manutencao).where(Manutencao.maquina_id == id_maquina)
    ).one()


def para_saida(session: Session, maquina: Maquina) -> MaquinaSaida:
    """Converte a entidade no schema de saída, com a contagem de manutenções."""
    return MaquinaSaida(
        id=maquina.id,
        nome=maquina.nome,
        setor=maquina.setor,
        total_manutencoes=_total_manutencoes(session, maquina.id),
    )


def listar(session: Session) -> list[MaquinaSaida]:
    """Lista as máquinas em ordem alfabética, com o total de manutenções de cada uma.

    Usa ``LEFT JOIN`` para incluir também as máquinas sem nenhuma manutenção.
    """
    total = func.count(Manutencao.id).label("total")
    linhas = session.exec(
        select(Maquina, total)
        .join(Manutencao, Manutencao.maquina_id == Maquina.id, isouter=True)
        .group_by(Maquina.id)
        .order_by(func.lower(Maquina.nome))
    ).all()

    return [
        MaquinaSaida(id=m.id, nome=m.nome, setor=m.setor, total_manutencoes=qtd)
        for m, qtd in linhas
    ]


def indicadores(session: Session) -> list[IndicadoresMaquina]:
    """MTTR, MTBF e disponibilidade de cada máquina, a partir das corretivas.

    As fórmulas estão em :mod:`backend.apps.maquinas.indicadores`. Máquinas
    sem falhas também aparecem, com os indicadores nulos.
    """
    corretivas = session.exec(
        select(Manutencao.maquina_id, Manutencao.data_manutencao, Manutencao.horas_paradas)
        .where(Manutencao.tipo == "corretiva")
    ).all()

    falhas_por_maquina: dict[int, list[Falha]] = {}
    for maquina_id, data, horas in corretivas:
        falhas_por_maquina.setdefault(maquina_id, []).append(Falha(data, horas))

    maquinas = session.exec(select(Maquina).order_by(func.lower(Maquina.nome))).all()
    resultado = []
    for maquina in maquinas:
        calculo = calcular(falhas_por_maquina.get(maquina.id, []))
        resultado.append(
            IndicadoresMaquina(
                maquina_id=maquina.id,
                maquina=maquina.nome,
                setor=maquina.setor,
                falhas=calculo.falhas,
                mttr_horas=calculo.mttr_horas,
                mtbf_horas=calculo.mtbf_horas,
                disponibilidade=calculo.disponibilidade,
            )
        )
    return resultado


def obter(session: Session, id_maquina: int) -> Maquina:
    """Busca uma máquina pelo ``id``.

    :raises HTTPException: 404 se não existir.
    """
    maquina = session.get(Maquina, id_maquina)
    if maquina is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NAO_ENCONTRADA)
    return maquina


def buscar_por_nome(session: Session, nome: str) -> Maquina | None:
    """Busca por nome sem diferenciar maiúsculas de minúsculas."""
    return session.exec(
        select(Maquina).where(func.lower(Maquina.nome) == nome.strip().lower())
    ).first()


# --------------------------------------------------------------------------- #
# Comandos (todos auditados)
# --------------------------------------------------------------------------- #


def _recusar(session: Session, username: str, operacao: str, recurso_id: int | None,
             status_code: int, detalhe: str) -> NoReturn:
    """Audita a tentativa recusada e interrompe com o status informado."""
    registrar_auditoria(username, operacao, _RECURSO, "negado", recurso_id, detalhe, session=session)
    session.commit()
    raise HTTPException(status_code=status_code, detail=detalhe)


def _garantir_nome_livre(session: Session, nome: str, username: str, operacao: str,
                         id_atual: int | None = None) -> None:
    """Impede duas máquinas com o mesmo nome (409)."""
    existente = buscar_por_nome(session, nome)
    if existente is not None and existente.id != id_atual:
        _recusar(
            session, username, operacao, id_atual, status.HTTP_409_CONFLICT,
            f"Já existe uma máquina chamada {existente.nome}.",
        )


def _obter_ou_auditar_falha(session: Session, id_maquina: int, username: str, operacao: str) -> Maquina:
    """Como :func:`obter`, mas registra a tentativa malsucedida na auditoria."""
    maquina = session.get(Maquina, id_maquina)
    if maquina is None:
        registrar_auditoria(
            username, operacao, _RECURSO, "falha", id_maquina, _NAO_ENCONTRADA, session=session
        )
        session.commit()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NAO_ENCONTRADA)
    return maquina


def criar(session: Session, dados: MaquinaBase, username: str) -> MaquinaSaida:
    """Cadastra uma nova máquina."""
    _garantir_nome_livre(session, dados.nome, username, "CREATE")

    nova = Maquina(**dados.model_dump())
    session.add(nova)
    session.flush()

    saida = para_saida(session, nova)
    registrar_auditoria(
        username, "CREATE", _RECURSO, "sucesso", nova.id, f"Máquina: {nova.nome}", session=session
    )
    session.commit()
    return saida


def atualizar(session: Session, id_maquina: int, dados: MaquinaBase, username: str) -> MaquinaSaida:
    """Altera nome e setor. As manutenções passam a exibir o novo nome."""
    maquina = _obter_ou_auditar_falha(session, id_maquina, username, "UPDATE")
    _garantir_nome_livre(session, dados.nome, username, "UPDATE", id_atual=id_maquina)

    nome_anterior = maquina.nome
    maquina.nome = dados.nome
    maquina.setor = dados.setor
    session.flush()

    saida = para_saida(session, maquina)
    detalhe = (
        f"Máquina: {nome_anterior} renomeada para {maquina.nome}"
        if nome_anterior != maquina.nome
        else f"Máquina: {maquina.nome}"
    )
    registrar_auditoria(username, "UPDATE", _RECURSO, "sucesso", id_maquina, detalhe, session=session)
    session.commit()
    return saida


def excluir(session: Session, id_maquina: int, username: str) -> str:
    """Exclui uma máquina sem manutenções e devolve o nome excluído.

    Máquinas com histórico não podem ser excluídas (409): apagar a máquina
    deixaria manutenções sem referência e distorceria os indicadores.
    """
    maquina = _obter_ou_auditar_falha(session, id_maquina, username, "DELETE")
    total = _total_manutencoes(session, id_maquina)

    if total:
        _recusar(
            session, username, "DELETE", id_maquina, status.HTTP_409_CONFLICT,
            f"{maquina.nome} possui {total} manutenção(ões) registrada(s) e não pode ser excluída.",
        )

    nome = maquina.nome
    session.delete(maquina)
    registrar_auditoria(
        username, "DELETE", _RECURSO, "sucesso", id_maquina, f"Máquina: {nome}", session=session
    )
    session.commit()
    return nome
