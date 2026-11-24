"""Criação do schema, migrações leves e carga inicial de dados.

Executado uma vez na subida da API (ver ``lifespan`` em ``backend.main``).
"""

from __future__ import annotations

import logging
import shutil
import time
from datetime import date
from pathlib import Path
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import inspect
from sqlmodel import Field, Session, SQLModel, select

# Os imports de models abaixo registram as tabelas no ``SQLModel.metadata``.
# Sem eles, ``create_all`` não saberia que essas tabelas existem.
from backend.apps.auditoria.models import LogAuditoria  # noqa: F401
from backend.apps.autenticacao.models import RefreshToken  # noqa: F401
from backend.apps.maquinas.models import Maquina
from backend.apps.manutencoes.models import Manutencao
from backend.apps.usuarios.models import Usuario
from backend.core.config import settings
from backend.core.database import engine
from backend.core.security import PERFIL_ADMIN, gerar_hash_senha

logger = logging.getLogger("uvicorn.error")


class ControleInicializacao(SQLModel, table=True):
    """Registra se a carga de demonstração já foi processada.

    Evita que os registros de exemplo voltem a ser inseridos depois que o
    usuário apagar todas as manutenções.
    """

    id: int = Field(default=1, primary_key=True)
    manutencoes_demo_inseridas: bool = False


#: Máquinas de exemplo (nome, setor) inseridas na primeira execução.
MAQUINAS_DEMO: tuple[tuple[str, str], ...] = (
    ("Bobinadeira 01", "Acabamento"),
    ("Máquina de papel MP-2", "Fabricação de papel"),
    ("Caldeira", "Utilidades"),
    ("Cortadeira CT-3", "Acabamento"),
)

#: Manutenções de exemplo; ``maquina`` é o nome de uma das máquinas acima.
MANUTENCOES_DEMO: tuple[dict, ...] = (
    {"maquina": "Bobinadeira 01", "tipo": "preventiva", "data_manutencao": date(2026, 9, 2),
     "custo": Decimal("850.00"), "horas_paradas": Decimal("4.0")},
    {"maquina": "Máquina de papel MP-2", "tipo": "corretiva", "data_manutencao": date(2026, 9, 18),
     "custo": Decimal("12400.00"), "horas_paradas": Decimal("16.5")},
    {"maquina": "Caldeira", "tipo": "preditiva", "data_manutencao": date(2026, 10, 5),
     "custo": Decimal("1350.00"), "horas_paradas": Decimal("0.0")},
    {"maquina": "Cortadeira CT-3", "tipo": "corretiva", "data_manutencao": date(2026, 10, 21),
     "custo": Decimal("3200.00"), "horas_paradas": Decimal("6.0")},
    {"maquina": "Bobinadeira 01", "tipo": "corretiva", "data_manutencao": date(2026, 11, 10),
     "custo": Decimal("2780.50"), "horas_paradas": Decimal("8.5")},
)


def preparar_banco() -> None:
    """Cria as tabelas e aplica migrações aditivas em bancos de versões antigas.

    O projeto não usa Alembic para manter a simplicidade do estudo de caso;
    em vez disso, colunas novas são adicionadas com ``ALTER TABLE`` quando
    ainda não existem.
    """
    SQLModel.metadata.create_all(engine)
    _migrar_maquina_texto_para_tabela()

    inspetor = inspect(engine)
    colunas_usuario = {c["name"] for c in inspetor.get_columns("usuario")}

    if "role" not in colunas_usuario:
        with engine.begin() as conexao:
            conexao.exec_driver_sql(
                "ALTER TABLE usuario ADD COLUMN role VARCHAR NOT NULL DEFAULT 'usuario'"
            )

    if not inspetor.has_table("refreshtoken"):
        return

    colunas_refresh = {c["name"] for c in inspetor.get_columns("refreshtoken")}

    with engine.begin() as conexao:
        if "ultima_atividade" not in colunas_refresh:
            agora = int(time.time())
            conexao.exec_driver_sql(
                "ALTER TABLE refreshtoken "
                f"ADD COLUMN ultima_atividade INTEGER NOT NULL DEFAULT {agora}"
            )

        if "sessao_id" not in colunas_refresh:
            conexao.exec_driver_sql("ALTER TABLE refreshtoken ADD COLUMN sessao_id VARCHAR")

        if "scopes" not in colunas_refresh:
            conexao.exec_driver_sql(
                "ALTER TABLE refreshtoken ADD COLUMN scopes VARCHAR NOT NULL DEFAULT ''"
            )

        # Refresh tokens de versões anteriores (sem sessão) recebem uma sessão
        # própria para continuarem válidos.
        registros_sem_sessao = conexao.exec_driver_sql(
            "SELECT id FROM refreshtoken WHERE sessao_id IS NULL"
        ).all()

        for (registro_id,) in registros_sem_sessao:
            conexao.exec_driver_sql(
                "UPDATE refreshtoken SET sessao_id = ? WHERE id = ?",
                (uuid4().hex, registro_id),
            )


def _copiar_banco_sqlite(sufixo: str) -> None:
    """Copia o arquivo SQLite antes de uma migração estrutural.

    Rede de segurança adicional: o driver ``sqlite3`` pode confirmar comandos
    DDL fora da transação, então o rollback sozinho não garante a reversão.
    """
    caminho = engine.url.database
    if engine.url.get_backend_name() != "sqlite" or not caminho or caminho == ":memory:":
        return

    origem = Path(caminho)
    if origem.exists():
        destino = origem.with_name(f"{origem.stem}.{sufixo}{origem.suffix}")
        shutil.copy2(origem, destino)
        logger.warning("Migração do banco: cópia de segurança salva em %s", destino)


