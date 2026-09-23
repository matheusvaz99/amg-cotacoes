"""Parsing e validacao dos formularios: cotacao do cliente (rapida/completa),
formacao de preco do comercial, solicitacao de frete e agenda de carregamentos."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.constants import (
    AGENDA_AGUARDANDO,
    AGENDA_STATUS_LABELS,
    OBSERVACAO_PADRAO_PROPOSTA,
    PAGADOR_OPCOES,
    TIPO_COTACAO_COMPLETA,
    TIPO_COTACAO_RAPIDA,
    TIPOS_MATERIAL,
)
from app.utils import (
    normalize_cep,
    parse_brl,
    parse_int,
    utcnow,
)


def _clean(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _yesno(value: Any) -> bool:
    return _clean(value).lower() in {"sim", "true", "1", "on", "yes"}


@dataclass
class QuoteForm:
    """Valida os campos da cotacao. `data` sao os valores brutos do request.form.
    `tipo_cotacao` define quais campos sao obrigatorios (rapida = minimo para uma
    estimativa; completa = tudo)."""

    data: dict[str, Any]
    tipo_cotacao: str = TIPO_COTACAO_COMPLETA
    allowed_carrocerias: list[str] | None = None
    allowed_tipos_veiculo: list[str] | None = None
    errors: dict[str, str] = field(default_factory=dict)
    values: dict[str, Any] = field(default_factory=dict)

    # Obrigatorios em qualquer tipo de cotacao.
    REQUIRED_LABELS = {
        "client_name": "Nome do comprador",
        "client_company": "Empresa que representa",
        "client_cnpj": "CNPJ/CPF da empresa",
        "origem_cidade": "Cidade de origem",
        "destino_cidade": "Cidade de destino",
        "tipo_material": "Tipo de material",
        "peso_total": "Peso total aproximado",
        "data_coleta": "Data prevista para coleta",
    }
    # Obrigatorios so na cotacao completa.
    REQUIRED_LABELS_COMPLETA = {
        "valor_nf": "Valor aproximado da NF",
        "tipo_veiculo": "Tipo de veículo desejado",
        "carroceria": "Carroceria",
        "capacidade_aprox": "Capacidade aproximada",
    }

    def _is_completa(self) -> bool:
        return self.tipo_cotacao != TIPO_COTACAO_RAPIDA

    def validate(self) -> bool:
        d = self.data
        v = self.values
        completa = self._is_completa()
        v["tipo_cotacao"] = TIPO_COTACAO_COMPLETA if completa else TIPO_COTACAO_RAPIDA

        # Texto simples sempre obrigatorio
        for key in ("client_name", "client_company", "client_cnpj", "origem_cidade", "destino_cidade"):
            v[key] = _clean(d.get(key))
            if not v[key]:
                self.errors[key] = f"{self.REQUIRED_LABELS[key]} é obrigatório."

        # Capacidade aproximada: obrigatoria so na completa
        v["capacidade_aprox"] = _clean(d.get("capacidade_aprox")) or None
        if completa and not v["capacidade_aprox"]:
            self.errors["capacidade_aprox"] = f"{self.REQUIRED_LABELS_COMPLETA['capacidade_aprox']} é obrigatório."

        # E-mail: opcional -- se informado, precisa ser valido
        v["client_email"] = _clean(d.get("client_email")).lower() or None
        if v["client_email"] and (
            "@" not in v["client_email"] or "." not in v["client_email"].split("@")[-1]
        ):
            self.errors["client_email"] = "Informe um e-mail válido."

        v["client_phone"] = _clean(d.get("client_phone")) or None

        # Tipo de material: sempre obrigatorio
        v["tipo_material"] = _clean(d.get("tipo_material"))
        if not v["tipo_material"]:
            self.errors["tipo_material"] = "Selecione o tipo de material."
        elif v["tipo_material"] not in TIPOS_MATERIAL:
            self.errors["tipo_material"] = "Opção inválida."

        # Tipo de veiculo / carroceria: obrigatorios so na completa; "nao sei" na rapida
        v["tipo_veiculo"] = _clean(d.get("tipo_veiculo")) or None
        if completa:
            if not v["tipo_veiculo"]:
                self.errors["tipo_veiculo"] = "Selecione o tipo de veículo."
            elif self.allowed_tipos_veiculo is not None and v["tipo_veiculo"] not in self.allowed_tipos_veiculo:
                self.errors["tipo_veiculo"] = "Opção inválida."
        elif v["tipo_veiculo"] and self.allowed_tipos_veiculo is not None and v["tipo_veiculo"] not in self.allowed_tipos_veiculo:
            self.errors["tipo_veiculo"] = "Opção inválida."

        v["carroceria"] = _clean(d.get("carroceria")) or None
        if completa:
            if not v["carroceria"]:
                self.errors["carroceria"] = "Selecione a carroceria."
            elif self.allowed_carrocerias is not None and v["carroceria"] not in self.allowed_carrocerias:
                self.errors["carroceria"] = "Opção inválida."
        elif v["carroceria"] and self.allowed_carrocerias is not None and v["carroceria"] not in self.allowed_carrocerias:
            self.errors["carroceria"] = "Opção inválida."

        # Quantidade de volumes: sempre opcional
        v["qtd_volumes"] = parse_int(d.get("qtd_volumes"))
        if v["qtd_volumes"] is not None and v["qtd_volumes"] <= 0:
            self.errors["qtd_volumes"] = "A quantidade deve ser maior que zero."

        # Peso: sempre obrigatorio (rapida e completa) -- texto livre, o
        # proprio cliente informa a unidade (kg ou toneladas).
        v["peso_total"] = _clean(d.get("peso_total"))
        if not v["peso_total"]:
            self.errors["peso_total"] = "Informe o peso total aproximado (kg ou toneladas)."

        # Valor da NF: obrigatorio so na completa
        v["valor_nf"] = parse_brl(d.get("valor_nf"))
        if completa and v["valor_nf"] is None:
            self.errors["valor_nf"] = "Informe o valor aproximado da NF."
        elif v["valor_nf"] is not None and v["valor_nf"] < 0:
            self.errors["valor_nf"] = "Valor inválido."

        # Data de coleta (obrigatoria)
        raw_date = _clean(d.get("data_coleta"))
        v["data_coleta"] = None
        if not raw_date:
            self.errors["data_coleta"] = "Informe a data prevista para coleta."
        else:
            try:
                parsed = datetime.strptime(raw_date, "%Y-%m-%d").date()
                if parsed < utcnow().date():
                    self.errors["data_coleta"] = "A data não pode estar no passado."
                else:
                    v["data_coleta"] = parsed
            except ValueError:
                self.errors["data_coleta"] = "Data inválida."

        # Data de entrega (opcional)
        raw_entrega = _clean(d.get("data_entrega"))
        v["data_entrega"] = None
        if raw_entrega:
            try:
                entrega = datetime.strptime(raw_entrega, "%Y-%m-%d").date()
                if v["data_coleta"] and entrega < v["data_coleta"]:
                    self.errors["data_entrega"] = "A data de entrega não pode ser antes da coleta."
                else:
                    v["data_entrega"] = entrega
            except ValueError:
                self.errors["data_entrega"] = "Data inválida."

        # Sim/Nao (default Nao) — servicos que o cliente pode precisar
        v["servico_diaria"] = _yesno(d.get("servico_diaria"))
        v["servico_guincho"] = _yesno(d.get("servico_guincho"))
        v["servico_ajudante"] = _yesno(d.get("servico_ajudante"))
        v["servico_empilhadeira"] = _yesno(d.get("servico_empilhadeira"))
        v["ajudante_qtd"] = parse_int(d.get("ajudante_qtd"))

        # Opcionais
        v["origem_cep"] = normalize_cep(d.get("origem_cep"))
        v["origem_endereco"] = _clean(d.get("origem_endereco")) or None
        v["origem_bairro"] = _clean(d.get("origem_bairro")) or None
        v["destino_cep"] = normalize_cep(d.get("destino_cep"))
        v["destino_endereco"] = _clean(d.get("destino_endereco")) or None
        v["destino_bairro"] = _clean(d.get("destino_bairro")) or None
        v["descricao_material"] = _clean(d.get("descricao_material")) or None
        v["dimensoes"] = _clean(d.get("dimensoes")) or None
        v["observacoes"] = _clean(d.get("observacoes")) or None

        return not self.errors


@dataclass
class ProposalForm:
    """Valida a formacao de preco do comercial: FC (custos internos) -> margem
    -> FE, mais os adicionais precificaveis. FC/FE/valor_final sao sempre
    recalculados no servidor, nunca confiando no que o JS mostrou."""

    data: dict[str, Any]
    errors: dict[str, str] = field(default_factory=dict)
    values: dict[str, Any] = field(default_factory=dict)

    CUSTO_FIELDS = [
        "custo_motorista",
        "custo_pedagio",
        "custo_impostos",
        "custo_seguro",
        "custo_outros_internos",
    ]
    ADICIONAL_FIELDS = [
        "valor_diaria",
        "valor_ajudante",
        "valor_empilhadeira",
        "valor_guincho",
    ]

    def validate(self) -> bool:
        d = self.data
        v = self.values

        for campo in self.CUSTO_FIELDS:
            valor = parse_brl(d.get(campo)) or Decimal("0.00")
            if valor < 0:
                self.errors[campo] = "Valor inválido."
            v[campo] = valor
        v["fc"] = sum((v[c] for c in self.CUSTO_FIELDS), Decimal("0.00"))

        margem = parse_brl(d.get("margem_pct"))
        v["margem_pct"] = margem if margem is not None else Decimal("0.00")
        if v["margem_pct"] < 0:
            self.errors["margem_pct"] = "Valor inválido."
        v["fe"] = (v["fc"] * (Decimal("1") + v["margem_pct"] / Decimal("100"))).quantize(
            Decimal("0.01")
        )

        for campo in self.ADICIONAL_FIELDS:
            valor = parse_brl(d.get(campo)) or Decimal("0.00")
            if valor < 0:
                self.errors[campo] = "Valor inválido."
            v[campo] = valor

        v["custos_adicionais"] = parse_brl(d.get("custos_adicionais")) or Decimal("0.00")
        if v["custos_adicionais"] < 0:
            self.errors["custos_adicionais"] = "Valor inválido."
        v["custos_adicionais_desc"] = _clean(d.get("custos_adicionais_desc")) or None
        if v["custos_adicionais"] > 0 and not v["custos_adicionais_desc"]:
            self.errors["custos_adicionais_desc"] = "Descreva o que está sendo cobrado em Outros."

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
                self.errors["validade"] = "Data inválida."

        v["observacoes"] = _clean(d.get("observacoes")) or OBSERVACAO_PADRAO_PROPOSTA

        if not self.errors:
            adicionais_total = sum((v[c] for c in self.ADICIONAL_FIELDS), Decimal("0.00"))
            adicionais_total += v["custos_adicionais"]
            v["valor_final"] = v["fe"] + adicionais_total

        return not self.errors


@dataclass
class SolicitacaoFreteForm:
    """Dados operacionais/fiscais da Solicitacao de Frete, preenchidos pelo
    cliente apos a cotacao ser aprovada."""

    data: dict[str, Any]
    errors: dict[str, str] = field(default_factory=dict)
    values: dict[str, Any] = field(default_factory=dict)

    REQUIRED_LABELS = {
        "pagador": "Pagador do frete",
        "pagador_documento": "CNPJ/CPF do pagador",
        "fornecedor_nome": "Fornecedor / remetente",
        "destinatario_nome": "Destinatário",
    }

    def validate(self) -> bool:
        d = self.data
        v = self.values
        for key in self.REQUIRED_LABELS:
            v[key] = _clean(d.get(key))
            if not v[key]:
                self.errors[key] = f"{self.REQUIRED_LABELS[key]} é obrigatório."

        if v.get("pagador") and v["pagador"] not in PAGADOR_OPCOES:
            self.errors["pagador"] = "Opção inválida."

        v["fornecedor_contato"] = _clean(d.get("fornecedor_contato")) or None
        v["destinatario_contato"] = _clean(d.get("destinatario_contato")) or None

        v["valor_nf"] = parse_brl(d.get("valor_nf"))
        if v["valor_nf"] is not None and v["valor_nf"] < 0:
            self.errors["valor_nf"] = "Valor inválido."

        v["observacoes_operacionais"] = _clean(d.get("observacoes_operacionais")) or None

        return not self.errors


@dataclass
class AgendaForm:
    """Atualizacao de um item da Agenda de Carregamentos (status, confirmacao,
    reagendamento)."""

    data: dict[str, Any]
    errors: dict[str, str] = field(default_factory=dict)
    values: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> bool:
        d = self.data
        v = self.values

        raw_data = _clean(d.get("data_carregamento"))
        v["data_carregamento"] = None
        if not raw_data:
            self.errors["data_carregamento"] = "Informe a data do carregamento."
        else:
            try:
                v["data_carregamento"] = datetime.strptime(raw_data, "%Y-%m-%d").date()
            except ValueError:
                self.errors["data_carregamento"] = "Data inválida."

        v["hora_prevista"] = _clean(d.get("hora_prevista")) or None
        v["responsavel_logistica"] = _clean(d.get("responsavel_logistica")) or None

        v["status_agenda"] = _clean(d.get("status_agenda")) or AGENDA_AGUARDANDO
        if v["status_agenda"] not in AGENDA_STATUS_LABELS:
            self.errors["status_agenda"] = "Status inválido."

        v["confirmado"] = _yesno(d.get("confirmado"))
        v["observacoes"] = _clean(d.get("observacoes")) or None

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
        "dimensoes": quote.dimensoes,
        "qtd_volumes": quote.qtd_volumes,
        "peso_total": quote.peso_total,
        "valor_nf": quote.valor_nf,
        "servico_diaria": quote.servico_diaria,
        "servico_guincho": quote.servico_guincho,
        "servico_ajudante": quote.servico_ajudante,
        "servico_empilhadeira": quote.servico_empilhadeira,
        "ajudante_qtd": quote.ajudante_qtd,
        "tipo_veiculo": quote.tipo_veiculo,
        "carroceria": quote.carroceria,
        "capacidade_aprox": quote.capacidade_aprox,
        "data_entrega": quote.data_entrega.isoformat() if quote.data_entrega else None,
        "observacoes": quote.observacoes,
    }


def prefill_from_quote_for_solicitacao(quote) -> dict[str, Any]:
    """Sugestao inicial da Solicitacao de Frete a partir da propria cotacao
    (destinatario/fornecedor nao existem na cotacao, ficam em branco)."""
    return {"valor_nf": quote.valor_nf}
