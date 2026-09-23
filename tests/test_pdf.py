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
        tipo_cotacao="completa",
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
        dimensoes=None,
        qtd_volumes=10,
        peso_total_kg=Decimal("5000.00"),
        valor_nf=Decimal("25000.00"),
        servico_diaria=False,
        servico_ajudante=False,
        servico_empilhadeira=False,
        servico_guincho=True,
        ajudante_qtd=None,
        tipo_veiculo="Carreta Sider",
        carroceria="Sider",
        capacidade_aprox="28 toneladas",
        data_coleta=date.today() + timedelta(days=5),
        data_entrega=None,
        observacoes="Acesso fácil — cais nível 2 → doca 5",
    )
    data.update(over)
    return crud.create_quote(db, data)


def _proposal_values(**over):
    values = dict(
        custo_motorista=Decimal("2900.00"), custo_pedagio=Decimal("50.00"),
        custo_impostos=Decimal("0.00"), custo_seguro=Decimal("50.00"),
        custo_outros_internos=Decimal("0.00"), fc=Decimal("3000.00"),
        margem_pct=Decimal("0.00"), fe=Decimal("3000.00"),
        valor_diaria=Decimal("0.00"), valor_ajudante=Decimal("0.00"),
        valor_empilhadeira=Decimal("0.00"), valor_guincho=Decimal("350.00"),
        custos_adicionais=Decimal("0.00"), custos_adicionais_desc=None,
        valor_final=Decimal("3350.00"),
        prazo_entrega="1 dia útil", validade=date.today() + timedelta(days=7),
        observacoes="Valores sujeitos à confirmação na contratação.",
    )
    values.update(over)
    return values


def test_pdf_without_proposal_is_valid_pdf():
    with SessionLocal() as db:
        quote = _make_quote(db)
        pdf = build_quote_pdf(quote)
    assert pdf[:5] == b"%PDF-"
    assert pdf.rstrip().endswith(b"%%EOF")
    assert len(pdf) > 1500


def test_pdf_without_proposal_rapida_com_campos_ausentes():
    with SessionLocal() as db:
        quote = _make_quote(
            db, tipo_cotacao="rapida", qtd_volumes=None, valor_nf=None,
            tipo_veiculo=None, carroceria=None, capacidade_aprox=None,
        )
        pdf = build_quote_pdf(quote)
    assert pdf[:5] == b"%PDF-"


def test_pdf_with_proposal_and_accents():
    with SessionLocal() as db:
        quote = _make_quote(db, carroceria=None)
        crud.add_proposal(db, quote, _proposal_values(), created_by="tester")
        db.refresh(quote)
        assert quote.proposal.valor_final == Decimal("3350.00")
        pdf = build_quote_pdf(quote)
    assert pdf[:5] == b"%PDF-"
    assert len(pdf) > 1800


def test_pdf_shows_only_fe_and_charged_adicionais():
    with SessionLocal() as db:
        quote = _make_quote(db)
        crud.add_proposal(
            db, quote,
            _proposal_values(valor_diaria=Decimal("100.00"), valor_guincho=Decimal("0.00")),
            created_by="tester",
        )
        db.refresh(quote)
        itens = dict(quote.proposal.adicionais_itens())
        assert "Diária" in itens
        assert "Guincho / Munck" not in itens  # zerado -> nao aparece
