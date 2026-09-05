from datetime import date, timedelta

from conftest import csrf_from

VALID = {
    "client_name": "Construtora Alfa",
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
}


def _submit_quote(client):
    page = client.get("/cotacao")
    token = csrf_from(page.text)
    payload = dict(VALID)
    payload["csrf_token"] = token
    payload["data_coleta"] = (date.today() + timedelta(days=5)).isoformat()
    resp = client.post("/cotacao", data=payload, follow_redirects=False)
    assert resp.status_code == 303, resp.text
    location = resp.headers["location"]
    code = location.split("/cotacao/")[1].split("/")[0]
    assert code.startswith("COT-")
    return code


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_submit_quote_creates_record(client):
    code = _submit_quote(client)
    # cliente ganhou acesso na sessao -> ve a cotacao
    detail = client.get(f"/cotacao/{code}")
    assert detail.status_code == 200
    assert code in detail.text
    assert "Proposta em analise" in detail.text


def test_admin_requires_login(client):
    resp = client.get("/admin", follow_redirects=False)
    assert resp.status_code == 303
    assert "/admin/login" in resp.headers["location"]


def _admin_login(client):
    page = client.get("/admin/login")
    token = csrf_from(page.text)
    resp = client.post(
        "/admin/login",
        data={"username": "admin@amg.test", "password": "senha-teste",
              "csrf_token": token, "next": "/admin"},
        follow_redirects=False,
    )
    assert resp.status_code == 303


def test_admin_can_respond_and_client_accepts(client):
    code = _submit_quote(client)
    _admin_login(client)

    page = client.get(f"/admin/cotacao/{code}")
    assert page.status_code == 200
    token = csrf_from(page.text)

    resp = client.post(
        f"/admin/cotacao/{code}",
        data={
            "frete": "2.900,00", "pedagio": "50,00", "seguro": "50,00",
            "prazo_entrega": "1 dia util",
            "validade": (date.today() + timedelta(days=7)).isoformat(),
            "observacoes": "", "csrf_token": token,
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303

    detail = client.get(f"/cotacao/{code}")
    assert "Itens da cotacao" in detail.text
    assert "R$ 3.000,00" in detail.text  # total = 2900 + 50 + 50
    dtoken = csrf_from(detail.text)

    accept = client.post(
        f"/cotacao/{code}/aceitar",
        data={"csrf_token": dtoken, "t": ""},
        follow_redirects=False,
    )
    assert accept.status_code == 200
    assert "aceita" in accept.text.lower()


def test_client_form_lists_carrocerias_e_tipos_veiculo(client):
    page = client.get("/cotacao")
    assert 'name="carroceria"' in page.text
    assert 'name="tipo_veiculo"' in page.text
    assert "Sider" in page.text  # seed padrao de carroceria
    assert "Carreta Sider" in page.text  # seed padrao de tipo de veiculo


def _get_opcao_id(categoria: str, nome: str) -> int:
    from app.database import SessionLocal
    from app.models import Opcao

    with SessionLocal() as db:
        return db.query(Opcao).filter_by(categoria=categoria, nome=nome).one().id


def test_admin_unknown_categoria_redirects(client):
    _admin_login(client)
    resp = client.get("/admin/opcoes/inexistente", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/admin"


def test_admin_can_manage_carrocerias(client):
    _admin_login(client)

    page = client.get("/admin/opcoes/carroceria")
    assert page.status_code == 200
    token = csrf_from(page.text)

    add = client.post(
        "/admin/opcoes/carroceria",
        data={"nome": "Bau sider", "csrf_token": token},
        follow_redirects=True,
    )
    assert "Bau sider" in add.text

    # inativar remove do formulario do cliente
    cid = _get_opcao_id("carroceria", "Bau sider")
    token = csrf_from(client.get("/admin/opcoes/carroceria").text)
    client.post(f"/admin/opcoes/carroceria/{cid}/toggle", data={"csrf_token": token})

    form_page = client.get("/cotacao").text
    assert "Bau sider" not in form_page

    # cotacao com carroceria inativa e recusada
    token = csrf_from(client.get("/cotacao").text)
    payload = dict(VALID)
    payload.update(
        csrf_token=token, carroceria="Bau sider",
        data_coleta=(date.today() + timedelta(days=5)).isoformat(),
    )
    resp = client.post("/cotacao", data=payload, follow_redirects=False)
    assert resp.status_code == 200
    assert "Opcao invalida" in resp.text


def test_admin_can_manage_tipos_veiculo(client):
    _admin_login(client)

    page = client.get("/admin/opcoes/tipo_veiculo")
    assert page.status_code == 200
    token = csrf_from(page.text)

    add = client.post(
        "/admin/opcoes/tipo_veiculo",
        data={"nome": "Rodotrem", "csrf_token": token},
        follow_redirects=True,
    )
    assert "Rodotrem" in add.text
    assert "Rodotrem" in client.get("/cotacao").text


def test_admin_edit_renames_and_rejects_duplicate(client):
    _admin_login(client)
    page = client.get("/admin/opcoes/carroceria")
    token = csrf_from(page.text)

    sider_id = _get_opcao_id("carroceria", "Sider")
    edit = client.post(
        f"/admin/opcoes/carroceria/{sider_id}/editar",
        data={"nome": "Sider reforcado", "csrf_token": token},
        follow_redirects=True,
    )
    assert "Sider reforcado" in edit.text
    assert "Opcao atualizada" in edit.text

    # duplicar o nome de outra opcao da mesma categoria falha
    token = csrf_from(client.get("/admin/opcoes/carroceria").text)
    bau_id = _get_opcao_id("carroceria", "Bau")
    dup = client.post(
        f"/admin/opcoes/carroceria/{bau_id}/editar",
        data={"nome": "Sider reforcado", "csrf_token": token},
        follow_redirects=True,
    )
    assert "Ja existe uma opcao com esse nome" in dup.text


def test_admin_can_delete_opcao(client):
    _admin_login(client)
    page = client.get("/admin/opcoes/tipo_veiculo")
    token = csrf_from(page.text)
    client.post(
        "/admin/opcoes/tipo_veiculo",
        data={"nome": "Temporario", "csrf_token": token},
    )
    tid = _get_opcao_id("tipo_veiculo", "Temporario")
    token = csrf_from(client.get("/admin/opcoes/tipo_veiculo").text)
    resp = client.post(
        f"/admin/opcoes/tipo_veiculo/{tid}/delete",
        data={"csrf_token": token},
        follow_redirects=True,
    )
    assert "Temporario" not in resp.text


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
    assert f'filename="cotacao-{code}.pdf"' in resp.headers["content-disposition"]
    assert resp.content[:5] == b"%PDF-"


def test_admin_can_send_quote_pdf_to_client(client):
    code = _submit_quote(client)
    _admin_login(client)
    page = client.get(f"/admin/cotacao/{code}")
    token = csrf_from(page.text)
    resp = client.post(
        f"/admin/cotacao/{code}/enviar-pdf",
        data={"csrf_token": token},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"].endswith("?ok=pdf")


def test_client_without_access_is_redirected(client):
    code = _submit_quote(client)
    client.cookies.clear()  # nova sessao, sem acesso
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
