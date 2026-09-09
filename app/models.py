"""Modelos de dados: Quote (cotacao) e Proposal (proposta do comercial)."""

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

from app.constants import STATUS_ABERTA
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
    status: Mapped[str] = mapped_column(String(30), default=STATUS_ABERTA, index=True)

    # Contato
    client_name: Mapped[str] = mapped_column(String(120))  # nome do comprador
    client_company: Mapped[str] = mapped_column(String(160), default="")  # empresa
    client_email: Mapped[str] = mapped_column(String(180), index=True)
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
    qtd_volumes: Mapped[int] = mapped_column()
    peso_total_kg: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    valor_nf: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    servico_carga: Mapped[bool] = mapped_column(Boolean, default=False)
    servico_descarga: Mapped[bool] = mapped_column(Boolean, default=False)
    servico_diaria: Mapped[bool] = mapped_column(Boolean, default=False)
    servico_guincho: Mapped[bool] = mapped_column(Boolean, default=False)

    # Transporte
    tipo_veiculo: Mapped[str] = mapped_column(String(120))
    carroceria: Mapped[str | None] = mapped_column(String(120), nullable=True)
    capacidade_aprox: Mapped[str] = mapped_column(String(80))
    data_coleta: Mapped[date] = mapped_column(Date)
    data_entrega: Mapped[date | None] = mapped_column(Date, nullable=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Motivo informado pelo admin ao reprovar a cotacao
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    proposal: Mapped[Proposal | None] = relationship(
        back_populates="quote", uselist=False, cascade="all, delete-orphan"
    )

    @property
    def rota(self) -> str:
        return f"{self.origem_cidade}  →  {self.destino_cidade}"


class Proposal(Base):
    __tablename__ = "proposals"

    id: Mapped[int] = mapped_column(primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    created_by: Mapped[str | None] = mapped_column(String(120), nullable=True)

    frete: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    pedagio: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    seguro: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    # total = frete + pedagio + seguro  ("valor total do frete" para o cliente)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    # custo extra lancado pelo admin (guincho, armazenagem, etc.)
    custos_adicionais: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), default=Decimal("0.00")
    )
    custos_adicionais_desc: Mapped[str | None] = mapped_column(Text, nullable=True)

    prazo_entrega: Mapped[str] = mapped_column(String(80))
    validade: Mapped[date] = mapped_column(Date)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)

    quote: Mapped[Quote] = relationship(back_populates="proposal")

    @property
    def valor_total_frete(self) -> Decimal:
        """Frete + pedagio + seguro consolidados."""
        return self.total

    @property
    def valor_final(self) -> Decimal:
        """Valor total do frete + outros custos adicionais."""
        return self.total + (self.custos_adicionais or Decimal("0.00"))

    @property
    def expirada(self) -> bool:
        from app.utils import utcnow as _now

        return self.validade < _now().date()


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
