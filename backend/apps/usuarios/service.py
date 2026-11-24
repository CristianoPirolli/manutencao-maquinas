"""Regras de negócio do app de usuários."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlmodel import Session, select

from backend.apps.auditoria.service import registrar_auditoria
from backend.apps.usuarios.models import Usuario
from backend.apps.usuarios.schemas import UsuarioCadastro
from backend.core.security import PERFIL_USUARIO, gerar_hash_senha


def buscar_por_username(session: Session, username: str) -> Usuario | None:
    """Busca um usuário pelo login já normalizado."""
    return session.exec(select(Usuario).where(Usuario.username == username)).first()


def cadastrar_usuario(session: Session, dados: UsuarioCadastro) -> Usuario:
    """Cria uma conta com perfil comum.

    Contas de administrador não podem ser criadas por esta via: o único admin
    é provisionado na inicialização do sistema.

    :raises HTTPException: 409 se o login já estiver em uso.
    """
    username = dados.username

    if buscar_por_username(session, username) is not None:
        registrar_auditoria(
            username, "CREATE", "usuario", "negado",
            detalhes="Nome de usuário já cadastrado",
            session=session,
        )
        session.commit()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Nome de usuário já cadastrado",
        )

    usuario = Usuario(
        username=username,
        senha_hash=gerar_hash_senha(dados.senha),
        role=PERFIL_USUARIO,
    )
    session.add(usuario)
    session.flush()  # Garante o ``id`` gerado para o registro de auditoria.

    registrar_auditoria(
        username, "CREATE", "usuario", "sucesso", usuario.id,
        "Novo usuário cadastrado",
        session=session,
    )
    session.commit()
    session.refresh(usuario)

    return usuario
