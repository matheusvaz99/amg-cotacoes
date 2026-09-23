"""Popula o banco com cotacoes de exemplo em cada estagio do pipeline
(em analise -> respondida -> negociacao -> aprovada -> solicitacao de frete
-> Ordem de Coleta -> Logistica -> Agenda de Carregamentos), para validar o
fluxo completo no painel.

Uso:  python seed.py
"""

from datetime import date, timedelta
from decimal import Decimal

from app import crud
from app.constants import PAGADOR_OPCOES, TIPO_COTACAO_RAPIDA
from app.database import SessionLocal, init_db
from app.filiais import extrair_uf


def _empresa_cnpj_para(db, quote):
    uf = extrair_uf(quote.destino_cidade)
    escolha = crud.resolver_empresa_cnpj_oc(db, uf, None)
    return escolha or ("AMG Logistica Ltda", "53.805.774/0001-56")

D = Decimal
TWO = D("0.01")


def _proposta_values(
    *, motorista, pedagio=D("0"), impostos=D("0"), seguro=D("0"), outros_internos=D("0"),
    margem_pct=D("20"), diaria=D("0"), ajudante=D("0"),
    empilhadeira=D("0"), guincho=D("0"), outros=D("0"), outros_desc=None,
    prazo_entrega="1 dia útil", validade_dias=7, observacoes=None,
):
    fc = (motorista + pedagio + impostos + seguro + outros_internos).quantize(TWO)
    fe = (fc * (D("1") + margem_pct / D("100"))).quantize(TWO)
    adicionais = diaria + ajudante + empilhadeira + guincho + outros
    return dict(
        custo_motorista=motorista, custo_pedagio=pedagio, custo_impostos=impostos,
        custo_seguro=seguro, custo_outros_internos=outros_internos, fc=fc,
        margem_pct=margem_pct, fe=fe,
        valor_diaria=diaria,
        valor_ajudante=ajudante, valor_empilhadeira=empilhadeira, valor_guincho=guincho,
        custos_adicionais=outros, custos_adicionais_desc=outros_desc,
        valor_final=(fe + adicionais).quantize(TWO),
        prazo_entrega=prazo_entrega,
        validade=date.today() + timedelta(days=validade_dias),
        observacoes=observacoes,
    )


def _quote(db, **kw):
    kw.setdefault("descricao_material", None)
    kw.setdefault("dimensoes", None)
    kw.setdefault("qtd_volumes", 10)
    kw.setdefault("valor_nf", D("25000.00"))
    kw.setdefault("servico_diaria", False)
    kw.setdefault("servico_guincho", False)
    kw.setdefault("servico_ajudante", False)
    kw.setdefault("servico_empilhadeira", False)
    kw.setdefault("ajudante_qtd", None)
    kw.setdefault("tipo_veiculo", "Truck")
    kw.setdefault("carroceria", "Sider")
    kw.setdefault("capacidade_aprox", "10 toneladas")
    kw.setdefault("data_entrega", None)
    kw.setdefault("observacoes", None)
    kw.setdefault("client_phone", None)
    kw.setdefault("origem_cep", None)
    kw.setdefault("origem_endereco", None)
    kw.setdefault("origem_bairro", None)
    kw.setdefault("destino_cep", None)
    kw.setdefault("destino_endereco", None)
    kw.setdefault("destino_bairro", None)
    q = crud.create_quote(db, kw)
    print("criada", q.code, "-", q.tipo_cotacao, "-", q.rota)
    return q


