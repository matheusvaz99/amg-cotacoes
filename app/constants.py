"""Opcoes de formulario e estados de cotacao."""

# Status de uma cotacao — pipeline completo: cotacao -> preco -> decisao ->
# solicitacao de frete -> ordem de coleta -> logistica.
STATUS_EM_ANALISE = "em_analise"
STATUS_RESPONDIDA = "respondida"
STATUS_NEGOCIACAO = "negociacao"
STATUS_APROVADA = "aprovada"
STATUS_REPROVADA = "reprovada"
STATUS_FRETE_SOLICITADO = "frete_solicitado"
STATUS_EM_VALIDACAO = "em_validacao"
STATUS_OC_EMITIDA = "oc_emitida"
STATUS_ENVIADA_LOGISTICA = "enviada_logistica"

STATUS_LABELS = {
    STATUS_EM_ANALISE: "Em análise",
    STATUS_RESPONDIDA: "Respondida",
    STATUS_NEGOCIACAO: "Negociação",
    STATUS_APROVADA: "Aprovada",
    STATUS_REPROVADA: "Reprovada",
    STATUS_FRETE_SOLICITADO: "Frete solicitado",
    STATUS_EM_VALIDACAO: "Em validação",
    STATUS_OC_EMITIDA: "OC emitida",
    STATUS_ENVIADA_LOGISTICA: "Enviada à Logística",
}

# "Próxima ação" sugerida na fila do painel, conforme a planilha de escopo.
PROXIMA_ACAO = {
    STATUS_EM_ANALISE: "Formar preço",
    STATUS_RESPONDIDA: "Aguardar cliente",
    STATUS_NEGOCIACAO: "Revisar FE",
    STATUS_APROVADA: "Gerar Ordem de Coleta",
    STATUS_REPROVADA: "Encerrado",
    STATUS_FRETE_SOLICITADO: "Validar solicitação",
    STATUS_EM_VALIDACAO: "Validar solicitação",
    STATUS_OC_EMITIDA: "Enviar à Logística",
    STATUS_ENVIADA_LOGISTICA: "Acompanhar na agenda",
}

# status antigos -> novos, aplicado uma vez na migracao de dados
STATUS_LEGADO = {
    "aberta": STATUS_EM_ANALISE,
    "aceita": STATUS_APROVADA,
    "ajuste_solicitado": STATUS_REPROVADA,
}

# nomes de opcoes (carroceria/tipo_veiculo) semeados sem acentuacao antes da
# correcao ortografica -> forma correta. Corrige as linhas ja existentes na
# tabela `opcoes` em producao (o seed inicial so roda uma vez, entao mudar
# OPCOES_PADRAO sozinho nao alcanca quem ja foi semeado). Chaves sao os
# valores literais de categoria ("carroceria"/"tipo_veiculo"), nao as
# constantes OPCAO_* -- elas ainda nao existem nesse ponto do arquivo.
OPCOES_ORTOGRAFIA_LEGADO = {
    "tipo_veiculo": {
        "Carreta Bau": "Carreta Baú",
    },
    "carroceria": {
        "Bau": "Baú",
        "Cacamba / basculante": "Caçamba / basculante",
        "Refrigerada / frigorifica": "Refrigerada / frigorífica",
        "Bau frigorifico": "Baú frigorífico",
    },
}

# Abas do painel comercial -> filtro de status (None = todas).
ADMIN_TABS = {
    "todas": None,
    "em_analise": (STATUS_EM_ANALISE,),
    "negociacao": (STATUS_NEGOCIACAO,),
    "respondidas": (STATUS_RESPONDIDA,),
    "finalizadas": (STATUS_APROVADA, STATUS_REPROVADA),
    "solicitacao": (STATUS_FRETE_SOLICITADO, STATUS_EM_VALIDACAO),
    "logistica": (STATUS_OC_EMITIDA, STATUS_ENVIADA_LOGISTICA),
}

ADMIN_TAB_LABELS = {
    "todas": "Todas",
    "em_analise": "Em análise",
    "negociacao": "Negociação",
    "respondidas": "Respondidas",
    "finalizadas": "Finalizadas",
    "solicitacao": "Solicitação de frete",
    "logistica": "Logística",
}

# Tipo de cotacao: define quais campos sao obrigatorios no formulario.
TIPO_COTACAO_RAPIDA = "rapida"
TIPO_COTACAO_COMPLETA = "completa"
TIPOS_COTACAO_LABELS = {
    TIPO_COTACAO_RAPIDA: "Cotação Rápida",
    TIPO_COTACAO_COMPLETA: "Cotação Completa",
}

# Status da Solicitacao de Frete (app.models.SolicitacaoFrete.status)
SOLICITACAO_ENVIADA = "enviada"
SOLICITACAO_VALIDADA = "validada"
SOLICITACAO_PENDENTE = "pendente_correcao"

