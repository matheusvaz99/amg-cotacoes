"""Popula o banco com cotacoes de exemplo para testar o painel.

Uso:  python seed.py
"""

from datetime import date, timedelta
from decimal import Decimal

from app.crud import add_proposal, create_quote
from app.database import SessionLocal, init_db
from app.utils import calc_seguro

EXEMPLOS = [
    dict(
        client_name="Construtora Alfa", client_email="compras@alfa.com.br",
        client_phone="(41) 99999-0001",
        origem_cidade="Curitiba - PR", origem_cep="80010-000", origem_endereco="Rua das Industrias, 100", origem_bairro="CIC",
        destino_cidade="Londrina - PR", destino_cep="86010-000", destino_endereco="Av. Tiradentes, 500", destino_bairro="Centro",
        tipo_material="Andaime", descricao_material="Tubos e acessorios de andaime",
        qtd_volumes=10, peso_total_kg=Decimal("5000.00"), valor_nf=Decimal("25000.00"),
        servico_carga=False, servico_descarga=True,
        tipo_veiculo="Carreta Sider", carroceria="Sider", capacidade_aprox="28 toneladas",
        data_coleta=date.today() + timedelta(days=5),
        observacoes="Acesso facil para carga e descarga.",
    ),
    dict(
        client_name="Metalurgica Beta", client_email="logistica@beta.com.br",
        client_phone=None,
        origem_cidade="Itajai - SC", destino_cidade="Maringa - PR",
        tipo_material="Estrutura metalica", descricao_material=None,
        qtd_volumes=4, peso_total_kg=Decimal("12000.00"), valor_nf=Decimal("80000.00"),
        servico_carga=True, servico_descarga=True,
        tipo_veiculo="Carreta Grade Baixa", carroceria="Grade baixa",
        capacidade_aprox="30 toneladas",
        data_coleta=date.today() + timedelta(days=8), observacoes=None,
    ),
    dict(
        client_name="Obras Gamma", client_email="gamma@obras.com.br",
        client_phone="(11) 98888-1234",
        origem_cidade="Sao Paulo - SP", destino_cidade="Curitiba - PR",
        tipo_material="Material de construcao", descricao_material="Blocos e cimento",
        qtd_volumes=30, peso_total_kg=Decimal("18000.00"), valor_nf=Decimal("42000.00"),
        servico_carga=False, servico_descarga=False,
        tipo_veiculo="Truck", carroceria="Bau", capacidade_aprox="14 toneladas",
        data_coleta=date.today() + timedelta(days=3), observacoes="Entrega em horario comercial.",
    ),
]


def run() -> None:
    init_db()
    db = SessionLocal()
    try:
        for data in EXEMPLOS:
            quote = create_quote(db, data)
            print("criada", quote.code, "-", quote.rota)

        # responde a primeira com uma proposta
        first = create_quote(
            db,
            dict(
                client_name="Cliente Demo", client_email="demo@exemplo.com",
                client_phone=None,
                origem_cidade="Joinville - SC", destino_cidade="Londrina - PR",
                tipo_material="Escoramento", descricao_material=None,
                qtd_volumes=6, peso_total_kg=Decimal("4200.00"), valor_nf=Decimal("14000.00"),
                servico_carga=True, servico_descarga=False,
                tipo_veiculo="Toco", carroceria="Graneleiro", capacidade_aprox="6 toneladas",
                data_coleta=date.today() + timedelta(days=4), observacoes=None,
            ),
        )
        add_proposal(
            db, first,
            dict(
                frete=Decimal("2900.00"), pedagio=Decimal("50.00"),
                seguro=calc_seguro(first.valor_nf),
                total=Decimal("2900.00") + Decimal("50.00") + calc_seguro(first.valor_nf),
                prazo_entrega="1 dia util",
                validade=date.today() + timedelta(days=7),
                observacoes="Valores sujeitos a confirmacao na contratacao.",
            ),
            created_by="seed",
        )
        print("respondida", first.code)
    finally:
        db.close()


if __name__ == "__main__":
    run()
