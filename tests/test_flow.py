from datetime import date, timedelta
from decimal import Decimal

from conftest import csrf_from

VALID = {
    "tipo_cotacao": "completa",
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
    "servico_carga": "nao",
    "servico_descarga": "sim",
    "servico_diaria": "sim",
    "servico_guincho": "nao",
}

PROPOSTA = {
    "custo_motorista": "8.000,00", "custo_pedagio": "900,00", "custo_impostos": "700,00",
    "custo_seguro": "200,00", "custo_outros_internos": "0,00", "margem_pct": "20",
    "custos_adicionais": "0,00", "custos_adicionais_desc": "",
    "prazo_entrega": "1 dia útil", "observacoes": "",
}
# FC = 9800 ; FE = 9800 * 1.20 = 11760,00


def _submit_quote(client, **overrides):
    page = client.get("/cotacao/nova?tipo=completa")
    token = csrf_from(page.text)
    payload = dict(VALID)
    payload["csrf_token"] = token
    payload["data_coleta"] = (date.today() + timedelta(days=5)).isoformat()
    payload.update(overrides)
    resp = client.post("/cotacao/nova", data=payload, follow_redirects=False)
    assert resp.status_code == 303, resp.text
    location = resp.headers["location"]
    code = location.split("/cotacao/")[1].split("/")[0]
    assert code.startswith("COT-")
    return code


def _admin_login(client):
    page = client.get("/admin/login", follow_redirects=False)
    if page.status_code == 303:
        return  # ja logado nesta sessao (chamada repetida no mesmo teste)
    token = csrf_from(page.text)
    resp = client.post(
        "/admin/login",
        data={"username": "admin@amg.test", "password": "senha-teste",
              "csrf_token": token, "next": "/admin"},
        follow_redirects=False,
    )
    assert resp.status_code == 303


def _respond(client, code, **overrides):
    page = client.get(f"/admin/cotacao/{code}")
    assert page.status_code == 200
    data = dict(PROPOSTA)
    data["csrf_token"] = csrf_from(page.text)
    data["validade"] = (date.today() + timedelta(days=7)).isoformat()
    data.update(overrides)
    resp = client.post(f"/admin/cotacao/{code}", data=data, follow_redirects=False)
    assert resp.status_code == 303, resp.text
    return resp


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_cotacao_escolha_tem_dois_links(client):
    page = client.get("/cotacao").text
    assert "/cotacao/nova?tipo=rapida" in page
    assert "/cotacao/nova?tipo=completa" in page


def test_submit_quote_completa_creates_record(client):
    code = _submit_quote(client)
    detail = client.get(f"/cotacao/{code}")
    assert detail.status_code == 200
    assert code in detail.text
    assert "Proposta em análise" in detail.text


def test_submit_quote_rapida_com_campos_minimos(client):
    page = client.get("/cotacao/nova?tipo=rapida")
    token = csrf_from(page.text)
    payload = {
        "tipo_cotacao": "rapida", "csrf_token": token,
        "client_name": "Fulano", "client_company": "Empresa X",
        "client_email": "fulano@x.com", "origem_cidade": "Curitiba - PR",
        "destino_cidade": "Sao Paulo - SP", "tipo_material": "Andaime",
        "peso_total_kg": "3.000", "data_coleta": (date.today() + timedelta(days=4)).isoformat(),
    }
    resp = client.post("/cotacao/nova", data=payload, follow_redirects=False)
    assert resp.status_code == 303, resp.text


def test_admin_requires_login(client):
    resp = client.get("/admin", follow_redirects=False)
    assert resp.status_code == 303
    assert "/admin/login" in resp.headers["location"]


def test_admin_precifica_fc_fe_e_cliente_nao_ve_fc(client):
    code = _submit_quote(client)
    _admin_login(client)
    _respond(client, code)

    from app.database import SessionLocal
    from app.models import Quote

    with SessionLocal() as db:
        p = db.query(Quote).filter_by(code=code).one().proposal
        assert p.fc == Decimal("9800.00")
        assert p.fe == Decimal("11760.00")
        assert p.valor_final == Decimal("11760.00")

    detail = client.get(f"/cotacao/{code}").text
    assert "R$ 11.760,00" in detail  # FE / valor total
    assert "9.800,00" not in detail  # FC nunca aparece ao cliente
    assert "Valor do frete" in detail