PAGADOR_OPCOES = ["Remetente", "Destinatário", "Terceiro"]

# Status da Agenda de Carregamentos (app.models.AgendaCarregamento.status_agenda)
AGENDA_AGUARDANDO = "aguardando_confirmacao"
AGENDA_PROGRAMADO = "programado"
AGENDA_CONFIRMADO = "confirmado"
AGENDA_REAGENDADO = "reagendado"
AGENDA_CARREGADO = "carregado"
AGENDA_CANCELADO = "cancelado"

AGENDA_STATUS_LABELS = {
    AGENDA_AGUARDANDO: "Aguardando confirmação",
    AGENDA_PROGRAMADO: "Programado",
    AGENDA_CONFIRMADO: "Confirmado",
    AGENDA_REAGENDADO: "Reagendado",
    AGENDA_CARREGADO: "Carregado",
    AGENDA_CANCELADO: "Cancelado",
}

# Alertas de prazo da agenda (calculados a partir da data de carregamento).
ALERTA_HOJE = "HOJE"
ALERTA_AMANHA = "AMANHÃ"
ALERTA_PROXIMO = "PRÓXIMO"
ALERTA_ATRASADO = "ATRASADO"

TIPOS_MATERIAL = [
    "Andaime",
    "Escoramento",
    "Forma / painel",
    "Equipamento",
    "Material de construção",
    "Estrutura metálica",
    "Outro",
]

# Carrocerias e tipos de veiculo oferecidos ao cliente. A lista definitiva de
# cada categoria vive no banco (tabela `opcoes`, gerenciada pelo painel em
# /admin/opcoes/<categoria>). As listas abaixo sao apenas a carga inicial
# criada automaticamente quando uma categoria ainda nao tem opcoes.
OPCAO_CARROCERIA = "carroceria"
OPCAO_TIPO_VEICULO = "tipo_veiculo"

OPCOES_CATEGORIAS = {
    OPCAO_CARROCERIA: {"titulo": "Carrocerias", "singular": "carroceria"},
    OPCAO_TIPO_VEICULO: {"titulo": "Tipos de veículo", "singular": "tipo de veículo"},
}

TIPOS_VEICULO_PADRAO = [
    "Carreta Sider",
    "Carreta Baú",
    "Carreta Grade Baixa",
    "Truck",
    "Toco",
    "VUC / 3/4",
    "Bitrem",
    "Outro",
]

CARROCERIAS_PADRAO = [
    "Sider",
    "Baú",
    "Grade baixa",
    "Graneleiro",
    "Prancha",
    "Caçamba / basculante",
    "Refrigerada / frigorífica",
    "Plataforma",
    "Baú frigorífico",
    "Cegonha",
]

OPCOES_PADRAO = {
    OPCAO_CARROCERIA: CARROCERIAS_PADRAO,
    OPCAO_TIPO_VEICULO: TIPOS_VEICULO_PADRAO,
}

OBSERVACAO_PADRAO_PROPOSTA = "Valores sujeitos a confirmação na contratação."

DISCLAIMERS = [
    "As cotações são estimativas e não geram reserva de veículo.",
    "Valores válidos conforme o prazo informado na proposta.",
    "A disponibilidade de veículo e a confirmação do frete acontecem somente após aprovação.",
    "Em caso de informações incompletas, o time comercial poderá entrar em contato.",
]

# Condicoes comerciais padrao, exibidas ao final de cada cotacao com
# proposta (site do cliente + PDF) -- texto conforme modelo de cotacao
# fornecido pelo cliente, a partir de "Obrigatoria apresentacao da nota
# fiscal...". Nao entra no rodape geral do site (DISCLAIMERS), so nas
# telas/documentos da propria cotacao.
TERMOS_COTACAO = [
    "Obrigatória apresentação da nota fiscal no momento do embarque para fins de seguro da carga.",
    "Inclusos: impostos, pedágios e seguros. Condição de pagamento: 28 dias no boleto bancário.",
    "**Não inclusos serviços de carga e descarga, sendo de inteira responsabilidade do contratante do frete o correto armazenamento do material no veículo.",
    "**Não incluso serviço de conferência.",
    "**Não incluso diária (se necessário, avisar a transportadora).",
    "**Caso ocorra cancelamento da carga sem prévio aviso, será cobrado valor de deslocamento acordado à parte (verificar valor junto ao comercial).",
    "**Valores sujeitos a alterações devido a aumento do diesel/pedágios, etc.",
    "**Validade da proposta: 10 dias.",
]

SLOGAN = "RÁPIDO PARA SOLICITAR. FÁCIL PARA COTAR. EFICIENTE PARA TODOS."
