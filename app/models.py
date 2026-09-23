"""Modelos de dados: Quote (cotacao), Proposal (formacao de preco), historico de
versoes, Solicitacao de Frete, Ordem de Coleta e Agenda de Carregamentos."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants import STATUS_EM_ANALISE, TIPO_COTACAO_COMPLETA
from app.database import Base
from app.utils import utcnow


class Quote(Base):
    __tablename__ = "quotes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )
    status: Mapped[str] = mapped_column(
        String(30), default=STATUS_EM_ANALISE, index=True
    )
    tipo_cotacao: Mapped[str] = mapped_column(
        String(20), default=TIPO_COTACAO_COMPLETA, index=True
    )

    # Contato
    client_name: Mapped[str] = mapped_column(String(120))  # nome do comprador
    client_company: Mapped[str] = mapped_column(String(160), default="")  # empresa
    client_email: Mapped[str | None] = mapped_column(String(180), index=True, nullable=True)
    client_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)

    # Origem (coleta)
    origem_cidade: Mapped[str] = mapped_column(String(120))
    origem_cep: Mapped[str | None] = mapped_column(String(12), nullable=True)
    origem_endereco: Mapped[str | None] = mapped_column(String(200), nullable=True)
    origem_bairro: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # Destino (entrega)
    destino_cidade: Mapped[str] = mapped_column(String(120))
    destino_cep: Mapped[str | None] = mapped_column(String(12), nullable=True)
    destino_endereco: Mapped[str | None] = mapped_column(String(200), nullable=True)
    destino_bairro: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # Carga
    tipo_material: Mapped[str] = mapped_column(String(120))
    descricao_material: Mapped[str | None] = mapped_column(Text, nullable=True)
    qtd_volumes: Mapped[int | None] = mapped_column(nullable=True)
    dimensoes: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # peso_total_kg era numerico fixo em kg; peso agora e texto livre (o
    # cliente escreve a unidade -- kg ou toneladas). Coluna legada mantida
    # sem DROP, nao usada pelo codigo novo.
    peso_total_kg: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    peso_total: Mapped[str | None] = mapped_column(String(60), nullable=True)
    valor_nf: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    # carga/descarga removidos das opcoes (cliente e precificacao) -- colunas
    # legadas mantidas sem DROP, nao usadas pelo codigo novo.
    servico_carga: Mapped[bool] = mapped_column(Boolean, default=False)
    servico_descarga: Mapped[bool] = mapped_column(Boolean, default=False)
    servico_diaria: Mapped[bool] = mapped_column(Boolean, default=False)
    servico_guincho: Mapped[bool] = mapped_column(Boolean, default=False)
    servico_ajudante: Mapped[bool] = mapped_column(Boolean, default=False)
    servico_empilhadeira: Mapped[bool] = mapped_column(Boolean, default=False)
    ajudante_qtd: Mapped[int | None] = mapped_column(nullable=True)

    # Transporte
    tipo_veiculo: Mapped[str | None] = mapped_column(String(120), nullable=True)
    carroceria: Mapped[str | None] = mapped_column(String(120), nullable=True)
    capacidade_aprox: Mapped[str | None] = mapped_column(String(80), nullable=True)
    data_coleta: Mapped[date] = mapped_column(Date)
    data_entrega: Mapped[date | None] = mapped_column(Date, nullable=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Nota da decisao do cliente/admin: vazia ao aprovar, motivo ao negociar/reprovar
    # ou ao devolver uma solicitacao de frete para correcao.
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    proposal: Mapped[Proposal | None] = relationship(
        back_populates="quote", uselist=False, cascade="all, delete-orphan"
    )
    solicitacao: Mapped[SolicitacaoFrete | None] = relationship(
        back_populates="quote", uselist=False, cascade="all, delete-orphan"
    )
    ordem_coleta: Mapped[OrdemColeta | None] = relationship(
        back_populates="quote", uselist=False, cascade="all, delete-orphan"
    )

    @property
    def rota(self) -> str:
        return f"{self.origem_cidade}  →  {self.destino_cidade}"

    @property
    def is_rapida(self) -> bool:
        from app.constants import TIPO_COTACAO_RAPIDA

        return self.tipo_cotacao == TIPO_COTACAO_RAPIDA


class Proposal(Base):
    """Formacao de preco: FC (custo interno) -> margem -> FE (preco de venda) +
    adicionais. Representa a proposta ATUAL da cotacao (1 por Quote); versoes
    anteriores ficam registradas em ProposalVersionLog antes de serem substituidas."""

    __tablename__ = "proposals"

    id: Mapped[int] = mapped_column(primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    created_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    versao: Mapped[int] = mapped_column(default=1)

    # --- colunas legadas (nao usadas pelo codigo novo, mantidas sem DROP) ---
    frete: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    pedagio: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    seguro: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    total: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)

    # --- FC: Frete Custo (uso exclusivo do comercial, nunca exibido ao cliente) ---
    custo_motorista: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    custo_pedagio: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    custo_impostos: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    custo_seguro: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    custo_outros_internos: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    fc: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))

    # --- Margem / FE: preco de venda (o que o cliente ve) ---
    margem_pct: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=Decimal("0.00"))
    fe: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))

    # carga/descarga removidos das opcoes (cliente e precificacao) -- colunas
    # legadas mantidas sem DROP, nao usadas pelo codigo novo.
    valor_carga: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    valor_descarga: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))

    # --- Adicionais precificaveis (visiveis ao cliente somente os cobrados) ---
    valor_diaria: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    valor_ajudante: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    valor_empilhadeira: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    valor_guincho: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    custos_adicionais: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))  # "Outros"
    custos_adicionais_desc: Mapped[str | None] = mapped_column(Text, nullable=True)

    valor_final: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))

    prazo_entrega: Mapped[str] = mapped_column(String(80))
    validade: Mapped[date] = mapped_column(Date)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)

    quote: Mapped[Quote] = relationship(back_populates="proposal")

    ADICIONAIS_LABELS = {
        "valor_diaria": "Diária",
        "valor_ajudante": "Ajudante",
        "valor_empilhadeira": "Empilhadeira",
        "valor_guincho": "Guincho / Munck",
    }

    def adicionais_itens(self) -> list[tuple[str, Decimal]]:
        """Lista (label, valor) dos adicionais efetivamente cobrados (> 0), na
        ordem da planilha, com 'Outros' (com descricao) por ultimo."""
        itens = []
        for campo, label in self.ADICIONAIS_LABELS.items():
            valor = getattr(self, campo) or Decimal("0.00")
            if valor > 0:
                itens.append((label, valor))
        if self.custos_adicionais and self.custos_adicionais > 0:
            desc = self.custos_adicionais_desc or "Outros"
            itens.append((desc, self.custos_adicionais))
        return itens

    @property
    def adicionais_total(self) -> Decimal:
        return sum((v for _, v in self.adicionais_itens()), Decimal("0.00"))

    @property
    def expirada(self) -> bool:
        from app.utils import utcnow as _now

        return self.validade < _now().date()


class ProposalVersionLog(Base):
    """Registro append-only de cada versao anterior da proposta, gravado logo
    antes de ela ser sobrescrita por uma reprecificacao apos negociacao."""

    __tablename__ = "proposal_version_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"), index=True)
    versao: Mapped[int] = mapped_column()
    fc: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    margem_pct: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    fe: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    valor_final: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    motivo_negociacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_por: Mapped[str | None] = mapped_column(String(120), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class SolicitacaoFrete(Base):
    """Dados operacionais/fiscais preenchidos pelo cliente apos a cotacao ser
    aprovada, necessarios para emitir a Ordem de Coleta."""

    __tablename__ = "solicitacoes_frete"

    id: Mapped[int] = mapped_column(primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    pagador: Mapped[str] = mapped_column(String(20))  # remetente | destinatario | terceiro
    pagador_documento: Mapped[str] = mapped_column(String(20))  # CNPJ/CPF
    fornecedor_nome: Mapped[str] = mapped_column(String(160))
    fornecedor_contato: Mapped[str | None] = mapped_column(String(120), nullable=True)
    destinatario_nome: Mapped[str] = mapped_column(String(160))
    destinatario_contato: Mapped[str | None] = mapped_column(String(120), nullable=True)
    valor_nf: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    observacoes_operacionais: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="enviada")

    quote: Mapped[Quote] = relationship(back_populates="solicitacao")


class OrdemColeta(Base):
    __tablename__ = "ordens_coleta"

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"), unique=True)
    solicitacao_id: Mapped[int] = mapped_column(ForeignKey("solicitacoes_frete.id"))

    gerado_em: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    gerado_por: Mapped[str | None] = mapped_column(String(120), nullable=True)
    enviado_logistica_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    enviado_por: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # Empresa do grupo AMG (e respectivo CNPJ de filial) que emite esta OC —
    # define tambem qual modelo .docx e usado. Ver app.filiais.
    empresa: Mapped[str | None] = mapped_column(String(120), nullable=True)
    cnpj_filial: Mapped[str | None] = mapped_column(String(20), nullable=True)
    uf_referencia: Mapped[str | None] = mapped_column(String(2), nullable=True)

    quote: Mapped[Quote] = relationship(back_populates="ordem_coleta")
    agenda: Mapped[AgendaCarregamento | None] = relationship(
        back_populates="ordem_coleta", uselist=False, cascade="all, delete-orphan"
    )


class AgendaCarregamento(Base):
    """Compromisso de carregamento, criado automaticamente quando a Ordem de
    Coleta e enviada a Logistica. Serve para acompanhamento comercial; nao
    substitui a operacao logistica em si."""

    __tablename__ = "agenda_carregamentos"

    id: Mapped[int] = mapped_column(primary_key=True)
    ordem_coleta_id: Mapped[int] = mapped_column(ForeignKey("ordens_coleta.id"), unique=True)

    data_carregamento: Mapped[date] = mapped_column(Date, index=True)
    hora_prevista: Mapped[str | None] = mapped_column(String(10), nullable=True)
    responsavel_logistica: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status_agenda: Mapped[str] = mapped_column(String(30), default="aguardando_confirmacao")
    confirmado: Mapped[bool] = mapped_column(Boolean, default=False)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    ordem_coleta: Mapped[OrdemColeta] = relationship(back_populates="agenda")


class Opcao(Base):
    """Opcoes de cadastro geridas pelo painel (carroceria, tipo de veiculo, ...).

    Uma unica tabela genérica evita duplicar modelo/CRUD/telas para cada
    lista de opcoes que o comercial precisa manter; `categoria` distingue
    qual lista a linha pertence (ver `app.constants.OPCOES_CATEGORIAS`).
    """

    __tablename__ = "opcoes"
    __table_args__ = (UniqueConstraint("categoria", "nome", name="uq_opcao_categoria_nome"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    categoria: Mapped[str] = mapped_column(String(40), index=True)
    nome: Mapped[str] = mapped_column(String(120))
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
