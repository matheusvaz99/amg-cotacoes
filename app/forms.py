"""Parsing e validacao dos formularios (cotacao do cliente e proposta do comercial)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.constants import OBSERVACAO_PADRAO_PROPOSTA, TIPOS_MATERIAL
from app.utils import (
    calc_seguro,
    normalize_cep,
    parse_brl,
    parse_int,
    parse_peso,
    utcnow,
)


def _clean(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _yesno(value: Any) -> bool:
    return _clean(value).lower() in {"sim", "true", "1", "on", "yes"}


@dataclass
class QuoteForm:
    """Valida os campos da cotacao. `data` sao os valores brutos do request.form."""

    data: dict[str, Any]
    allowed_carrocerias: list[str] | None = None
    allowed_tipos_veiculo: list[str] | None = None
    errors: dict[str, str] = field(default_factory=dict)
    values: dict[str, Any] = field(default_factory=dict)

    REQUIRED_LABELS = {
        "client_name": "Nome do comprador",
        "client_company": "Empresa que representa",
        "client_email": "E-mail",
        "origem_cidade": "Cidade de origem",
        "destino_cidade": "Cidade de destino",
        "tipo_material": "Tipo de material",
        "qtd_volumes": "Quantidade de volumes",
        "peso_total_kg": "Peso total aproximado",
        "valor_nf": "Valor aproximado da NF",
        "tipo_veiculo": "Tipo de veiculo desejado",
        "carroceria": "Carroceria",
        "capacidade_aprox": "Capacidade aproximada",
        "data_coleta": "Data prevista para coleta",
    }

    def validate(self) -> bool:
        d = self.data
        v = self.values

        # Texto simples obrigatorio
        for key in (
            "client_name",
            "client_company",
            "origem_cidade",
            "destino_cidade",
            "capacidade_aprox",
        ):
            v[key] = _clean(d.get(key))
            if not v[key]:
                self.errors[key] = f"{self.REQUIRED_LABELS[key]} e obrigatorio."

        # E-mail
        v["client_email"] = _clean(d.get("client_email")).lower()
        if not v["client_email"]:
            self.errors["client_email"] = "E-mail e obrigatorio."
        elif "@" not in v["client_email"] or "." not in v["client_email"].split("@")[-1]:
            self.errors["client_email"] = "Informe um e-mail valido."

        v["client_phone"] = _clean(d.get("client_phone")) or None

        # Selects obrigatorios
        v["tipo_material"] = _clean(d.get("tipo_material"))
        if not v["tipo_material"]:
            self.errors["tipo_material"] = "Selecione o tipo de material."
        elif v["tipo_material"] not in TIPOS_MATERIAL:
            self.errors["tipo_material"] = "Opcao invalida."

        v["tipo_veiculo"] = _clean(d.get("tipo_veiculo"))
        if not v["tipo_veiculo"]:
            self.errors["tipo_veiculo"] = "Selecione o tipo de veiculo."
        elif (
            self.allowed_tipos_veiculo is not None
            and v["tipo_veiculo"] not in self.allowed_tipos_veiculo
        ):
            self.errors["tipo_veiculo"] = "Opcao invalida."

        v["carroceria"] = _clean(d.get("carroceria"))
        if not v["carroceria"]:
            self.errors["carroceria"] = "Selecione a carroceria."
        elif (
            self.allowed_carrocerias is not None
            and v["carroceria"] not in self.allowed_carrocerias
        ):
            self.errors["carroceria"] = "Opcao invalida."

        # Numericos obrigatorios
        v["qtd_volumes"] = parse_int(d.get("qtd_volumes"))
        if v["qtd_volumes"] is None:
            self.errors["qtd_volumes"] = "Informe a quantidade de volumes."
        elif v["qtd_volumes"] <= 0:
            self.errors["qtd_volumes"] = "A quantidade deve ser maior que zero."

        v["peso_total_kg"] = parse_peso(d.get("peso_total_kg"))
        if v["peso_total_kg"] is None:
            self.errors["peso_total_kg"] = "Informe o peso total aproximado em kg."
        elif v["peso_total_kg"] <= 0:
            self.errors["peso_total_kg"] = "O peso deve ser maior que zero."

        v["valor_nf"] = parse_brl(d.get("valor_nf"))
        if v["valor_nf"] is None:
            self.errors["valor_nf"] = "Informe o valor aproximado da NF."
        elif v["valor_nf"] < 0:
            self.errors["valor_nf"] = "Valor invalido."

        # Data de coleta
        raw_date = _clean(d.get("data_coleta"))
        v["data_coleta"] = None
        if not raw_date:
            self.errors["data_coleta"] = "Informe a data prevista para coleta."
        else:
            try:
                parsed = datetime.strptime(raw_date, "%Y-%m-%d").date()
                if parsed < utcnow().date():
                    self.errors["data_coleta"] = "A data nao pode estar no passado."
                else:
                    v["data_coleta"] = parsed
            except ValueError:
                self.errors["data_coleta"] = "Data invalida."

        # Sim/Nao obrigatorios (default Nao)
        v["servico_carga"] = _yesno(d.get("servico_carga"))
        v["servico_descarga"] = _yesno(d.get("servico_descarga"))
        v["servico_diaria"] = _yesno(d.get("servico_diaria"))
        v["servico_guincho"] = _yesno(d.get("servico_guincho"))

        # Opcionais
        v["origem_cep"] = normalize_cep(d.get("origem_cep"))
        v["origem_endereco"] = _clean(d.get("origem_endereco")) or None
        v["origem_bairro"] = _clean(d.get("origem_bairro")) or None
        v["destino_cep"] = normalize_cep(d.get("destino_cep"))
        v["destino_endereco"] = _clean(d.get("destino_endereco")) or None
        v["destino_bairro"] = _clean(d.get("destino_bairro")) or None
        v["descricao_material"] = _clean(d.get("descricao_material")) or None
        v["observacoes"] = _clean(d.get("observacoes")) or None

        return not self.errors


@dataclass
class ProposalForm:
    """Valida a proposta lancada pelo comercial."""

    data: dict[str, Any]
    valor_nf: Decimal
    errors: dict[str, str] = field(default_factory=dict)
    values: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> bool:
        d = self.data
        v = self.values

        v["frete"] = parse_brl(d.get("frete"))
        if v["frete"] is None or v["frete"] < 0:
            self.errors["frete"] = "Informe o valor do frete."

        v["pedagio"] = parse_brl(d.get("pedagio")) or Decimal("0.00")
        if v["pedagio"] < 0:
            self.errors["pedagio"] = "Valor invalido."

        seguro = parse_brl(d.get("seguro"))
        v["seguro"] = seguro if seguro is not None else calc_seguro(self.valor_nf)
        if v["seguro"] < 0:
            self.errors["seguro"] = "Valor invalido."

        v["custos_adicionais"] = parse_brl(d.get("custos_adicionais")) or Decimal("0.00")
        if v["custos_adicionais"] < 0:
            self.errors["custos_adicionais"] = "Valor invalido."
        v["custos_adicionais_desc"] = _clean(d.get("custos_adicionais_desc")) or None
        if v["custos_adicionais"] > 0 and not v["custos_adicionais_desc"]:
            self.errors["custos_adicionais_desc"] = (
                "Descreva o que esta sendo cobrado nos custos adicionais."
            )

        v["prazo_entrega"] = _clean(d.get("prazo_entrega"))
        if not v["prazo_entrega"]:
            self.errors["prazo_entrega"] = "Informe o prazo de entrega."

        raw_validade = _clean(d.get("validade"))
        v["validade"] = None
        if not raw_validade:
            self.errors["validade"] = "Informe a validade da proposta."
        else:
            try:
                v["validade"] = datetime.strptime(raw_validade, "%Y-%m-%d").date()
            except ValueError:
                self.errors["validade"] = "Data invalida."

        v["observacoes"] = _clean(d.get("observacoes")) or OBSERVACAO_PADRAO_PROPOSTA

        if not self.errors:
            v["total"] = v["frete"] + v["pedagio"] + v["seguro"]
            v["valor_final"] = v["total"] + v["custos_adicionais"]

        return not self.errors


def prefill_from_quote(quote) -> dict[str, Any]:
    """Valores para reaproveitar uma cotacao anterior (rota + carga + transporte)."""
    return {
        "origem_cidade": quote.origem_cidade,
        "origem_cep": quote.origem_cep,
        "origem_endereco": quote.origem_endereco,
        "origem_bairro": quote.origem_bairro,
        "destino_cidade": quote.destino_cidade,
        "destino_cep": quote.destino_cep,
        "destino_endereco": quote.destino_endereco,
        "destino_bairro": quote.destino_bairro,
        "tipo_material": quote.tipo_material,
        "descricao_material": quote.descricao_material,
        "qtd_volumes": quote.qtd_volumes,
        "peso_total_kg": quote.peso_total_kg,
        "valor_nf": quote.valor_nf,
        "servico_carga": quote.servico_carga,
        "servico_descarga": quote.servico_descarga,
        "servico_diaria": quote.servico_diaria,
        "servico_guincho": quote.servico_guincho,
        "tipo_veiculo": quote.tipo_veiculo,
        "carroceria": quote.carroceria,
        "capacidade_aprox": quote.capacidade_aprox,
        "observacoes": quote.observacoes,
    }