def test_painel_prefill_moeda_em_formato_br(client):
    code = _submit_quote(client)
    _admin_login(client)
    _respond(client, code, custo_motorista="2.000")  # ponto como milhar
    page = client.get(f"/admin/cotacao/{code}").text
    assert 'value="2.000,00"' in page
    assert 'value="2000.00"' not in page


def test_custos_adicionais_somam_no_valor_final(client):
    code = _submit_quote(client)
    _admin_login(client)
    _respond(client, code, valor_diaria="450,00", valor_guincho="350,00")
    detail = client.get(f"/cotacao/{code}").text
    assert "Diária" in detail
    assert "Guincho / Munck" in detail
    assert "R$ 12.560,00" in detail  # 11760 + 450 + 350


def test_admin_aprova_e_cliente_ve_link_para_solicitacao(client):
    code = _submit_quote(client)
    _admin_login(client)
    _respond(client, code)

    page = client.get(f"/admin/cotacao/{code}")
    token = csrf_from(page.text)
    resp = client.post(f"/admin/cotacao/{code}/aprovar", data={"csrf_token": token}, follow_redirects=False)
    assert resp.status_code == 303

    detail2 = client.get(f"/cotacao/{code}").text
    assert "aprovada" in detail2.lower()
    assert f"/cotacao/{code}/solicitacao" in detail2


def test_admin_reprecifica_gera_historico_de_versoes(client):
    code = _submit_quote(client)
    _admin_login(client)
    _respond(client, code)
    _respond(client, code, margem_pct="10")  # reprecifica -> FE menor

    from app.database import SessionLocal
    from app.models import ProposalVersionLog, Quote

    with SessionLocal() as db:
        q = db.query(Quote).filter_by(code=code).one()
        assert q.status == "respondida"
        historico = db.query(ProposalVersionLog).filter_by(quote_id=q.id).all()
        assert len(historico) == 1
        assert historico[0].versao == 1
        assert q.proposal.versao == 2
        assert q.proposal.fe == Decimal("10780.00")  # 9800 * 1.10


def test_cliente_nao_pode_mais_aprovar_ou_negociar_via_app(client):
    """O cliente nao decide mais pelo site (feature retirada) -- as rotas
    antigas simplesmente nao existem mais."""
    code = _submit_quote(client)
    _admin_login(client)
    _respond(client, code)

    # a pagina nao tem mais formulario de decisao (nem csrf_token para ela) --
    # a rota em si nao existe mais, entao o token nao importa aqui.
    resp = client.post(f"/cotacao/{code}/aprovar", data={"csrf_token": "x", "t": ""})
    assert resp.status_code == 404
    resp2 = client.post(f"/cotacao/{code}/negociar", data={"csrf_token": "x", "t": "", "motivo": "x"})
    assert resp2.status_code == 404


def test_salvar_precificacao_apenas_salva_sem_notificar(client):
    code = _submit_quote(client)
    _admin_login(client)
    page = client.get(f"/admin/cotacao/{code}").text
    assert "Salvar precificação" in page
    assert "notificar cliente" not in page.lower()
    assert "enviar ao cliente" not in page.lower()

    resp = _respond(client, code)
    assert resp.headers["location"] == f"/admin/cotacao/{code}?ok=1"


def test_admin_aprova_e_reprova_manual(client):
    code = _submit_quote(client)
    _admin_login(client)
    _respond(client, code)

    page = client.get(f"/admin/cotacao/{code}")
    token = csrf_from(page.text)
    resp = client.post(f"/admin/cotacao/{code}/aprovar", data={"csrf_token": token}, follow_redirects=False)
    assert resp.status_code == 303

    page2 = client.get(f"/admin/cotacao/{code}")
    token2 = csrf_from(page2.text)
    resp2 = client.post(
        f"/admin/cotacao/{code}/reprovar",
        data={"csrf_token": token2, "motivo": "Cliente desistiu"},
        follow_redirects=False,
    )
    assert resp2.status_code == 303
    detail = client.get(f"/cotacao/{code}").text
    assert "reprovada" in detail.lower()
    assert "Cliente desistiu" in detail


def _fluxo_ate_aprovada(client):
    code = _submit_quote(client)
    _admin_login(client)
    _respond(client, code)
    page = client.get(f"/admin/cotacao/{code}")
    token = csrf_from(page.text)
    client.post(f"/admin/cotacao/{code}/aprovar", data={"csrf_token": token})
    return code


