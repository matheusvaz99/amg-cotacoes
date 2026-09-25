from datetime import date, timedelta
from decimal import Decimal

from conftest import csrf_from

VALID = {
    "tipo_cotacao": "completa",
    "client_name": "Joao Alves",
    "client_company": "Construtora Alfa",
    "client_cnpj": "12.345.678/0001-90",
    "client_email": "compras@alfa.com.br",
    # origem e destino ficam em UFs diferentes de proposito: a empresa/CNPJ
    # da OC deve seguir o destino (Londrina - PR, com varias filiais
    # elegiveis), nunca a origem (Salvador - BA, so a JVA atende) -- assim os
    # testes pegam se essa logica for trocada de volta por engano.
    "origem_cidade": "Salvador - BA",
    "destino_cidade": "Londrina - PR",
    "tipo_material": "Andaime",
    "qtd_volumes": "10",
    "peso_total": "5.000 kg",
    "valor_nf": "25.000,00",
    "tipo_veiculo": "Carreta Sider",
    "carroceria": "Sider",
    "capacidade_aprox": "28 toneladas",
    "servico_diaria": "sim",
    "servico_guincho": "nao",
}

PROPOSTA = {
    "custo_motorista": "8.000,00", "custo_pedagio": "900,00", "custo_impostos": "700,00",
    "custo_outros_internos": "0,00", "margem_pct": "20",
    "custos_adicionais": "0,00", "custos_adicionais_desc": "",
    "prazo_entrega": "1 dia útil", "observacoes": "",
}
# FC = 9600 ; FE = 9600 * 1.20 = 11520,00


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


