"""Regras de negócio do app de auditoria."""

from __future__ import annotations

from sqlmodel import Session, select

from backend.apps.auditoria.models import LogAuditoria
from backend.core.database import engine


def registrar_auditoria(
    usuario: str,
    operacao: str,
    recurso: str,
    resultado: str,
    recurso_id: int | None = None,
    detalhes: str | None = None,
    *,
    session: Session | None = None,
) -> None:
    """Registra uma entrada de auditoria.

    - Com ``session``: o log é apenas adicionado e será gravado no mesmo
      ``commit`` da operação auditada (atomicidade entre ação e registro).
    - Sem ``session``: o log é gravado imediatamente em uma sessão própria.
      Útil quando a sessão principal sofreu ``rollback`` ou ainda não existe.
    """
    log = LogAuditoria(
        usuario=usuario or "desconhecido",
        operacao=operacao,
        recurso=recurso,
        recurso_id=recurso_id,
        resultado=resultado,
        detalhes=detalhes,
    )

    if session is not None:
        session.add(log)
        return

    with Session(engine) as nova_session:
        nova_session.add(log)
        nova_session.commit()


def listar_ultimos(session: Session, limite: int) -> list[LogAuditoria]:
    """Retorna os ``limite`` registros mais recentes, do mais novo ao mais antigo."""
    return list(
        session.exec(
            select(LogAuditoria).order_by(LogAuditoria.id.desc()).limit(limite)
        ).all()
    )
