"""Testes de app/filiais.py: mapeamento empresa/UF -> CNPJ e modelo .docx,
usado para emitir a Ordem de Coleta com a filial correta."""

from app.filiais import (
    EMPRESA_TEMPLATE,
    FILIAIS_CNPJ,
    extrair_uf,
    opcoes_empresa_cnpj,
    parse_empresa_cnpj,
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
    # PR tem filial em 3 das 4 empresas -- prioridade e a ordem do dict
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