def test_cotacao_redireciona_direto_pro_formulario(client):
    # "Cotação Rápida" foi descontinuada -- so existe cotação completa, entao
    # /cotacao nem mostra mais tela de escolha, vai direto pro formulario.
    resp = client.get("/cotacao", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/cotacao/nova?tipo=completa"


def test_submit_quote_completa_creates_record(client):
    code = _submit_quote(client)
    detail = client.get(f"/cotacao/{code}")
    assert detail.status_code == 200
    assert code in detail.text
    assert "Proposta em análise" in detail.text


def test_submit_quote_ignora_tipo_rapida_e_exige_campos_da_completa(client):
    # "Cotação Rápida" foi descontinuada -- mesmo que "rapida" seja enviado
    # (ex.: link antigo/salvo), o servidor trata como completa e exige os
    # campos correspondentes (valor_nf, tipo_veiculo, carroceria, etc.).
    page = client.get("/cotacao/nova?tipo=rapida")
    token = csrf_from(page.text)
    payload = {
        "tipo_cotacao": "rapida", "csrf_token": token,
        "client_name": "Fulano", "client_company": "Empresa X",
        "client_cnpj": "98.765.432/0001-10",
        "client_email": "fulano@x.com", "origem_cidade": "Curitiba - PR",
        "destino_cidade": "Sao Paulo - SP", "tipo_material": "Andaime",
        "peso_total": "3 toneladas", "data_coleta": (date.today() + timedelta(days=4)).isoformat(),
    }
    resp = client.post("/cotacao/nova", data=payload, follow_redirects=False)
    assert resp.status_code == 200  # rerenderiza com erros, nao redireciona
    assert "obrigatório" in resp.text


def test_submit_quote_sem_email_e_aceito(client, capsys):
    """E-mail do comprador e opcional -- a cotacao e criada normalmente, so
    nao ha confirmacao por e-mail (nao ha pra quem mandar)."""
    code = _submit_quote(client, client_email="")
    capsys.readouterr()  # descarta o e-mail interno ao comercial, so nos interessa o do cliente

    detail = client.get(f"/cotacao/{code}")
    assert detail.status_code == 200

    from app.database import SessionLocal
    from app.models import Quote

    with SessionLocal() as db:
        q = db.query(Quote).filter_by(code=code).one()
        assert q.client_email is None

    _admin_login(client)
    _respond(client, code)
    page = client.get(f"/admin/cotacao/{code}")
    token = csrf_from(page.text)
    capsys.readouterr()  # limpa o buffer antes do aprovar, pra isolar so esse passo
    resp = client.post(
        f"/admin/cotacao/{code}/aprovar", data={"csrf_token": token}, follow_redirects=False
    )
    assert resp.status_code == 303
    out = capsys.readouterr()
    assert "----- E-MAIL" not in out.out  # sem e-mail, nao ha aviso nenhum pra disparar


def test_submit_quote_sem_qtd_volumes_completa_e_aceito(client):
    code = _submit_quote(client, qtd_volumes="")

    from app.database import SessionLocal
    from app.models import Quote

    with SessionLocal() as db:
        q = db.query(Quote).filter_by(code=code).one()
        assert q.qtd_volumes is None


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
        assert p.fc == Decimal("9600.00")
        assert p.fe == Decimal("11520.00")
        assert p.valor_final == Decimal("11520.00")

    detail = client.get(f"/cotacao/{code}").text
    assert "R$ 11.520,00" in detail  # FE / valor total
    assert "9.600,00" not in detail  # FC nunca aparece ao cliente
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
    assert "R$ 12.320,00" in detail  # 11520 + 450 + 350


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
        assert q.proposal.fe == Decimal("10560.00")  # 9600 * 1.10


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


def test_fluxo_completo_solicitacao_oc_logistica_agenda(client, capsys):
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

    empresa_cnpj = sugestao_empresa_cnpj(extrair_uf(VALID["destino_cidade"]))
    assert empresa_cnpj  # destino PR tem filial cadastrada -- vem pre-selecionada
    assert f'value="{empresa_cnpj}"' in admin_sol.text
    assert "<select" in admin_sol.text  # dropdown sempre visivel, mesmo com sugestao

    resp = client.post(
        f"/admin/cotacao/{code}/solicitacao/validar",
        data={"csrf_token": token},  # empresa/CNPJ e resolvido pelo servidor, nao pelo form
        follow_redirects=False,
    )
    assert resp.status_code == 303

    from app.database import SessionLocal
    from app.models import Quote

    with SessionLocal() as db:
        q = db.query(Quote).filter_by(code=code).one()
        assert q.status == "oc_emitida"
        assert q.ordem_coleta is not None
        assert q.ordem_coleta.numero.startswith("AMG-J-")
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

    from app.config import settings

    email_log = capsys.readouterr().out
    assert f"Para: {settings.email_logistica}" in email_log
    assert f"Cc: {settings.email_logistica_cc}" in email_log

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


def test_mensagem_logistica_usa_fc_sem_margem(client):
    code = _submit_quote(client)
    _admin_login(client)
    _respond(client, code)  # FC = 9600, FE = 11520 (ver PROPOSTA no topo do arquivo)

    resp = client.get(f"/admin/cotacao/{code}/mensagem-logistica")
    assert resp.status_code == 200
    assert "R$ 9.600,00" in resp.text  # FC
    assert "R$ 11.520,00" not in resp.text  # nunca o FE/valor cobrado
    assert "Sider" in resp.text
    assert "Andaime" in resp.text

    # botao aparece na tela da cotacao assim que ha proposta
    detalhe = client.get(f"/admin/cotacao/{code}")
    assert f"/admin/cotacao/{code}/mensagem-logistica" in detalhe.text


def test_mensagem_logistica_sem_proposta_redireciona(client):
    code = _submit_quote(client)
    _admin_login(client)
    resp = client.get(f"/admin/cotacao/{code}/mensagem-logistica", follow_redirects=False)
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

    empresa_cnpj = sugestao_empresa_cnpj(extrair_uf(VALID["destino_cidade"]))
    assert empresa_cnpj  # resolvido automaticamente para a UF de destino

    resp = client.post(
        f"/admin/cotacao/{code}/gerar-oc",
        data={
            "csrf_token": token, "empresa_cnpj": empresa_cnpj,
            "origem_cidade": VALID["origem_cidade"], "destino_cidade": VALID["destino_cidade"],
            "pagador": "Remetente", "pagador_documento": "12.345.678/0001-90",
            "destinatario_nome": "Obra Y",
            "valor_nf": "25.000,00",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303, resp.text

    from app.database import SessionLocal
    from app.models import Quote

    with SessionLocal() as db:
        q = db.query(Quote).filter_by(code=code).one()
        assert q.status == "oc_emitida"
        assert q.solicitacao is not None  # criada junto pelo atalho
        assert q.solicitacao.fornecedor_nome == "Construtora Alfa"  # sempre client_company, sem perguntar
        assert q.ordem_coleta is not None
        assert q.ordem_coleta.empresa == empresa_cnpj.split("|")[0]


def test_gerar_oc_sem_filial_na_uf_exige_escolha_manual_e_rejeita_vazio(client):
    """Manaus - AM nao tem filial de nenhuma empresa cadastrada -- e o unico
    caso em que o dropdown aparece e a escolha manual e obrigatoria."""
    code = _fluxo_ate_aprovada_em(client, "Manaus - AM")
    form_page = client.get(f"/admin/cotacao/{code}/gerar-oc")
    assert "<select" in form_page.text  # sem filial elegivel, pede escolha manual
    token = csrf_from(form_page.text)
    resp = client.post(
        f"/admin/cotacao/{code}/gerar-oc",
        data={
            "csrf_token": token, "empresa_cnpj": "",
            "origem_cidade": VALID["origem_cidade"], "destino_cidade": "Manaus - AM",
            "pagador": "Remetente", "pagador_documento": "12.345.678/0001-90",
            "destinatario_nome": "Obra Y",
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


def test_gerar_oc_sem_filial_na_uf_aceita_escolha_manual(client):
    """No mesmo cenario sem filial (Manaus - AM), escolher manualmente no
    dropdown deve funcionar normalmente."""
    code = _fluxo_ate_aprovada_em(client, "Manaus - AM")
    manual = "AMG Expresso Ltda|50.786.286/0003-12"  # MS, so pra ilustrar escolha livre
    _gerar_oc(client, code, manual, destino_cidade="Manaus - AM")

    from app.database import SessionLocal
    from app.models import Quote

    with SessionLocal() as db:
        q = db.query(Quote).filter_by(code=code).one()
        assert q.status == "oc_emitida"
        assert q.ordem_coleta.empresa == "AMG Expresso Ltda"
        assert q.ordem_coleta.cnpj_filial == "50.786.286/0003-12"


def test_resolver_empresa_cnpj_oc(client):
    """Unidade direta de crud.resolver_empresa_cnpj_oc: a escolha manual do
    dropdown sempre manda quando valida (mesmo havendo sugestao por rodizio
    disponivel); cai pra sugestao so quando a escolha manual e None/invalida."""
    from app import crud
    from app.database import SessionLocal

    with SessionLocal() as db:
        # PR tem filiais elegiveis -- sem escolha (valida), usa a sugestao
        sugestao_pr = crud.resolver_empresa_cnpj_oc(db, "PR", None)
        assert sugestao_pr is not None
        assert crud.resolver_empresa_cnpj_oc(db, "PR", "lixo invalido, sem pipe") == sugestao_pr

        # escolha manual valida sempre vence, mesmo com sugestao disponivel
        manual = "JVA Logistica e Transportes Ltda|22.729.681/0001-66"
        assert crud.resolver_empresa_cnpj_oc(db, "PR", manual) == (
            "JVA Logistica e Transportes Ltda", "22.729.681/0001-66",
        )

        # AM nao tem nenhuma filial/sugestao -- so a escolha manual decide
        assert crud.resolver_empresa_cnpj_oc(db, "AM", None) is None
        assert crud.resolver_empresa_cnpj_oc(db, "AM", "valor invalido") is None
        assert crud.resolver_empresa_cnpj_oc(db, "AM", manual) == (
            "JVA Logistica e Transportes Ltda", "22.729.681/0001-66",
        )


def test_sugestao_empresa_faz_rodizio_entre_filiais_da_mesma_uf(client):
    """Quando mais de uma empresa do grupo atende a UF de destino, a
    sugestao de CNPJ alterna entre elas a cada OC gerada (fila em
    rodizio), em vez de sempre sugerir a mesma."""
    from app.filiais import empresas_elegiveis, extrair_uf

    fila = empresas_elegiveis(extrair_uf(VALID["destino_cidade"]))
    assert len(fila) >= 2  # PR (destino do VALID) atende por varias empresas

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


def _fluxo_ate_aprovada_em(client, destino_cidade: str):
    code = _submit_quote(client, destino_cidade=destino_cidade)
    _admin_login(client)
    _respond(client, code)
    page = client.get(f"/admin/cotacao/{code}")
    token = csrf_from(page.text)
    client.post(f"/admin/cotacao/{code}/aprovar", data={"csrf_token": token})
    return code


def _gerar_oc(
    client, code: str, empresa_cnpj: str,
    origem_cidade: str = VALID["origem_cidade"], destino_cidade: str = VALID["destino_cidade"],
):
    form_page = client.get(f"/admin/cotacao/{code}/gerar-oc")
    token = csrf_from(form_page.text)
    resp = client.post(
        f"/admin/cotacao/{code}/gerar-oc",
        data={
            "csrf_token": token, "empresa_cnpj": empresa_cnpj,
            "origem_cidade": origem_cidade, "destino_cidade": destino_cidade,
            "pagador": "Remetente", "pagador_documento": "12.345.678/0001-90",
            "destinatario_nome": "Obra Y",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303, resp.text
    return form_page


def _empresa_sugerida_no_form(html: str) -> str | None:
    """Le a empresa/CNPJ que o form vai enviar: modo automatico (input
    hidden, quando ha filial elegivel) ou modo manual (option selecionada
    no dropdown, quando nao ha nenhuma)."""
    import re

    m = re.search(r'name="empresa_cnpj" value="([^"]+)"', html)
    if m:
        return m.group(1)
    m = re.search(r'value="([^"]+)"\s+selected', html)
    return m.group(1) if m else None


def test_sugestao_empresa_uf_com_uma_so_filial_nao_alterna(client):
    """BA so tem filial da JVA -- a sugestao deve continuar sempre a mesma,
    sem rodizio (nao ha o que alternar)."""
    jva = "JVA Logistica e Transportes Ltda|22.729.681/0002-47"

    code1 = _fluxo_ate_aprovada_em(client, "Salvador - BA")
    form1 = _gerar_oc(client, code1, jva, destino_cidade="Salvador - BA")
    assert _empresa_sugerida_no_form(form1.text) == jva

    code2 = _fluxo_ate_aprovada_em(client, "Salvador - BA")
    form2 = _gerar_oc(client, code2, jva, destino_cidade="Salvador - BA")
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
