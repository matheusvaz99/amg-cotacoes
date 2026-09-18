"""Testes de app/filiais.py: mapeamento empresa/UF -> CNPJ e modelo .docx,
usado para emitir a Ordem de Coleta com a filial correta."""

from app.filiais import (
    EMPRESA_TEMPLATE,
    FILIAIS_CNPJ,
    empresas_elegiveis,
    extrair_uf,
    label_empresa_cnpj,
    opcoes_empresa_cnpj,
    parse_empresa_cnpj,
    proxima_empresa_da_fila,
    sugestao_empresa_cnpj,
)


def test_extrair_uf_formato_padrao():
    assert extrair_uf("Curitiba - PR") == "PR"
    assert extrair_uf("Sao Paulo - SP") == "SP"


def test_extrair_uf_invalido_devolve_none():
    assert extrair_uf(None) is None
    assert extrair_uf("") is None
    assert extrair_uf("Curitiba") is None
    assert extrair_uf("Curitiba - Parana") is None


def test_sugestao_empresa_cnpj_uf_com_filial():
    # PR tem filial nas 4 empresas -- prioridade e a ordem do dict
    assert sugestao_empresa_cnpj("PR") == "AMG Logistica Ltda|53.805.774/0001-56"


def test_sugestao_empresa_cnpj_uf_sem_nenhuma_filial():
    assert sugestao_empresa_cnpj("AM") is None
    assert sugestao_empresa_cnpj(None) is None


def test_sugestao_empresa_cnpj_uf_so_uma_empresa_atende():
    # BA so tem filial da JVA
    assert sugestao_empresa_cnpj("BA") == "JVA Logistica e Transportes Ltda|22.729.681/0002-47"


def test_parse_empresa_cnpj_ida_e_volta():
    for empresa, ufs in FILIAIS_CNPJ.items():
        for cnpj in ufs.values():
            valor = f"{empresa}|{cnpj}"
            assert parse_empresa_cnpj(valor) == (empresa, cnpj)


def test_parse_empresa_cnpj_invalido():
    assert parse_empresa_cnpj(None) is None
    assert parse_empresa_cnpj("") is None
    assert parse_empresa_cnpj("sem-pipe") is None
    assert parse_empresa_cnpj("Empresa Inexistente|00.000.000/0001-00") is None


def test_opcoes_empresa_cnpj_cobre_todas_as_filiais():
    opcoes = opcoes_empresa_cnpj()
    total_filiais = sum(len(ufs) for ufs in FILIAIS_CNPJ.values())
    assert len(opcoes) == total_filiais
    valores = {value for value, _ in opcoes}
    for empresa, ufs in FILIAIS_CNPJ.items():
        for cnpj in ufs.values():
            assert f"{empresa}|{cnpj}" in valores


def test_toda_empresa_tem_modelo_docx_mapeado():
    for empresa in FILIAIS_CNPJ:
        assert empresa in EMPRESA_TEMPLATE
        assert EMPRESA_TEMPLATE[empresa].endswith(".docx")


def test_empresas_elegiveis_uf_com_varias():
    # PR tem filial nas 4, na ordem de prioridade do dict
    assert empresas_elegiveis("PR") == [
        "AMG Logistica Ltda",
        "AMG Logistica e Transportes Eireli",
        "JVA Logistica e Transportes Ltda",
        "AMG Expresso Ltda",
    ]


def test_empresas_elegiveis_uf_com_uma_so():
    assert empresas_elegiveis("BA") == ["JVA Logistica e Transportes Ltda"]


def test_empresas_elegiveis_uf_sem_nenhuma():
    assert empresas_elegiveis("AM") == []
    assert empresas_elegiveis(None) == []


def test_proxima_empresa_da_fila_roda_e_volta_ao_inicio():
    fila = empresas_elegiveis("PR")
    assert proxima_empresa_da_fila(fila, None) == fila[0]
    assert proxima_empresa_da_fila(fila, fila[0]) == fila[1]
    assert proxima_empresa_da_fila(fila, fila[1]) == fila[2]
    assert proxima_empresa_da_fila(fila, fila[2]) == fila[3]
    assert proxima_empresa_da_fila(fila, fila[3]) == fila[0]  # volta ao inicio


def test_proxima_empresa_da_fila_ultima_fora_da_lista_comeca_do_topo():
    fila = empresas_elegiveis("PR")
    assert proxima_empresa_da_fila(fila, "Empresa que nao atende mais essa UF") == fila[0]


def test_proxima_empresa_da_fila_vazia():
    assert proxima_empresa_da_fila([], None) is None
    assert proxima_empresa_da_fila([], "qualquer") is None


def test_label_empresa_cnpj():
    valor = "AMG Logistica Ltda|53.805.774/0001-56"
    assert label_empresa_cnpj(valor) == "AMG Logistica Ltda — PR — 53.805.774/0001-56"


def test_label_empresa_cnpj_none_ou_invalido():
    assert label_empresa_cnpj(None) is None
    assert label_empresa_cnpj("") is None
    # valor sem correspondencia: devolve o proprio valor (nao quebra o template)
    assert label_empresa_cnpj("Algo|123") == "Algo|123"
