"""Engine e sessao do SQLAlchemy."""

from collections.abc import Iterator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

_connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

engine = create_engine(settings.database_url, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Colunas adicionadas depois da primeira versao. create_all() nao altera
# tabelas existentes, entao garantimos as novas colunas manualmente.
# Sem DEFAULT para nao esbarrar em diferencas de sintaxe entre SQLite e
# Postgres; linhas antigas ficam NULL e o app trata NULL como falso/zero.
_ADDED_COLUMNS = {
    "quotes": {
        "carroceria": "VARCHAR(120)",
        "client_company": "VARCHAR(160)",
        "servico_diaria": "BOOLEAN",
        "servico_guincho": "BOOLEAN",
        "decision_note": "TEXT",
        "data_entrega": "DATE",
        "tipo_cotacao": "VARCHAR(20)",
        "dimensoes": "VARCHAR(120)",
        "servico_ajudante": "BOOLEAN",
        "servico_empilhadeira": "BOOLEAN",
        "ajudante_qtd": "INTEGER",
        "peso_total": "VARCHAR(60)",
        "client_cnpj": "VARCHAR(20)",
    },
    "proposals": {
        "custos_adicionais": "NUMERIC(14,2)",
        "custos_adicionais_desc": "TEXT",
        "versao": "INTEGER",
        "custo_motorista": "NUMERIC(14,2)",
        "custo_pedagio": "NUMERIC(14,2)",
        "custo_impostos": "NUMERIC(14,2)",
        "custo_seguro": "NUMERIC(14,2)",
        "custo_outros_internos": "NUMERIC(14,2)",
        "fc": "NUMERIC(14,2)",
        "margem_pct": "NUMERIC(6,2)",
        "fe": "NUMERIC(14,2)",
        "valor_carga": "NUMERIC(14,2)",
        "valor_descarga": "NUMERIC(14,2)",
        "valor_diaria": "NUMERIC(14,2)",
        "valor_ajudante": "NUMERIC(14,2)",
        "valor_empilhadeira": "NUMERIC(14,2)",
        "valor_guincho": "NUMERIC(14,2)",
        "valor_final": "NUMERIC(14,2)",
    },
    "ordens_coleta": {
        "empresa": "VARCHAR(120)",
        "cnpj_filial": "VARCHAR(20)",
        "uf_referencia": "VARCHAR(2)",
    },
}

# Colunas que existiam como NOT NULL na primeira versao e agora precisam
# aceitar NULL (cotacao rapida nao preenche todos os campos da completa).
# SQLite nao suporta ALTER COLUMN ... DROP NOT NULL (exigiria reconstruir a
# tabela); em dev, apague amg.db e rode seed.py de novo apos essa mudanca.
_RELAX_NOT_NULL = {
    "quotes": ["qtd_volumes", "valor_nf", "tipo_veiculo", "capacidade_aprox", "client_email", "peso_total_kg"],
    # frete/pedagio/seguro/total sao as colunas legadas da 1a versao da formacao
    # de preco; o codigo novo nao grava mais nelas (usa fc/fe/adicionais).
    "proposals": ["frete", "pedagio", "seguro", "total"],
}


def _ensure_columns() -> None:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, columns in _ADDED_COLUMNS.items():
            if table not in existing_tables:
                continue
            have = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name not in have:
                    conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {ddl}'))


def _relax_not_null() -> None:
    """Remove NOT NULL de colunas que a cotacao rapida pode deixar em branco.
    So roda em Postgres (idempotente); SQLite e recriado do zero em dev."""
    if engine.dialect.name != "postgresql":
        return
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, columns in _RELAX_NOT_NULL.items():
            if table not in existing_tables:
                continue
            for name in columns:
                conn.execute(text(f'ALTER TABLE {table} ALTER COLUMN {name} DROP NOT NULL'))


def _migrate_statuses() -> None:
    """Converte os status antigos (aceita / ajuste_solicitado) para os novos."""
    from app.constants import STATUS_LEGADO

    inspector = inspect(engine)
    if "quotes" not in set(inspector.get_table_names()):
        return
    with engine.begin() as conn:
        for antigo, novo in STATUS_LEGADO.items():
            conn.execute(
                text("UPDATE quotes SET status = :novo WHERE status = :antigo"),
                {"novo": novo, "antigo": antigo},
            )


def _fix_opcoes_ortografia() -> None:
    """Corrige o nome de opcoes semeadas antes da correcao ortografica
    (ex.: 'Bau' -> 'Baú'). So atualiza linhas que ainda tem o nome antigo
    exato -- idempotente, nao mexe em nada que o admin ja tenha renomeado."""
    from app.constants import OPCOES_ORTOGRAFIA_LEGADO

    inspector = inspect(engine)
    if "opcoes" not in set(inspector.get_table_names()):
        return
    with engine.begin() as conn:
        for categoria, nomes in OPCOES_ORTOGRAFIA_LEGADO.items():
            for antigo, novo in nomes.items():
                conn.execute(
                    text("UPDATE opcoes SET nome = :novo WHERE categoria = :categoria AND nome = :antigo"),
                    {"novo": novo, "categoria": categoria, "antigo": antigo},
                )


def _seed_opcoes() -> None:
    """Cria a carga inicial de cada categoria de opcao (carroceria, tipo de
    veiculo...) apenas se essa categoria ainda nao tiver nenhuma opcao."""
    from app.constants import OPCOES_PADRAO
    from app.models import Opcao

    with SessionLocal() as db:
        for categoria, nomes in OPCOES_PADRAO.items():
            ja_tem = db.query(Opcao).filter_by(categoria=categoria).count() > 0
            if not ja_tem:
                db.add_all(Opcao(categoria=categoria, nome=n) for n in nomes)
        db.commit()


def init_db() -> None:
    """Cria/atualiza as tabelas. Chamado no startup da aplicacao."""
    from app import models  # noqa: F401  (garante o registro dos modelos)

    Base.metadata.create_all(bind=engine)
    _ensure_columns()
    _relax_not_null()
    _migrate_statuses()
    _fix_opcoes_ortografia()
    _seed_opcoes()
