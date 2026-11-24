"""Configurações centrais do backend.

Todos os valores sensíveis ou dependentes de ambiente podem ser sobrescritos por
variáveis de ambiente. Os valores-padrão existem apenas para facilitar a
execução local do estudo de caso e **não devem ser usados em produção**.

Variáveis suportadas:

=========================  ====================================================
``DATABASE_URL``           URL SQLAlchemy do banco (padrão: SQLite na raiz).
``JWT_SECRET``             Chave HS256 com no mínimo 32 bytes.
``ADMIN_USERNAME``         Login do administrador criado na primeira execução.
``ADMIN_INITIAL_PASSWORD`` Senha inicial desse administrador.
``CORS_ORIGINS``           Origens permitidas, separadas por vírgula (padrão ``*``).
=========================  ====================================================
"""

from __future__ import annotations

import os
import warnings
from dataclasses import dataclass
from pathlib import Path

#: Diretório raiz do repositório (pai do pacote ``backend``).
DIRETORIO_RAIZ = Path(__file__).resolve().parents[2]

_BANCO_PADRAO = f"sqlite:///{(DIRETORIO_RAIZ / 'manutencao.db').as_posix()}"

# Chave local apenas para o exemplo didático. Em outros ambientes, configure
# JWT_SECRET com uma chave aleatória de pelo menos 32 bytes.
_CHAVE_DESENVOLVIMENTO = "chave-local-de-desenvolvimento-com-mais-de-32-bytes"


@dataclass(frozen=True)
class Configuracoes:
    """Conjunto imutável de configurações da aplicação."""

    nome_api: str
    versao_api: str
    database_url: str
    jwt_secret: str
    jwt_algoritmo: str
    access_token_minutos: int
    sessao_inatividade_minutos: int
    refresh_token_dias: int
    admin_username: str
    admin_senha_inicial: str
    cors_origens: tuple[str, ...]

    @property
    def access_token_segundos(self) -> int:
        """Validade do access token, em segundos."""
        return self.access_token_minutos * 60

    @property
    def sessao_inatividade_segundos(self) -> int:
        """Tempo máximo sem atividade antes de a sessão ser encerrada."""
        return self.sessao_inatividade_minutos * 60

    @property
    def refresh_token_segundos(self) -> int:
        """Validade absoluta do refresh token, em segundos."""
        return self.refresh_token_dias * 24 * 60 * 60


def _validar(config: Configuracoes) -> None:
    """Falha cedo (na subida da API) se alguma configuração for inválida."""
    if config.jwt_secret == _CHAVE_DESENVOLVIMENTO:
        # A chave-padrão é pública (está no repositório): qualquer pessoa pode
        # assinar tokens com ela. Aceitável apenas para estudo local.
        warnings.warn(
            "JWT_SECRET não definido: usando a chave de desenvolvimento. "
            "Defina JWT_SECRET fora do ambiente local.",
            RuntimeWarning,
            stacklevel=2,
        )

    if len(config.jwt_secret.encode("utf-8")) < 32:
        raise RuntimeError("JWT_SECRET deve ter pelo menos 32 bytes para HS256.")

    if not 3 <= len(config.admin_username) <= 50:
        raise RuntimeError("ADMIN_USERNAME deve ter entre 3 e 50 caracteres.")

    if len(config.admin_senha_inicial) < 6:
        raise RuntimeError("ADMIN_INITIAL_PASSWORD deve ter pelo menos 6 caracteres.")


def carregar_configuracoes() -> Configuracoes:
    """Lê as variáveis de ambiente e devolve as configurações validadas."""
    origens = os.getenv("CORS_ORIGINS", "*")

    config = Configuracoes(
        nome_api="API de Manutenção de Máquinas",
        versao_api="9.0",
        database_url=os.getenv("DATABASE_URL", _BANCO_PADRAO),
        jwt_secret=os.getenv("JWT_SECRET", _CHAVE_DESENVOLVIMENTO),
        jwt_algoritmo="HS256",
        access_token_minutos=15,
        sessao_inatividade_minutos=30,
        refresh_token_dias=7,
        admin_username=os.getenv("ADMIN_USERNAME", "admin").strip().lower(),
        admin_senha_inicial=os.getenv("ADMIN_INITIAL_PASSWORD", "admin123"),
        cors_origens=tuple(o.strip() for o in origens.split(",") if o.strip()),
    )

    _validar(config)
    return config


#: Instância única usada por todo o backend.
settings = carregar_configuracoes()