def _migrar_maquina_texto_para_tabela() -> None:
    """Converte bancos antigos em que ``manutencao.maquina`` era texto livre.

    Passos, todos na mesma transação (falhou, nada muda):

    1. cria uma máquina para cada nome distinto já usado (ignorando
       maiúsculas/minúsculas e espaços nas pontas);
    2. renomeia a tabela antiga e cria a nova a partir do modelo atual;
    3. copia os registros trocando o nome pelo ``maquina_id``;
    4. confere a contagem de linhas e apaga a tabela antiga.

    O SQLite não permite remover/alterar colunas ``NOT NULL`` com
    ``ALTER TABLE``, por isso a tabela é reconstruída.
    """
    inspetor = inspect(engine)
    colunas = {c["name"] for c in inspetor.get_columns("manutencao")}
    if "maquina_id" in colunas or "maquina" not in colunas:
        return  # Banco já está no formato novo.

    _copiar_banco_sqlite("pre-maquinas")

    with engine.begin() as conexao:
        nomes = conexao.exec_driver_sql(
            "SELECT trim(maquina) FROM manutencao GROUP BY lower(trim(maquina)) "
            "ORDER BY min(id)"
        ).scalars().all()

        for nome in nomes:
            existe = conexao.exec_driver_sql(
                "SELECT 1 FROM maquina WHERE lower(nome) = lower(?)", (nome,)
            ).first()
            if existe is None:
                conexao.exec_driver_sql("INSERT INTO maquina (nome) VALUES (?)", (nome,))

        total_antes = conexao.exec_driver_sql("SELECT count(*) FROM manutencao").scalar_one()

        conexao.exec_driver_sql("ALTER TABLE manutencao RENAME TO manutencao_antiga")
        # Índices mantêm o nome ao renomear a tabela; removê-los evita conflito
        # com os índices criados pela nova tabela.
        indices = conexao.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type = 'index' "
            "AND tbl_name = 'manutencao_antiga' AND sql IS NOT NULL"
        ).scalars().all()
        for indice in indices:
            conexao.exec_driver_sql(f'DROP INDEX "{indice}"')

        Manutencao.__table__.create(conexao)
        conexao.exec_driver_sql(
            "INSERT INTO manutencao (id, maquina_id, tipo, data_manutencao, custo, horas_paradas) "
            "SELECT a.id, q.id, a.tipo, a.data_manutencao, a.custo, a.horas_paradas "
            "FROM manutencao_antiga a "
            "JOIN maquina q ON lower(q.nome) = lower(trim(a.maquina))"
        )

        total_depois = conexao.exec_driver_sql("SELECT count(*) FROM manutencao").scalar_one()
        if total_depois != total_antes:
            raise RuntimeError(
                f"Migração de máquinas abortada: {total_antes} registros antes, "
                f"{total_depois} depois. Nenhuma alteração foi gravada."
            )

        conexao.exec_driver_sql("DROP TABLE manutencao_antiga")


def _inserir_manutencoes_demo(session: Session) -> None:
    """Insere os registros de exemplo apenas uma vez na vida do banco."""
    controle = session.get(ControleInicializacao, 1)

    if controle is None:
        # Dados existentes indicam que a carga demonstrativa já ocorreu.
        ja_possui_dados = session.exec(select(Manutencao.id)).first() is not None
        controle = ControleInicializacao(id=1, manutencoes_demo_inseridas=ja_possui_dados)
        session.add(controle)
        session.flush()

    if not controle.manutencoes_demo_inseridas:
        maquinas = {}
        for nome, setor in MAQUINAS_DEMO:
            maquina = session.exec(select(Maquina).where(Maquina.nome == nome)).first()
            if maquina is None:
                maquina = Maquina(nome=nome, setor=setor)
                session.add(maquina)
                session.flush()  # Gera o ``id`` usado pelas manutenções abaixo.
            maquinas[nome] = maquina.id

        session.add_all(
            Manutencao(
                maquina_id=maquinas[dados["maquina"]],
                **{campo: valor for campo, valor in dados.items() if campo != "maquina"},
            )
            for dados in MANUTENCOES_DEMO
        )
        controle.manutencoes_demo_inseridas = True


def _garantir_administrador(session: Session) -> None:
    """Cria o administrador inicial caso ainda não exista nenhum.

    Por segurança, uma conta comum que já use o login configurado **não** é
    promovida automaticamente a administrador.
    """
    if session.exec(select(Usuario).where(Usuario.role == PERFIL_ADMIN)).first():
        return

    username = settings.admin_username
    if session.exec(select(Usuario).where(Usuario.username == username)).first():
        raise RuntimeError(
            f"Já existe '{username}' com perfil comum. "
            "Escolha outro ADMIN_USERNAME ou ajuste o perfil no banco; "
            "a aplicação não promoverá essa conta automaticamente."
        )

    session.add(
        Usuario(
            username=username,
            senha_hash=gerar_hash_senha(settings.admin_senha_inicial),
            role=PERFIL_ADMIN,
        )
    )


def inserir_dados_iniciais() -> None:
    """Executa a carga demo e o provisionamento do admin em uma única transação."""
    with Session(engine) as session:
        _inserir_manutencoes_demo(session)
        _garantir_administrador(session)
        session.commit()


def inicializar_banco() -> None:
    """Ponto único de inicialização usado pelo ``lifespan`` da aplicação."""
    preparar_banco()
    inserir_dados_iniciais()
