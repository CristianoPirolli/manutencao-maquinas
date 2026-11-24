"""Endpoints do cadastro de máquinas."""

from fastapi import APIRouter, Security, status

from backend.apps.autenticacao.dependencies import UsuarioAtual, obter_usuario_atual
from backend.apps.maquinas import service
from backend.apps.maquinas.models import MaquinaBase
from backend.apps.maquinas.schemas import (
    IndicadoresMaquina,
    MaquinaOperacaoResponse,
    MaquinaSaida,
)
from backend.core.database import SessionDep
from backend.core.schemas import MensagemResponse

router = APIRouter(prefix="/maquinas", tags=["Máquinas"])


@router.get("", response_model=list[MaquinaSaida])
def listar_maquinas(
    session: SessionDep,
    _usuario: UsuarioAtual = Security(obter_usuario_atual, scopes=["maquinas:read"]),
):
    """Lista as máquinas em ordem alfabética, com o total de manutenções."""
    return service.listar(session)


# Declarada antes de ``/{id_maquina}``: as rotas são testadas em ordem e
# "indicadores" seria recusado como id inválido.
@router.get("/indicadores", response_model=list[IndicadoresMaquina])
def indicadores_confiabilidade(
    session: SessionDep,
    _usuario: UsuarioAtual = Security(
        obter_usuario_atual, scopes=["maquinas:read", "manutencoes:read"]
    ),
):
    """MTTR, MTBF e disponibilidade de cada máquina (só corretivas contam como falha)."""
    return service.indicadores(session)


@router.get("/{id_maquina}", response_model=MaquinaSaida)
def obter_maquina(
    id_maquina: int,
    session: SessionDep,
    _usuario: UsuarioAtual = Security(obter_usuario_atual, scopes=["maquinas:read"]),
):
    """Retorna uma máquina pelo ``id`` (404 se não existir)."""
    return service.para_saida(session, service.obter(session, id_maquina))


@router.post("", status_code=status.HTTP_201_CREATED, response_model=MaquinaOperacaoResponse)
def criar_maquina(
    dados: MaquinaBase,
    session: SessionDep,
    usuario: UsuarioAtual = Security(obter_usuario_atual, scopes=["maquinas:create"]),
):
    """Cadastra uma máquina (409 se o nome já existir)."""
    saida = service.criar(session, dados, usuario["username"])
    return {"mensagem": f"Máquina {saida.nome} cadastrada.", "maquina": saida}


@router.put("/{id_maquina}", response_model=MaquinaOperacaoResponse)
def atualizar_maquina(
    id_maquina: int,
    dados: MaquinaBase,
    session: SessionDep,
    usuario: UsuarioAtual = Security(obter_usuario_atual, scopes=["maquinas:update"]),
):
    """Altera nome e setor de uma máquina."""
    saida = service.atualizar(session, id_maquina, dados, usuario["username"])
    return {"mensagem": f"Máquina {saida.nome} atualizada.", "maquina": saida}


@router.delete("/{id_maquina}", response_model=MensagemResponse)
def excluir_maquina(
    id_maquina: int,
    session: SessionDep,
    usuario: UsuarioAtual = Security(obter_usuario_atual, scopes=["maquinas:delete"]),
):
    """Exclui uma máquina sem manutenções (409 se houver histórico)."""
    nome = service.excluir(session, id_maquina, usuario["username"])
    return {"mensagem": f"Máquina {nome} excluída."}
