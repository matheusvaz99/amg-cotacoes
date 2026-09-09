from datetime import date, timedelta
from decimal import Decimal

from app import crud
from app.database import SessionLocal
from app.pdf import build_quote_pdf


def _make_quote(db, **over):
    data = dict(
        client_name="José da Silva",
        client_company="Construtora São José",
        client_email="compras@saojose.com.br",
        client_phone="(41) 99999-0000",
        origem_cidade="São Paulo - SP",
        origem_cep="01001-000",
        origem_endereco="Av. Paulista, 1000",
        origem_bairro="Bela Vista",
        destino_cidade="Curitiba - PR",
        destino_cep=None,
        destino_endereco=None,
        destino_bairro=None,
        tipo_material="Andaime",
        descricao_material="Tubos e acessórios",
        qtd_volumes=10,
        peso_total_kg=Decimal("5000.00"),
        valor_nf=Decimal("25000.00"),
        servico_carga=True,
        servico_descarga=False,
        servico_diaria=False,
        servico_guincho=True,
        tipo_veiculo="Carreta Sider",
        carroceria="Sider",
        capacidade_aprox="28 toneladas",
        data_coleta=date.today() + timedelta(days=5),
        observacoes="Acesso fácil — cais nível 2 → doca 5",
    )
    data.update(over)
    return crud.create_quote(db, data)


def test_pdf_without_proposal_is_valid_pdf():
    with SessionLocal() as db:
        quote = _make_quote(db)
        pdf = build_quote_pdf(quote)
    assert pdf[:5] == b"%PDF-"
    assert pdf.rstrip().endswith(b"%%EOF")
    assert len(pdf) > 1500


def test_pdf_with_proposal_and_accents():
    with SessionLocal() as db:
        quote = _make_quote(db, carroceria=None)
        crud.add_proposal(
            db,
            quote,
            dict(
                frete=Decimal("2900.00"),
                pedagio=Decimal("50.00"),
                seguro=Decimal("50.00"),
                total=Decimal("3000.00"),
                custos_adicionais=Decimal("350.00"),
                custos_adicionais_desc="Guincho no destino",
                prazo_entrega="1 dia útil",
                validade=date.today() + timedelta(days=7),
                observacoes="Valores sujeitos à confirmação na contratação.",
            ),
            created_by="tester",
        )
        db.refresh(quote)
        assert quote.proposal.valor_final == Decimal("3350.00")
        pdf = build_quote_pdf(quote)
    assert pdf[:5] == b"%PDF-"
    assert len(pdf) > 1800
