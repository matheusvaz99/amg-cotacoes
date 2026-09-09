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
    },
    "proposals": {
        "custos_adicionais": "NUMERIC(14,2)",
        "custos_adicionais_desc": "TEXT",
    },
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
    _migrate_statuses()
    _seed_opcoes()
