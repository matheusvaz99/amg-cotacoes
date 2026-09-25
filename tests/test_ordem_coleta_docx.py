"""Testes de app/ordem_coleta_docx.py: preenchimento do modelo .docx real da
Ordem de Coleta a partir dos dados da cotacao."""

from datetime import date, timedelta

from docx import Document

from conftest import csrf_from

VALID = {
    "tipo_cotacao": "completa",
    "client_name": "Joao Alves",
    "client_company": "Construtora Alfa",
    "client_cnpj": "11.222.333/0001-44",
    "client_email": "compras@alfa.com.br",
    "client_phone": "(41) 99999-0000",
    "origem_cidade": "Curitiba - PR",
    "origem_cep": "80000-000",
    "origem_endereco": "Rua das Flores",
    "origem_numero": "100",
    "origem_bairro": "Centro",
    "destino_cidade": "Londrina - PR",
    "destino_cep": "86000-000",
    "destino_endereco": "Av. Brasil",
    "destino_numero": "200",
    "destino_bairro": "Jardim",
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
    "custo_seguro": "200,00", "custo_outros_internos": "0,00", "margem_pct": "20",
    "custos_adicionais": "0,00", "custos_adicionais_desc": "",
    "prazo_entrega": "1 dia útil", "observacoes": "",
}
# FC = 9800 ; FE = 9800 * 1.20 = 11760,00


def _fluxo_ate_oc(client):
    page = client.get("/cotacao/nova?tipo=completa")
    token = csrf_from(page.text)
    payload = dict(VALID)
    payload["csrf_token"] = token
    payload["data_coleta"] = (date.today() + timedelta(days=5)).isoformat()
    resp = client.post("/cotacao/nova", data=payload, follow_redirects=False)
    code = resp.headers["location"].split("/cotacao/")[1].split("/")[0]

    admin_page = client.get("/admin/login")
    token = csrf_from(admin_page.text)
    client.post(
        "/admin/login",
        data={"username": "admin@amg.test", "password": "senha-teste",
              "csrf_token": token, "next": "/admin"},
        follow_redirects=False,
    )

    resp_page = client.get(f"/admin/cotacao/{code}")
    data = dict(PROPOSTA)
    data["csrf_token"] = csrf_from(resp_page.text)
    data["validade"] = (date.today() + timedelta(days=7)).isoformat()
    client.post(f"/admin/cotacao/{code}", data=data, follow_redirects=False)

    page = client.get(f"/admin/cotacao/{code}")
    token = csrf_from(page.text)
    client.post(f"/admin/cotacao/{code}/aprovar", data={"csrf_token": token}, follow_redirects=False)

    form_page = client.get(f"/admin/cotacao/{code}/gerar-oc")
    token = csrf_from(form_page.text)
    from app.filiais import extrair_uf, sugestao_empresa_cnpj

    empresa_cnpj = sugestao_empresa_cnpj(extrair_uf(VALID["destino_cidade"]))
    resp = client.post(
        f"/admin/cotacao/{code}/gerar-oc",
        data={
            "csrf_token": token, "empresa_cnpj": empresa_cnpj,
            # o form real vem pre-preenchido com o endereco da propria
            # cotacao (confirmavel/editavel); o navegador reenvia tudo --
            # simula isso aqui em vez de so mandar as cidades.
            "origem_cidade": VALID["origem_cidade"], "origem_cep": VALID["origem_cep"],
            "origem_endereco": VALID["origem_endereco"], "origem_numero": VALID["origem_numero"],
            "origem_bairro": VALID["origem_bairro"],
            "destino_cidade": VALID["destino_cidade"], "destino_cep": VALID["destino_cep"],
            "destino_endereco": VALID["destino_endereco"], "destino_numero": VALID["destino_numero"],
            "destino_bairro": VALID["destino_bairro"],
            "pagador": "Remetente", "pagador_documento": "12.345.678/0001-90",
            "destinatario_nome": "Obra Y",
            "valor_nf": "25.000,00",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303, resp.text
    return code


def _tabelas_texto(doc: Document) -> str:
    partes = []
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                partes.append(cell.text)
    return "\n".join(partes)


def test_build_ordem_coleta_docx_preenche_campos_da_cotacao(client):
    from app.crud import get_quote_by_code
    from app.database import SessionLocal
    from app.ordem_coleta_docx import build_ordem_coleta_docx

    code = _fluxo_ate_oc(client)
    with SessionLocal() as db:
        quote = get_quote_by_code(db, code)
        conteudo = build_ordem_coleta_docx(quote)

    from io import BytesIO

    doc = Document(BytesIO(conteudo))
    texto = _tabelas_texto(doc)

    assert code in texto
    assert quote.ordem_coleta.numero in texto
    assert quote.client_cnpj in texto  # CNPJ COLETA = CNPJ do cliente, nao da AMG
    assert quote.ordem_coleta.cnpj_filial not in texto  # CNPJ da AMG so escolhe o modelo/letterhead
    assert "Construtora Alfa" in texto  # nome da empresa na coleta
    assert "Obra Y" in texto  # destinatario, vindo da solicitacao
    assert "Rua das Flores, 100" in texto
    assert "R$ 11.760,00" in texto  # FE total, sem FC/margem
    assert "9.800,00" not in texto  # FC nunca aparece no documento
    assert "5.000 kg" in texto  # peso: texto livre, repassado verbatim
    assert quote.data_coleta.strftime("%d/%m/%Y") in texto
    assert "Josemar Teixeira Costa" in texto  # comercial responsavel, sempre fixo


def test_build_ordem_coleta_docx_usa_modelo_da_empresa_escolhida(client):
    from app.crud import get_quote_by_code
    from app.database import SessionLocal
    from app.filiais import EMPRESA_TEMPLATE
    from app.ordem_coleta_docx import build_ordem_coleta_docx

    code = _fluxo_ate_oc(client)
    with SessionLocal() as db:
        quote = get_quote_by_code(db, code)
        empresa = quote.ordem_coleta.empresa
        conteudo = build_ordem_coleta_docx(quote)

    assert empresa in EMPRESA_TEMPLATE
    # o documento gerado deve ser um .docx (zip) valido, nao vazio
    assert conteudo[:2] == b"PK"
    assert len(conteudo) > 1000
