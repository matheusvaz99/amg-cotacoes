from datetime import date, timedelta
from decimal import Decimal

from app.constants import TIPO_COTACAO_COMPLETA, TIPO_COTACAO_RAPIDA
from app.forms import AgendaForm, ProposalForm, QuoteForm, SolicitacaoFreteForm


def _valid_payload(**over):
    payload = {
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
    payload.update(over)
    return payload


def test_quote_form_ok_without_optionals_completa():
    form = QuoteForm(
        _valid_payload(), tipo_cotacao=TIPO_COTACAO_COMPLETA,
        allowed_carrocerias=["Sider", "Bau"],
    )
    assert form.validate(), form.errors
    assert form.values["valor_nf"] == Decimal("25000.00")
    assert form.values["peso_total_kg"] == Decimal("5000.00")
    assert form.values["carroceria"] == "Sider"
    assert form.values["client_company"] == "Construtora Alfa"
    assert form.values["tipo_cotacao"] == TIPO_COTACAO_COMPLETA
    assert form.values["servico_carga"] is True
    assert form.values["servico_diaria"] is True


def test_quote_form_requires_company():
    payload = _valid_payload(client_company="")
    form = QuoteForm(payload)
    assert not form.validate()
    assert "client_company" in form.errors


def test_quote_form_rapida_dispensa_campos_da_completa():
    payload = _valid_payload(
        qtd_volumes="", valor_nf="", tipo_veiculo="", carroceria="", capacidade_aprox="",
    )
    form = QuoteForm(payload, tipo_cotacao=TIPO_COTACAO_RAPIDA)
    assert form.validate(), form.errors
    assert form.values["tipo_cotacao"] == TIPO_COTACAO_RAPIDA
    assert form.values["qtd_volumes"] is None
    assert form.values["valor_nf"] is None
    assert form.values["tipo_veiculo"] is None
    assert form.values["carroceria"] is None
    assert form.values["capacidade_aprox"] is None
    # peso continua obrigatorio em qualquer tipo
    assert form.values["peso_total_kg"] == Decimal("5000.00")


def test_quote_form_completa_exige_campos_extras():
    payload = _valid_payload(
        qtd_volumes="", valor_nf="", tipo_veiculo="", carroceria="", capacidade_aprox="",
    )
    form = QuoteForm(payload, tipo_cotacao=TIPO_COTACAO_COMPLETA)
    assert not form.validate()
    for campo in ("qtd_volumes", "valor_nf", "tipo_veiculo", "carroceria", "capacidade_aprox"):
        assert campo in form.errors, campo


def test_quote_form_rejects_carroceria_outside_list():
    payload = _valid_payload(carroceria="Inexistente")
    form = QuoteForm(payload, allowed_carrocerias=["Sider", "Bau"])
    assert not form.validate()
    assert "carroceria" in form.errors


def test_quote_form_rejects_tipo_veiculo_outside_list():
    payload = _valid_payload(tipo_veiculo="Inexistente")
    form = QuoteForm(payload, allowed_tipos_veiculo=["Carreta Sider", "Truck"])
    assert not form.validate()
    assert "tipo_veiculo" in form.errors


def test_quote_form_requires_each_mandatory_field():
    for field in QuoteForm.REQUIRED_LABELS:
        payload = _valid_payload()
        payload[field] = ""
        form = QuoteForm(payload)
        assert not form.validate(), f"{field} deveria ser obrigatorio"
        assert field in form.errors


def test_quote_form_rejects_past_date():
    payload = _valid_payload(data_coleta=(date.today() - timedelta(days=1)).isoformat())
    form = QuoteForm(payload)
    assert not form.validate()
    assert "data_coleta" in form.errors


def test_quote_form_data_entrega_antes_da_coleta():
    payload = _valid_payload(
        data_coleta=(date.today() + timedelta(days=10)).isoformat(),
        data_entrega=(date.today() + timedelta(days=3)).isoformat(),
    )
    form = QuoteForm(payload)
    assert not form.validate()
    assert "data_entrega" in form.errors


# ----- ProposalForm (FC -> margem -> FE + adicionais) ---------------------

def _valid_proposal_payload(**over):
    payload = {
        "custo_motorista": "8.000,00", "custo_pedagio": "900,00",
        "custo_impostos": "700,00", "custo_seguro": "200,00", "custo_outros_internos": "0,00",
        "margem_pct": "20",
        "prazo_entrega": "1 dia útil",
        "validade": (date.today() + timedelta(days=7)).isoformat(),
    }
    payload.update(over)
    return payload


def test_proposal_form_calcula_fc_fe_conforme_planilha():
    form = ProposalForm(_valid_proposal_payload())
    assert form.validate(), form.errors
    assert form.values["fc"] == Decimal("9800.00")
    assert form.values["fe"] == Decimal("11760.00")
    assert form.values["valor_final"] == Decimal("11760.00")


def test_proposal_form_soma_adicionais_no_valor_final():
    form = ProposalForm(_valid_proposal_payload(
        valor_diaria="450,00", valor_guincho="350,00", custos_adicionais="0,00",
    ))
    assert form.validate(), form.errors
    assert form.values["fe"] == Decimal("11760.00")
    assert form.values["valor_final"] == Decimal("12560.00")  # 11760 + 450 + 350


def test_proposal_form_outros_exige_descricao():
    form = ProposalForm(_valid_proposal_payload(custos_adicionais="200,00"))
    assert not form.validate()
    assert "custos_adicionais_desc" in form.errors


def test_proposal_form_sem_custos_e_margem_zero():
    form = ProposalForm({
        "prazo_entrega": "2 dias",
        "validade": (date.today() + timedelta(days=7)).isoformat(),
    })
    assert form.validate(), form.errors
    assert form.values["fc"] == Decimal("0.00")
    assert form.values["fe"] == Decimal("0.00")
    assert form.values["valor_final"] == Decimal("0.00")


def test_proposal_form_requires_prazo_e_validade():
    form = ProposalForm(_valid_proposal_payload(prazo_entrega="", validade=""))
    assert not form.validate()
    assert "prazo_entrega" in form.errors
    assert "validade" in form.errors


# ----- SolicitacaoFreteForm -------------------------------------------

def test_solicitacao_form_ok():
    form = SolicitacaoFreteForm({
        "pagador": "Remetente", "pagador_documento": "12.345.678/0001-90",
        "fornecedor_nome": "Fornecedor X", "destinatario_nome": "Obra Y",
        "valor_nf": "10.000,00",
    })
    assert form.validate(), form.errors
    assert form.values["valor_nf"] == Decimal("10000.00")


def test_solicitacao_form_requires_fields():
    form = SolicitacaoFreteForm({})
    assert not form.validate()
    for campo in ("pagador", "pagador_documento", "fornecedor_nome", "destinatario_nome"):
        assert campo in form.errors


def test_solicitacao_form_rejects_invalid_pagador():
    form = SolicitacaoFreteForm({
        "pagador": "Ninguem", "pagador_documento": "123", "fornecedor_nome": "X", "destinatario_nome": "Y",
    })
    assert not form.validate()
    assert "pagador" in form.errors


# ----- AgendaForm -------------------------------------------------------

def test_agenda_form_ok():
    form = AgendaForm({
        "data_carregamento": (date.today() + timedelta(days=2)).isoformat(),
        "hora_prevista": "08:00", "status_agenda": "confirmado", "confirmado": "sim",
    })
    assert form.validate(), form.errors
    assert form.values["confirmado"] is True
    assert form.values["status_agenda"] == "confirmado"


def test_agenda_form_requires_data():
    form = AgendaForm({"status_agenda": "programado"})
    assert not form.validate()
    assert "data_carregamento" in form.errors


def test_agenda_form_rejects_invalid_status():
    form = AgendaForm({
        "data_carregamento": (date.today() + timedelta(days=2)).isoformat(),
        "status_agenda": "inexistente",
    })
    assert not form.validate()
    assert "status_agenda" in form.errors
