"""Operacoes de banco para cotacoes e propostas."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.constants import ADMIN_TABS, STATUS_RESPONDIDA
from app.models import Opcao, Proposal, Quote
from app.utils import gen_quote_code


def create_quote(db: Session, values: dict[str, Any]) -> Quote:
    quote = Quote(code=gen_quote_code(db), **values)
    db.add(quote)
    db.commit()
    db.refresh(quote)
    return quote


def get_quote_by_code(db: Session, code: str) -> Quote | None:
    stmt = (
        select(Quote)
        .options(selectinload(Quote.proposal))
        .where(Quote.code == code.strip().upper())
    )
    return db.scalars(stmt).first()


def list_quotes_by_email(db: Session, email: str) -> list[Quote]:
    stmt = (
        select(Quote)
        .options(selectinload(Quote.proposal))
        .where(Quote.client_email == email.strip().lower())
        .order_by(Quote.created_at.desc())
    )
    return list(db.scalars(stmt))


def list_quotes(db: Session, *, tab: str = "todas", search: str = "") -> list[Quote]:
    stmt = select(Quote).options(selectinload(Quote.proposal))

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
                Quote.client_email.ilike(like),
            )
        )

    stmt = stmt.order_by(Quote.created_at.desc())
    return list(db.scalars(stmt))


def add_proposal(
    db: Session, quote: Quote, values: dict[str, Any], *, created_by: str | None = None
) -> Proposal:
    if quote.proposal is not None:
        db.delete(quote.proposal)
        db.flush()

    proposal = Proposal(
        quote_id=quote.id,
        created_by=created_by,
        frete=values["frete"],
        pedagio=values["pedagio"],
        seguro=values["seguro"],
        total=values["total"],
        prazo_entrega=values["prazo_entrega"],
        validade=values["validade"],
        observacoes=values["observacoes"],
    )
    db.add(proposal)
    quote.status = STATUS_RESPONDIDA
    db.commit()
    db.refresh(quote)
    return proposal


def set_status(
    db: Session, quote: Quote, status: str, *, decision_note: str | None = None
) -> Quote:
    quote.status = status
    if decision_note is not None:
        quote.client_decision_note = decision_note
    db.commit()
    db.refresh(quote)
    return quote


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
