"""Endpoints do CRUD de manutenções.

Atenção à ordem: as rotas fixas (``/qtd``, ``/resumo``, ``/busca``) precisam
ser declaradas antes de ``/{id_manutencao}``; caso contrário o FastAPI tentaria
interpretar ``"qtd"`` como um id inteiro e responderia 422.
"""

from decimal import Decimal

from fastapi import APIRouter, Query, Security, status

from backend.apps.autenticacao.dependencies import UsuarioAtual, obter_usuario_atual
from backend.apps.manutencoes import service
from backend.apps.manutencoes.models import ManutencaoBase, TipoManutencao
from backend.apps.manutencoes.schemas import (
    ManutencaoBuscaItem,
    ManutencaoOperacaoResponse,
    ManutencaoSaida,
    QuantidadeManutencoesResponse,
    ResumoCustosResponse,
)
from backend.core.database import SessionDep
from backend.core.schemas import MensagemResponse

router = APIRouter(prefix="/manutencoes", tags=["Manutenções"])


@router.get("", response_model=dict[int, ManutencaoBuscaItem])
def listar_manutencoes(
    session: SessionDep,
    _usuario: UsuarioAtual = Security(obter_usuario_atual, scopes=["manutencoes:read"]),
):
    """Lista todas as manutenções no formato ``{id: manutencao}``."""
    return service.indexar_por_id(service.listar(session))


@router.get("/qtd", response_model=QuantidadeManutencoesResponse)
def qtd_manutencoes(
    session: SessionDep,
    _usuario: UsuarioAtual = Security(obter_usuario_atual, scopes=["manutencoes:read"]),
):
    """Retorna a quantidade total de manutenções."""
    return {"quantidade_total": service.contar(session)}


@router.get("/resumo", response_model=ResumoCustosResponse)
def resumo_custos(
    session: SessionDep,
    _usuario: UsuarioAtual = Security(obter_usuario_atual, scopes=["manutencoes:read"]),
):
    """Retorna o custo total e o total de horas paradas."""
    return service.resumir_custos(session)


@router.get("/busca", response_model=dict[int, ManutencaoBuscaItem])
def buscar_manutencoes(
    session: SessionDep,
    maquina: str | None = Query(None, description="Parte do nome da máquina"),
    maquina_id: int | None = Query(None, gt=0, description="Id exato da máquina"),
    tipo: TipoManutencao | None = Query(None, description="preventiva, corretiva ou preditiva"),
    min_horas: Decimal | None = Query(None, ge=0, description="Mínimo de horas paradas"),
    _usuario: UsuarioAtual = Security(obter_usuario_atual, scopes=["manutencoes:read"]),
):
    """Busca manutenções combinando os filtros informados."""
    linhas = service.buscar(
        session, maquina=maquina, maquina_id=maquina_id, tipo=tipo, min_horas=min_horas
    )
    return service.indexar_por_id(linhas)


@router.get("/{id_manutencao}", response_model=ManutencaoSaida)
def obter_manutencao(
    id_manutencao: int,
    session: SessionDep,
    _usuario: UsuarioAtual = Security(obter_usuario_atual, scopes=["manutencoes:read"]),
):
    """Retorna uma manutenção pelo ``id`` (404 se não existir)."""
    manutencao, nome_maquina = service.obter(session, id_manutencao)
    return service.para_saida(manutencao, nome_maquina)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ManutencaoOperacaoResponse,
)
def criar_manutencao(
    manutencao: ManutencaoBase,
    session: SessionDep,
    usuario: UsuarioAtual = Security(obter_usuario_atual, scopes=["manutencoes:create"]),
):
    """Registra uma nova manutenção."""
    saida = service.criar(session, manutencao, usuario["username"])
    return {
        "mensagem": f"Manutenção registrada por {usuario['username']}.",
        "manutencao": saida,
    }


@router.put("/{id_manutencao}", response_model=ManutencaoOperacaoResponse)
def atualizar_manutencao(
    id_manutencao: int,
    dados: ManutencaoBase,
    session: SessionDep,
    usuario: UsuarioAtual = Security(obter_usuario_atual, scopes=["manutencoes:update"]),
):
    """Atualiza todos os campos de uma manutenção existente."""
    saida = service.atualizar(session, id_manutencao, dados, usuario["username"])
    return {
        "mensagem": f"Manutenção {id_manutencao} atualizada por {usuario['username']}.",
        "manutencao": saida,
    }


@router.delete("/{id_manutencao}", response_model=MensagemResponse)
def excluir_manutencao(
    id_manutencao: int,
    session: SessionDep,
    usuario: UsuarioAtual = Security(obter_usuario_atual, scopes=["manutencoes:delete"]),
):
    """Exclui uma manutenção (somente administradores)."""
    service.excluir(session, id_manutencao, usuario["username"])
    return {"mensagem": f"Manutenção {id_manutencao} excluída por {usuario['username']}."}
