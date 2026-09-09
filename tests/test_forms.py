from datetime import date, timedelta
from decimal import Decimal

from app.forms import ProposalForm, QuoteForm


def _valid_payload():
    return {
        "client_name": "Joao Alves",
        "client_company": "Construtora Alfa",
        "client_email": "compras@alfa.com.br",
        "origem_cidade": "Curitiba - PR",
        "destino_cidade": "Londrina - PR",
        "tipo_material": "Andaime",
        "qtd_volumes": "10",
        "peso_total_kg": "5.000",
        "valor_nf": "25.000,00",
        "tipo_veiculo": "Carreta Sider",
        "carroceria": "Sider",
        "capacidade_aprox": "28 toneladas",
        "data_coleta": (date.today() + timedelta(days=5)).isoformat(),
        "servico_carga": "sim",
        "servico_descarga": "nao",
        "servico_diaria": "sim",
        "servico_guincho": "nao",
    }


def test_quote_form_ok_without_optionals():
    form = QuoteForm(_valid_payload(), allowed_carrocerias=["Sider", "Bau"])
    assert form.validate(), form.errors
    assert form.values["valor_nf"] == Decimal("25000.00")
    assert form.values["peso_total_kg"] == Decimal("5000.00")
    assert form.values["carroceria"] == "Sider"
    assert form.values["client_company"] == "Construtora Alfa"
    assert form.values["servico_carga"] is True
    assert form.values["servico_descarga"] is False
    assert form.values["servico_diaria"] is True
    assert form.values["servico_guincho"] is False
    assert form.values["origem_cep"] is None


def test_quote_form_requires_company():
    payload = _valid_payload()
    payload["client_company"] = ""
    form = QuoteForm(payload)
    assert not form.validate()
    assert "client_company" in form.errors


def test_quote_form_rejects_carroceria_outside_list():
    payload = _valid_payload()
    payload["carroceria"] = "Inexistente"
    form = QuoteForm(payload, allowed_carrocerias=["Sider", "Bau"])
    assert not form.validate()
    assert "carroceria" in form.errors


def test_quote_form_rejects_tipo_veiculo_outside_list():
    payload = _valid_payload()
    payload["tipo_veiculo"] = "Inexistente"
    form = QuoteForm(payload, allowed_tipos_veiculo=["Carreta Sider", "Truck"])
    assert not form.validate()
    assert "tipo_veiculo" in form.errors


def test_quote_form_skips_existence_check_when_no_allowed_list_given():
    payload = _valid_payload()
    payload["tipo_veiculo"] = "Qualquer coisa"
    form = QuoteForm(payload)
    assert form.validate(), form.errors


def test_quote_form_requires_each_mandatory_field():
    for field in QuoteForm.REQUIRED_LABELS:
        payload = _valid_payload()
        payload.pop(field, None)
        payload[field] = ""
        form = QuoteForm(payload)
        assert not form.validate(), f"{field} deveria ser obrigatorio"
        assert field in form.errors


def test_quote_form_rejects_past_date():
    payload = _valid_payload()
    payload["data_coleta"] = (date.today() - timedelta(days=1)).isoformat()
    form = QuoteForm(payload)
    assert not form.validate()
    assert "data_coleta" in form.errors


def test_proposal_form_totals_on_server():
    form = ProposalForm(
        {"frete": "2.900,00", "pedagio": "50,00", "seguro": "28,00",
         "prazo_entrega": "1 dia util",
         "validade": (date.today() + timedelta(days=7)).isoformat()},
        valor_nf=Decimal("14000.00"),
    )
    assert form.validate(), form.errors
    assert form.values["total"] == Decimal("2978.00")
    assert form.values["custos_adicionais"] == Decimal("0.00")
    assert form.values["valor_final"] == Decimal("2978.00")


def test_proposal_form_with_custos_adicionais():
    form = ProposalForm(
        {"frete": "1.000,00", "pedagio": "0,00", "seguro": "0,00",
         "custos_adicionais": "350,00",
         "custos_adicionais_desc": "Guincho no destino",
         "prazo_entrega": "2 dias",
         "validade": (date.today() + timedelta(days=7)).isoformat()},
        valor_nf=Decimal("10000.00"),
    )
    assert form.validate(), form.errors
    assert form.values["total"] == Decimal("1000.00")
    assert form.values["valor_final"] == Decimal("1350.00")


def test_proposal_form_custos_require_description():
    form = ProposalForm(
        {"frete": "1000,00", "custos_adicionais": "200,00",
         "prazo_entrega": "2 dias",
         "validade": (date.today() + timedelta(days=7)).isoformat()},
        valor_nf=Decimal("10000.00"),
    )
    assert not form.validate()
    assert "custos_adicionais_desc" in form.errors


def test_proposal_form_defaults_seguro_from_nf():
    form = ProposalForm(
        {"frete": "1000,00", "prazo_entrega": "2 dias",
         "validade": (date.today() + timedelta(days=7)).isoformat()},
        valor_nf=Decimal("25000.00"),
    )
    assert form.validate(), form.errors
    assert form.values["seguro"] == Decimal("50.00")
    assert form.values["total"] == Decimal("1050.00")
