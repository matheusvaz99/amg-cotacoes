"""Operacoes de banco: cotacoes, formacao de preco, solicitacao de frete,
ordem de coleta e agenda de carregamentos."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.constants import (
    ADMIN_TABS,
    AGENDA_AGUARDANDO,
    SOLICITACAO_ENVIADA,
    SOLICITACAO_PENDENTE,
    SOLICITACAO_VALIDADA,
    STATUS_APROVADA,
    STATUS_ENVIADA_LOGISTICA,
    STATUS_FRETE_SOLICITADO,
    STATUS_OC_EMITIDA,
    STATUS_RESPONDIDA,
)
from app.filiais import (
    FILIAIS_CNPJ,
    empresas_elegiveis,
    parse_empresa_cnpj,
    proxima_empresa_da_fila,
)
from app.models import (
    AgendaCarregamento,
    Opcao,
    OrdemColeta,
    Proposal,
    ProposalVersionLog,
    Quote,
    SolicitacaoFrete,
)
from app.utils import gen_oc_numero, gen_quote_code, utcnow

_QUOTE_RELATIONS = (
    selectinload(Quote.proposal),
    selectinload(Quote.solicitacao),
    selectinload(Quote.ordem_coleta).selectinload(OrdemColeta.agenda),
)


def create_quote(db: Session, values: dict[str, Any]) -> Quote:
    quote = Quote(code=gen_quote_code(db), **values)
    db.add(quote)
    db.commit()
    db.refresh(quote)
    return quote


def get_quote_by_code(db: Session, code: str) -> Quote | None:
    stmt = select(Quote).options(*_QUOTE_RELATIONS).where(Quote.code == code.strip().upper())
    return db.scalars(stmt).first()


def list_quotes_by_email(db: Session, email: str) -> list[Quote]:
    stmt = (
        select(Quote)
        .options(*_QUOTE_RELATIONS)
        .where(Quote.client_email == email.strip().lower())
        .order_by(Quote.created_at.desc())
    )
    return list(db.scalars(stmt))


def list_quotes(
    db: Session, *, tab: str = "todas", search: str = "", empresa: str = "", tipo: str = ""
) -> list[Quote]:
    stmt = select(Quote).options(*_QUOTE_RELATIONS)

    statuses = ADMIN_TABS.get(tab)
    if statuses:
        stmt = stmt.where(Quote.status.in_(statuses))

    search = search.strip()
    if search:
        like = f"%{search}%"
        stmt = stmt.where(
            or_(
                Quote.code.ilike(like),
                Quote.origem_cidade.ilike(like),
                Quote.destino_cidade.ilike(like),
                Quote.client_name.ilike(like),
                Quote.client_company.ilike(like),
                Quote.client_email.ilike(like),
            )
        )

    if empresa.strip():
        stmt = stmt.where(Quote.client_company.ilike(f"%{empresa.strip()}%"))
    if tipo.strip():
        stmt = stmt.where(Quote.tipo_cotacao == tipo.strip())

    stmt = stmt.order_by(Quote.created_at.desc())
    return list(db.scalars(stmt))


# ----- Formacao de preco (Proposal) --------------------------------------

_PROPOSAL_FIELDS = (
    "custo_motorista", "custo_pedagio", "custo_impostos", "custo_seguro",
    "custo_outros_internos", "fc", "margem_pct", "fe",
    "valor_diaria", "valor_ajudante",
    "valor_empilhadeira", "valor_guincho", "custos_adicionais",
    "custos_adicionais_desc", "valor_final",
    "prazo_entrega", "validade", "observacoes",
)


def add_proposal(
    db: Session, quote: Quote, values: dict[str, Any], *, created_by: str | None = None
) -> Proposal:
    """Grava a formacao de preco atual da cotacao. Se ja existia uma proposta
    (reprecificacao apos negociacao), a versao anterior fica registrada em
    ProposalVersionLog antes de ser sobrescrita — nunca e apagada sem rastro."""
    versao = 1
    existing = quote.proposal
    if existing is not None:
        versao = existing.versao + 1
        db.add(
            ProposalVersionLog(
                quote_id=quote.id,
                versao=existing.versao,
                fc=existing.fc,
                margem_pct=existing.margem_pct,
                fe=existing.fe,
                valor_final=existing.valor_final,
                motivo_negociacao=quote.decision_note,
                criado_por=existing.created_by,
                criado_em=existing.created_at,
            )
        )
        db.delete(existing)
        db.flush()

    proposal = Proposal(
        quote_id=quote.id,
        created_by=created_by,
        versao=versao,
        **{k: values[k] for k in _PROPOSAL_FIELDS},
    )
    db.add(proposal)
    quote.status = STATUS_RESPONDIDA
    quote.decision_note = None  # negociacao (se havia) foi respondida
    db.commit()
    db.refresh(quote)
    return proposal


def list_proposal_history(db: Session, quote_id: int) -> list[ProposalVersionLog]:
    stmt = (
        select(ProposalVersionLog)
        .where(ProposalVersionLog.quote_id == quote_id)
        .order_by(ProposalVersionLog.versao)
    )
    return list(db.scalars(stmt))


def set_status(
    db: Session, quote: Quote, status: str, *, decision_note: str | None = None
) -> Quote:
    quote.status = status
    if decision_note is not None:
        quote.decision_note = decision_note
    db.commit()
    db.refresh(quote)
    return quote


# ----- Solicitacao de Frete -> Ordem de Coleta -> Logistica ---------------

def create_or_update_solicitacao(
    db: Session, quote: Quote, values: dict[str, Any]
) -> SolicitacaoFrete:
    solicitacao = quote.solicitacao
    if solicitacao is None:
        solicitacao = SolicitacaoFrete(quote_id=quote.id, **values, status=SOLICITACAO_ENVIADA)
        db.add(solicitacao)
    else:
        for key, val in values.items():
            setattr(solicitacao, key, val)
        solicitacao.status = SOLICITACAO_ENVIADA
    quote.status = STATUS_FRETE_SOLICITADO
    db.commit()
    db.refresh(quote)
    return quote.solicitacao


def devolver_solicitacao(db: Session, quote: Quote, motivo: str) -> Quote:
    if quote.solicitacao is not None:
        quote.solicitacao.status = SOLICITACAO_PENDENTE
    quote.status = STATUS_APROVADA
    quote.decision_note = motivo
    db.commit()
    db.refresh(quote)
    return quote


def sugestao_empresa_cnpj_fila(db: Session, uf: str | None) -> str | None:
    """Sugestao de empresa/CNPJ para a UF informada, em rodizio quando mais
    de uma empresa tem filial ali: olha a ultima OC realmente gerada para
    essa UF (qualquer que tenha sido a escolha do admin, sugerida ou nao) e
    sugere a proxima da fila. Sem historico, comeca do topo da prioridade."""
    elegiveis = empresas_elegiveis(uf)
    if not elegiveis:
        return None
    ultima_empresa = db.scalars(
        select(OrdemColeta.empresa)
        .where(OrdemColeta.uf_referencia == uf)
        .order_by(OrdemColeta.gerado_em.desc())
        .limit(1)
    ).first()
    proxima = proxima_empresa_da_fila(elegiveis, ultima_empresa)
    return f"{proxima}|{FILIAIS_CNPJ[proxima][uf]}"


def resolver_empresa_cnpj_oc(
    db: Session, uf: str | None, escolha_manual: str | None
) -> tuple[str, str] | None:
    """Decide quem emite a OC: a escolha do dropdown (`escolha_manual`)
    sempre manda -- o rodizio por UF so serve pra pre-selecionar uma
    sugestao no formulario, o admin confirma ou troca livremente antes de
    emitir. Sem escolha valida, cai de volta na sugestao (ex.: reenvio do
    form sem alterar o campo oculto)."""
    escolhida = parse_empresa_cnpj(escolha_manual)
    if escolhida:
        return escolhida
    sugestao = sugestao_empresa_cnpj_fila(db, uf)
    return parse_empresa_cnpj(sugestao)


_ENDERECO_FIELDS = (
    "origem_cidade", "origem_cep", "origem_endereco", "origem_numero", "origem_bairro",
    "destino_cidade", "destino_cep", "destino_endereco", "destino_numero", "destino_bairro",
)


def update_quote_enderecos(db: Session, quote: Quote, values: dict[str, Any]) -> Quote:
    """Aplica a confirmacao/edicao dos enderecos de coleta e entrega feita na
    tela de geracao da Ordem de Coleta de volta na propria cotacao -- ela e a
    fonte unica usada pelo docx/PDF, entao nao ha copia separada pra manter."""
    for campo in _ENDERECO_FIELDS:
        if campo in values:
            setattr(quote, campo, values[campo])
    db.commit()
    db.refresh(quote)
    return quote


def gerar_ordem_coleta(
    db: Session, quote: Quote, *, empresa: str, cnpj_filial: str,
    uf_referencia: str | None = None, gerado_por: str | None = None,
) -> OrdemColeta:
    oc = OrdemColeta(
        numero=gen_oc_numero(db),
        quote_id=quote.id,
        solicitacao_id=quote.solicitacao.id,
        gerado_por=gerado_por,
        empresa=empresa,
        cnpj_filial=cnpj_filial,
        uf_referencia=uf_referencia,
    )
    db.add(oc)
    quote.solicitacao.status = SOLICITACAO_VALIDADA
    quote.status = STATUS_OC_EMITIDA
    db.commit()
    db.refresh(quote)
    return oc


def enviar_logistica(db: Session, quote: Quote, *, enviado_por: str | None = None) -> AgendaCarregamento:
    oc = quote.ordem_coleta
    oc.enviado_logistica_em = utcnow()
    oc.enviado_por = enviado_por

    agenda = AgendaCarregamento(
        ordem_coleta_id=oc.id,
        data_carregamento=quote.data_coleta,
        status_agenda=AGENDA_AGUARDANDO,
    )
    db.add(agenda)
    quote.status = STATUS_ENVIADA_LOGISTICA
    db.commit()
    db.refresh(quote)
    return agenda


# ----- Agenda de Carregamentos --------------------------------------------

def list_agenda(
    db: Session, *, status: str = "", inicio: date | None = None, fim: date | None = None
) -> list[AgendaCarregamento]:
    stmt = select(AgendaCarregamento).options(
        selectinload(AgendaCarregamento.ordem_coleta).selectinload(OrdemColeta.quote)
    )
    if status:
        stmt = stmt.where(AgendaCarregamento.status_agenda == status)
    if inicio:
        stmt = stmt.where(AgendaCarregamento.data_carregamento >= inicio)
    if fim:
        stmt = stmt.where(AgendaCarregamento.data_carregamento <= fim)
    stmt = stmt.order_by(AgendaCarregamento.data_carregamento, AgendaCarregamento.hora_prevista)
    return list(db.scalars(stmt))


def get_agenda_item(db: Session, agenda_id: int) -> AgendaCarregamento | None:
    stmt = (
        select(AgendaCarregamento)
        .options(selectinload(AgendaCarregamento.ordem_coleta).selectinload(OrdemColeta.quote))
        .where(AgendaCarregamento.id == agenda_id)
    )
    return db.scalars(stmt).first()


def update_agenda(db: Session, item: AgendaCarregamento, values: dict[str, Any]) -> AgendaCarregamento:
    item.data_carregamento = values["data_carregamento"]
    item.hora_prevista = values["hora_prevista"]
    item.responsavel_logistica = values["responsavel_logistica"]
    item.status_agenda = values["status_agenda"]
    item.confirmado = values["confirmado"]
    item.observacoes = values["observacoes"]
    db.commit()
    db.refresh(item)
    return item


# ----- Opcoes de cadastro (carrocerias, tipos de veiculo, ...) -----------
# Uma unica tabela `opcoes`, particionada por `categoria`, atende qualquer
# lista que o admin precise manter (ver app.constants.OPCOES_CATEGORIAS).

def list_opcoes(db: Session, categoria: str, *, active_only: bool = False) -> list[Opcao]:
    stmt = select(Opcao).where(Opcao.categoria == categoria)
    if active_only:
        stmt = stmt.where(Opcao.ativa.is_(True))
    return list(db.scalars(stmt.order_by(Opcao.nome)))


def opcao_names(db: Session, categoria: str, *, active_only: bool = True) -> list[str]:
    return [o.nome for o in list_opcoes(db, categoria, active_only=active_only)]


def get_opcao(db: Session, opcao_id: int) -> Opcao | None:
    return db.get(Opcao, opcao_id)


def create_opcao(db: Session, categoria: str, nome: str) -> Opcao | None:
    nome = nome.strip()
    if not nome:
        return None
    exists = db.scalars(
        select(Opcao).where(
            Opcao.categoria == categoria, func.lower(Opcao.nome) == nome.lower()
        )
    ).first()
    if exists:
        return exists
    opcao = Opcao(categoria=categoria, nome=nome)
    db.add(opcao)
    db.commit()
    db.refresh(opcao)
    return opcao


def rename_opcao(db: Session, opcao: Opcao, novo_nome: str) -> Opcao | None:
    """Renomeia a opcao. Devolve None se ja existir outra com o mesmo nome
    na categoria (conflito), sem alterar nada."""
    novo_nome = novo_nome.strip()
    if not novo_nome:
        return None
    duplicado = db.scalars(
        select(Opcao).where(
            Opcao.categoria == opcao.categoria,
            func.lower(Opcao.nome) == novo_nome.lower(),
            Opcao.id != opcao.id,
        )
    ).first()
    if duplicado:
        return None
    opcao.nome = novo_nome
    db.commit()
    db.refresh(opcao)
    return opcao


def toggle_opcao(db: Session, opcao: Opcao) -> Opcao:
    opcao.ativa = not opcao.ativa
    db.commit()
    db.refresh(opcao)
    return opcao


def delete_opcao(db: Session, opcao: Opcao) -> None:
    db.delete(opcao)
    db.commit()