def run() -> None:
    init_db()
    db = SessionLocal()
    try:
        # 1) Em analise (cotacao rapida, sem proposta ainda)
        _quote(
            db, client_name="Fulano Rapido", client_company="Empresa Rapida LTDA",
            client_email="rapido@exemplo.com", tipo_cotacao=TIPO_COTACAO_RAPIDA,
            origem_cidade="Curitiba - PR", destino_cidade="Londrina - PR",
            tipo_material="Andaime", peso_total_kg=D("3000.00"), valor_nf=None,
            qtd_volumes=None, tipo_veiculo=None, carroceria=None, capacidade_aprox=None,
            data_coleta=date.today() + timedelta(days=5),
        )

        # 2) Respondida (aguardando decisao do cliente)
        q2 = _quote(
            db, client_name="Marina Souza", client_company="Metalurgica Beta",
            client_email="logistica@beta.com.br", origem_cidade="Itajai - SC",
            destino_cidade="Maringa - PR", tipo_material="Estrutura metalica",
            peso_total_kg=D("12000.00"), valor_nf=D("80000.00"), servico_diaria=True,
            tipo_veiculo="Carreta Grade Baixa",
            carroceria="Grade baixa", capacidade_aprox="30 toneladas",
            data_coleta=date.today() + timedelta(days=8),
        )
        crud.add_proposal(
            db, q2,
            _proposta_values(
                motorista=D("6500"), pedagio=D("620"), impostos=D("280"), seguro=D("160"),
                margem_pct=D("22"), diaria=D("450"),
            ),
            created_by="seed",
        )
        print("  -> respondida")

        # 3) Negociacao (cliente pediu ajuste)
        q3 = _quote(
            db, client_name="Carlos Lima", client_company="Obras Gamma",
            client_email="gamma@obras.com.br", origem_cidade="Sao Paulo - SP",
            destino_cidade="Curitiba - PR", tipo_material="Material de construcao",
            peso_total_kg=D("18000.00"), valor_nf=D("42000.00"), servico_guincho=True,
            tipo_veiculo="Truck", carroceria="Bau", capacidade_aprox="14 toneladas",
            data_coleta=date.today() + timedelta(days=3),
        )
        crud.add_proposal(
            db, q3,
            _proposta_values(motorista=D("2900"), pedagio=D("50"), seguro=D("84"), margem_pct=D("20"), guincho=D("350")),
            created_by="seed",
        )
        crud.set_status(db, q3, "negociacao", decision_note="Consegue rever a margem? Valor ficou acima do orcamento.")
        print("  -> negociacao")

        # 4) Aprovada (aguardando solicitacao de frete)
        q4 = _quote(
            db, client_name="Ana Martins", client_company="Construtora Alfa",
            client_email="compras@alfa.com.br", origem_cidade="Campinas - SP",
            destino_cidade="Bauru - SP", tipo_material="Andaime",
            peso_total_kg=D("5000.00"), valor_nf=D("25000.00"),
            tipo_veiculo="Carreta Sider", carroceria="Sider", capacidade_aprox="28 toneladas",
            data_coleta=date.today() + timedelta(days=6),
        )
        crud.add_proposal(
            db, q4, _proposta_values(motorista=D("2400"), pedagio=D("40"), seguro=D("50"), margem_pct=D("18")),
            created_by="seed",
        )
        crud.set_status(db, q4, "aprovada")
        print("  -> aprovada")

        # 5) Frete solicitado (aguardando validacao do comercial)
        q5 = _quote(
            db, client_name="Pedro Alves", client_company="Cliente E Engenharia",
            client_email="pedro@clientee.com.br", origem_cidade="Curitiba - PR",
            destino_cidade="Sao Paulo - SP", tipo_material="Piso elevado",
            peso_total_kg=D("9000.00"), valor_nf=D("35000.00"),
            tipo_veiculo="Truck", carroceria="Sider", capacidade_aprox="12 toneladas",
            data_coleta=date.today() + timedelta(days=4),
        )
        crud.add_proposal(db, q5, _proposta_values(motorista=D("3100"), pedagio=D("60"), seguro=D("70"), margem_pct=D("20")), created_by="seed")
        crud.set_status(db, q5, "aprovada")
        crud.create_or_update_solicitacao(db, q5, dict(
            pagador=PAGADOR_OPCOES[0], pagador_documento="12.345.678/0001-90",
            fornecedor_nome="Cliente E Engenharia", fornecedor_contato="(41) 99999-1111",
            destinatario_nome="Obra Sao Paulo Sul", destinatario_contato="(11) 98888-2222",
            valor_nf=D("35000.00"), observacoes_operacionais="Descarga com acesso restrito, avisar com antecedencia.",
        ))
        print("  -> frete solicitado")

        # 6) OC emitida (aguardando envio a Logistica)
        q6 = _quote(
            db, client_name="Luciana Reis", client_company="Cliente F Estruturas",
            client_email="luciana@clientef.com.br", origem_cidade="Joinville - SC",
            destino_cidade="Belo Horizonte - MG", tipo_material="Equipamentos",
            peso_total_kg=D("14000.00"), valor_nf=D("60000.00"),
            tipo_veiculo="Carreta Sider", carroceria="Sider", capacidade_aprox="24 toneladas",
            data_coleta=date.today() + timedelta(days=2),
        )
        crud.add_proposal(db, q6, _proposta_values(motorista=D("5200"), pedagio=D("480"), seguro=D("120"), margem_pct=D("20")), created_by="seed")
        crud.set_status(db, q6, "aprovada")
        crud.create_or_update_solicitacao(db, q6, dict(
            pagador=PAGADOR_OPCOES[1], pagador_documento="98.765.432/0001-10",
            fornecedor_nome="Cliente F Estruturas", fornecedor_contato=None,
            destinatario_nome="Filial BH", destinatario_contato="(31) 97777-3333",
            valor_nf=D("60000.00"), observacoes_operacionais=None,
        ))
        empresa6, cnpj6 = _empresa_cnpj_para(db, q6)
        crud.gerar_ordem_coleta(
            db, q6, empresa=empresa6, cnpj_filial=cnpj6,
            uf_referencia=extrair_uf(q6.destino_cidade), gerado_por="seed",
        )
        print("  -> OC emitida")

        # 7) Enviada a Logistica -> Agenda (variedade de datas p/ alertas)
        agenda_datas = [
            ("Rodrigo Nunes", "Cliente G Andaimes", "rodrigo@clienteg.com.br", "Curitiba - PR", "Londrina - PR", 0, "Confirmado"),
            ("Sabrina Costa", "Cliente H Formas", "sabrina@clienteh.com.br", "Itajai - SC", "Maringa - PR", 1, "Aguardando confirmacao"),
            ("Bruno Farias", "Cliente I Montagens", "bruno@clientei.com.br", "Sao Paulo - SP", "Goiania - GO", 4, "Programado"),
            ("Elaine Prado", "Cliente J Estruturas", "elaine@clientej.com.br", "Contagem - MG", "Curitiba - PR", -2, "Aguardando confirmacao"),
        ]
        for nome, empresa, email, origem, destino, dias, status_label in agenda_datas:
            qn = _quote(
                db, client_name=nome, client_company=empresa, client_email=email,
                origem_cidade=origem, destino_cidade=destino, tipo_material="Estruturas metalicas",
                peso_total_kg=D("8000.00"), valor_nf=D("30000.00"),
                tipo_veiculo="Truck", carroceria="Sider", capacidade_aprox="15 toneladas",
                data_coleta=date.today() + timedelta(days=dias),
            )
            crud.add_proposal(db, qn, _proposta_values(motorista=D("2800"), pedagio=D("70"), seguro=D("60"), margem_pct=D("20")), created_by="seed")
            crud.set_status(db, qn, "aprovada")
            crud.create_or_update_solicitacao(db, qn, dict(
                pagador=PAGADOR_OPCOES[0], pagador_documento="11.222.333/0001-44",
                fornecedor_nome=empresa, fornecedor_contato=None,
                destinatario_nome=f"Obra {destino}", destinatario_contato=None,
                valor_nf=D("30000.00"), observacoes_operacionais=None,
            ))
            empresa_n, cnpj_n = _empresa_cnpj_para(db, qn)
            crud.gerar_ordem_coleta(
                db, qn, empresa=empresa_n, cnpj_filial=cnpj_n,
                uf_referencia=extrair_uf(qn.destino_cidade), gerado_por="seed",
            )
            agenda = crud.enviar_logistica(db, qn, enviado_por="seed")
            agenda.responsavel_logistica = "Ryan"
            if status_label == "Confirmado":
                agenda.status_agenda = "confirmado"
                agenda.confirmado = True
                agenda.hora_prevista = "08:00"
            elif status_label == "Programado":
                agenda.status_agenda = "programado"
                agenda.hora_prevista = "14:00"
            db.commit()
        print("  -> 4 cotacoes enviadas a Logistica, na Agenda de Carregamentos")

    finally:
        db.close()


if __name__ == "__main__":
    run()
