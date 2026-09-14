"""Guarda contra o bug de producao: uma coluna que virou opcional no modelo
mas fica esquecida em _RELAX_NOT_NULL nunca é corrigida num banco existente
(SQLite recria do zero em dev, mas Postgres em produção mantém o NOT NULL
antigo até alguém rodar o ALTER). Este teste garante que toda coluna
nullable herdada de uma versão anterior do schema está listada."""

from app.database import _RELAX_NOT_NULL
from app.models import Proposal, Quote

# Colunas que ja existiam como NOT NULL antes de virarem opcionais no
# modelo atual. Se uma nova ficar de fora de _RELAX_NOT_NULL, o INSERT
# funciona no SQLite de dev (tabela sempre criada do zero) mas quebra no
# Postgres de producao (ALTER COLUMN nunca roda para ela).
LEGACY_NULLABLE = {
    Quote: ["qtd_volumes", "valor_nf", "tipo_veiculo", "capacidade_aprox"],
    Proposal: ["frete", "pedagio", "seguro", "total"],
}


def test_relax_not_null_cobre_todas_as_colunas_legadas_opcionais():
    for model, colunas in LEGACY_NULLABLE.items():
        table = model.__tablename__
        assert table in _RELAX_NOT_NULL, f"tabela {table} nao esta em _RELAX_NOT_NULL"
        for coluna in colunas:
            assert coluna in _RELAX_NOT_NULL[table], f"{table}.{coluna} nao esta em _RELAX_NOT_NULL"
            mapped_col = model.__table__.columns[coluna]
            assert mapped_col.nullable, f"{table}.{coluna} devia ser nullable no modelo atual"