def test_fluxo_completo_solicitacao_oc_logistica_agenda(client):
    code = _fluxo_ate_aprovada(client)

    sol_page = client.get(f"/cotacao/{code}/solicitacao")
    assert sol_page.status_code == 200
    token = csrf_from(sol_page.text)
    resp = client.post(
        f"/cotacao/{code}/solicitacao",
        data={
            "csrf_token": token, "t": "",
            "pagador": "Remetente", "pagador_documento": "12.345.678/0001-90",
            "fornecedor_nome": "Fornecedor X", "destinatario_nome": "Obra Y",
            "valor_nf": "25.000,00", "observacoes_operacionais": "",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303

    detail = client.get(f"/cotacao/{code}").text
    assert "frete_solicitado" in detail or "Solicitação de frete enviada" in detail

    admin_sol = client.get(f"/admin/cotacao/{code}/solicitacao")
    assert admin_sol.status_code == 200
    assert "Fornecedor X" in admin_sol.text
    token = csrf_from(admin_sol.text)

    from app.filiais import extrair_uf, sugestao_empresa_cnpj

    empresa_cnpj = sugestao_empresa_cnpj(extrair_uf(VALID["origem_cidade"]))
    assert empresa_cnpj  # origem PR tem filial cadastrada -- deve sugerir sozinho
    assert empresa_cnpj in admin_sol.text

    resp = client.post(
        f"/admin/cotacao/{code}/solicitacao/validar",
        data={"csrf_token": token, "empresa_cnpj": empresa_cnpj},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    from app.database import SessionLocal
    from app.models import Quote

    with SessionLocal() as db:
        q = db.query(Quote).filter_by(code=code).one()
        assert q.status == "oc_emitida"
        assert q.ordem_coleta is not None
        assert q.ordem_coleta.numero.startswith("OC-")
        assert q.ordem_coleta.empresa == empresa_cnpj.split("|")[0]
        assert q.ordem_coleta.cnpj_filial == empresa_cnpj.split("|")[1]

    docx_resp = client.get(f"/admin/cotacao/{code}/ordem-coleta.docx")
    assert docx_resp.status_code == 200
    assert docx_resp.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert docx_resp.content[:2] == b"PK"  # docx = zip

    sol_page2 = client.get(f"/admin/cotacao/{code}/solicitacao")
    token = csrf_from(sol_page2.text)
    resp = client.post(
        f"/admin/cotacao/{code}/enviar-logistica", data={"csrf_token": token}, follow_redirects=False
    )
    assert resp.status_code == 303

    with SessionLocal() as db:
        q = db.query(Quote).filter_by(code=code).one()
        assert q.status == "enviada_logistica"
        assert q.ordem_coleta.agenda is not None
        agenda_id = q.ordem_coleta.agenda.id

    agenda_lista = client.get("/admin/agenda")
    assert agenda_lista.status_code == 200
    assert code in agenda_lista.text or q.ordem_coleta.numero in agenda_lista.text

    agenda_cal = client.get("/admin/agenda?view=calendario")
    assert agenda_cal.status_code == 200

    item_page = client.get(f"/admin/agenda/{agenda_id}")
    assert item_page.status_code == 200
    token = csrf_from(item_page.text)
    resp = client.post(
        f"/admin/agenda/{agenda_id}",
        data={
            "csrf_token": token,
            "data_carregamento": (date.today() + timedelta(days=3)).isoformat(),
            "hora_prevista": "09:00", "responsavel_logistica": "Ryan",
            "status_agenda": "confirmado", "confirmado": "sim", "observacoes": "",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303


def test_solicitacao_devolvida_volta_para_aprovada(client):
    code = _fluxo_ate_aprovada(client)
    sol_page = client.get(f"/cotacao/{code}/solicitacao")
    token = csrf_from(sol_page.text)
    client.post(
        f"/cotacao/{code}/solicitacao",
        data={
            "csrf_token": token, "t": "",
            "pagador": "Remetente", "pagador_documento": "123",
            "fornecedor_nome": "F", "destinatario_nome": "D",
        },
    )
    admin_sol = client.get(f"/admin/cotacao/{code}/solicitacao")
    token = csrf_from(admin_sol.text)
    resp = client.post(
        f"/admin/cotacao/{code}/solicitacao/devolver",
        data={"csrf_token": token, "motivo": "Falta CNPJ correto"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    detail = client.get(f"/cotacao/{code}").text
    assert "Falta CNPJ correto" in detail


def test_gerar_oc_atalho_direto_da_cotacao_aprovada(client):
    """Cotacao aprovada ganha um atalho para gerar a OC direto pelo painel,
    sem esperar o cliente enviar a Solicitacao de Frete (mantem os dois
    caminhos: este atalho e o formulario do cliente)."""
    code = _fluxo_ate_aprovada(client)

    form_page = client.get(f"/admin/cotacao/{code}/gerar-oc")
    assert form_page.status_code == 200
    assert 'name="empresa_cnpj"' in form_page.text
    token = csrf_from(form_page.text)

    from app.filiais import extrair_uf, sugestao_empresa_cnpj

    empresa_cnpj = sugestao_empresa_cnpj(extrair_uf(VALID["origem_cidade"]))
    assert empresa_cnpj  # sugerido automaticamente para a UF de origem

    resp = client.post(
        f"/admin/cotacao/{code}/gerar-oc",
        data={
            "csrf_token": token, "empresa_cnpj": empresa_cnpj,
            "pagador": "Remetente", "pagador_documento": "12.345.678/0001-90",
            "fornecedor_nome": "Fornecedor X", "destinatario_nome": "Obra Y",
            "valor_nf": "25.000,00", "observacoes_operacionais": "",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303

    from app.database import SessionLocal
    from app.models import Quote

    with SessionLocal() as db:
        q = db.query(Quote).filter_by(code=code).one()
        assert q.status == "oc_emitida"
        assert q.solicitacao is not None  # criada junto pelo atalho
        assert q.ordem_coleta is not None
        assert q.ordem_coleta.empresa == empresa_cnpj.split("|")[0]


def test_gerar_oc_sem_empresa_e_rejeitado(client):
    code = _fluxo_ate_aprovada(client)
    form_page = client.get(f"/admin/cotacao/{code}/gerar-oc")
    token = csrf_from(form_page.text)
    resp = client.post(
        f"/admin/cotacao/{code}/gerar-oc",
        data={
            "csrf_token": token, "empresa_cnpj": "",
            "pagador": "Remetente", "pagador_documento": "12.345.678/0001-90",
            "fornecedor_nome": "Fornecedor X", "destinatario_nome": "Obra Y",
        },
    )
    assert resp.status_code == 200
    assert "Selecione a empresa" in resp.text

    from app.database import SessionLocal
    from app.models import Quote

    with SessionLocal() as db:
        q = db.query(Quote).filter_by(code=code).one()
        assert q.status == "aprovada"  # nao avancou
        assert q.ordem_coleta is None


def test_sugestao_empresa_faz_rodizio_entre_filiais_da_mesma_uf(client):
    """Quando mais de uma empresa do grupo atende a UF de origem, a
    sugestao de CNPJ alterna entre elas a cada OC gerada (fila em
    rodizio), em vez de sempre sugerir a mesma."""
    from app.filiais import empresas_elegiveis, extrair_uf

    fila = empresas_elegiveis(extrair_uf(VALID["origem_cidade"]))
    assert len(fila) >= 2  # PR (origem do VALID) atende por varias empresas

    escolhidas = []
    for _ in range(len(fila) + 1):  # uma volta completa + 1, pra conferir que reinicia
        code = _fluxo_ate_aprovada(client)
        preview = client.get(f"/admin/cotacao/{code}/gerar-oc")
        empresa_cnpj = _empresa_sugerida_no_form(preview.text)
        assert empresa_cnpj, "nenhuma opcao sugerida (selected) no dropdown"
        _gerar_oc(client, code, empresa_cnpj)
        escolhidas.append(empresa_cnpj.split("|")[0])

    assert escolhidas[: len(fila)] == fila  # uma volta completa segue a ordem da fila
    assert escolhidas[len(fila)] == fila[0]  # e reinicia do topo


def _fluxo_ate_aprovada_em(client, origem_cidade: str):
    code = _submit_quote(client, origem_cidade=origem_cidade)
    _admin_login(client)
    _respond(client, code)
    page = client.get(f"/admin/cotacao/{code}")
    token = csrf_from(page.text)
    client.post(f"/admin/cotacao/{code}/aprovar", data={"csrf_token": token})
    return code


def _gerar_oc(client, code: str, empresa_cnpj: str):
    form_page = client.get(f"/admin/cotacao/{code}/gerar-oc")
    token = csrf_from(form_page.text)
    resp = client.post(
        f"/admin/cotacao/{code}/gerar-oc",
        data={
            "csrf_token": token, "empresa_cnpj": empresa_cnpj,
            "pagador": "Remetente", "pagador_documento": "12.345.678/0001-90",
            "fornecedor_nome": "Fornecedor X", "destinatario_nome": "Obra Y",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    return form_page


def _empresa_sugerida_no_form(html: str) -> str | None:
    import re

    m = re.search(r'value="([^"]+)"\s+selected', html)
    return m.group(1) if m else None


def test_sugestao_empresa_uf_com_uma_so_filial_nao_alterna(client):
    """BA so tem filial da JVA -- a sugestao deve continuar sempre a mesma,
    sem rodizio (nao ha o que alternar)."""
    jva = "JVA Logistica e Transportes Ltda|22.729.681/0002-47"

    code1 = _fluxo_ate_aprovada_em(client, "Salvador - BA")
    form1 = _gerar_oc(client, code1, jva)
    assert _empresa_sugerida_no_form(form1.text) == jva

    code2 = _fluxo_ate_aprovada_em(client, "Salvador - BA")
    form2 = _gerar_oc(client, code2, jva)
    assert _empresa_sugerida_no_form(form2.text) == jva  # continua a mesma (unica elegivel)


def test_client_form_lists_carrocerias_e_tipos_veiculo(client):
    page = client.get("/cotacao/nova?tipo=completa")
    assert 'name="carroceria"' in page.text
    assert 'name="tipo_veiculo"' in page.text
    assert "Sider" in page.text  # seed padrao de carroceria
    assert "Carreta Sider" in page.text  # seed padrao de tipo de veiculo


def _get_opcao_id(categoria: str, nome: str) -> int:
    from app.database import SessionLocal
    from app.models import Opcao

    with SessionLocal() as db:
        return db.query(Opcao).filter_by(categoria=categoria, nome=nome).one().id


def test_admin_can_manage_carrocerias(client):
    _admin_login(client)
    page = client.get("/admin/opcoes/carroceria")
    assert page.status_code == 200
    token = csrf_from(page.text)
    add = client.post(
        "/admin/opcoes/carroceria", data={"nome": "Bau sider", "csrf_token": token}, follow_redirects=True,
    )
    assert "Bau sider" in add.text

    cid = _get_opcao_id("carroceria", "Bau sider")
    token = csrf_from(client.get("/admin/opcoes/carroceria").text)
    client.post(f"/admin/opcoes/carroceria/{cid}/toggle", data={"csrf_token": token})
    form_page = client.get("/cotacao/nova?tipo=completa").text
    assert "Bau sider" not in form_page


def test_admin_can_manage_tipos_veiculo(client):
    _admin_login(client)
    page = client.get("/admin/opcoes/tipo_veiculo")
    token = csrf_from(page.text)
    add = client.post(
        "/admin/opcoes/tipo_veiculo", data={"nome": "Rodotrem", "csrf_token": token}, follow_redirects=True,
    )
    assert "Rodotrem" in add.text
    assert "Rodotrem" in client.get("/cotacao/nova?tipo=completa").text


def test_acompanhar_por_email_apenas(client):
    code = _submit_quote(client)
    client.cookies.clear()
    page = client.get("/acompanhar")
    assert 'name="code"' not in page.text
    token = csrf_from(page.text)
    resp = client.post(
        "/acompanhar", data={"csrf_token": token, "email": VALID["client_email"]}, follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/minhas-cotacoes"
    lista = client.get("/minhas-cotacoes")
    assert code in lista.text


def test_acompanhar_email_sem_cotacoes(client):
    page = client.get("/acompanhar")
    resp = client.post(
        "/acompanhar", data={"csrf_token": csrf_from(page.text), "email": "ninguem@exemplo.com"},
    )
    assert "Não encontramos" in resp.text


def test_admin_pdf_requires_login(client):
    code = _submit_quote(client)
    client.cookies.clear()
    resp = client.get(f"/admin/cotacao/{code}/pdf", follow_redirects=False)
    assert resp.status_code == 303
    assert "/admin/login" in resp.headers["location"]


def test_admin_can_download_quote_pdf(client):
    code = _submit_quote(client)
    _admin_login(client)
    resp = client.get(f"/admin/cotacao/{code}/pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:5] == b"%PDF-"


def test_client_without_access_is_redirected(client):
    code = _submit_quote(client)
    client.cookies.clear()
    resp = client.get(f"/cotacao/{code}", follow_redirects=False)
    assert resp.status_code == 303
    assert "/acompanhar" in resp.headers["location"]


def test_token_link_grants_access(client):
    code = _submit_quote(client)
    from app.security import sign_quote_token

    client.cookies.clear()
    tok = sign_quote_token(code)
    resp = client.get(f"/cotacao/{code}?t={tok}")
    assert resp.status_code == 200
    assert code in resp.text
