"""Endpoints do app de usuários."""

from fastapi import APIRouter, Security, status

from backend.apps.autenticacao.dependencies import UsuarioAtual, obter_usuario_atual
from backend.apps.usuarios import service
from backend.apps.usuarios.schemas import (
    UsuarioCadastro,
    UsuarioCadastroResponse,
    UsuarioPerfil,
)
from backend.core.database import SessionDep

router = APIRouter(tags=["Usuários"])


@router.post(
    "/usuarios",
    status_code=status.HTTP_201_CREATED,
    response_model=UsuarioCadastroResponse,
)
def cadastrar_usuario(dados: UsuarioCadastro, session: SessionDep):
    """Cadastra um novo usuário com perfil comum (rota pública)."""
    usuario = service.cadastrar_usuario(session, dados)

    return {
        "mensagem": "Usuário cadastrado com sucesso.",
        "id": usuario.id,
        "username": usuario.username,
        "role": usuario.role,
    }


@router.get("/me", response_model=UsuarioPerfil)
def minha_conta(usuario: UsuarioAtual = Security(obter_usuario_atual, scopes=[])):
    """Retorna o perfil e os scopes efetivos da sessão autenticada."""
    return usuario
