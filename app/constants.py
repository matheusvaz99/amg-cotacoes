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
    STATUS_APROVADA: "Aguardar solicitação de frete",
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
    "Material de construcao",
    "Estrutura metalica",
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
    OPCAO_TIPO_VEICULO: {"titulo": "Tipos de veiculo", "singular": "tipo de veiculo"},
}

TIPOS_VEICULO_PADRAO = [
    "Carreta Sider",
    "Carreta Bau",
    "Carreta Grade Baixa",
    "Truck",
    "Toco",
    "VUC / 3/4",
    "Bitrem",
    "Outro",
]

CARROCERIAS_PADRAO = [
    "Sider",
    "Bau",
    "Grade baixa",
    "Graneleiro",
    "Prancha",
    "Cacamba / basculante",
    "Refrigerada / frigorifica",
    "Plataforma",
    "Bau frigorifico",
    "Cegonha",
]

OPCOES_PADRAO = {
    OPCAO_CARROCERIA: CARROCERIAS_PADRAO,
    OPCAO_TIPO_VEICULO: TIPOS_VEICULO_PADRAO,
}

OBSERVACAO_PADRAO_PROPOSTA = "Valores sujeitos a confirmacao na contratacao."

DISCLAIMERS = [
    "As cotacoes sao estimativas e nao geram reserva de veiculo.",
    "Valores validos conforme o prazo informado na proposta.",
    "A disponibilidade de veiculo e a confirmacao do frete acontecem somente apos aprovacao.",
    "Em caso de informacoes incompletas, o time comercial podera entrar em contato.",
]

SLOGAN = "RAPIDO PARA SOLICITAR. FACIL PARA COTAR. EFICIENTE PARA TODOS."
