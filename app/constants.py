"""Opcoes de formulario e estados de cotacao."""

# Status de uma cotacao.
STATUS_ABERTA = "aberta"
STATUS_RESPONDIDA = "respondida"
STATUS_APROVADA = "aprovada"
STATUS_REPROVADA = "reprovada"

STATUS_LABELS = {
    STATUS_ABERTA: "Em analise",
    STATUS_RESPONDIDA: "Respondida",
    STATUS_APROVADA: "Aprovada",
    STATUS_REPROVADA: "Reprovada",
}

# status antigos -> novos, aplicado uma vez na migracao de dados
STATUS_LEGADO = {"aceita": STATUS_APROVADA, "ajuste_solicitado": STATUS_REPROVADA}

# Abas do painel comercial -> filtro de status (None = todas).
ADMIN_TABS = {
    "todas": None,
    "em_analise": (STATUS_ABERTA,),
    "respondidas": (STATUS_RESPONDIDA,),
    "finalizadas": (STATUS_APROVADA, STATUS_REPROVADA),
}

ADMIN_TAB_LABELS = {
    "todas": "Todas",
    "em_analise": "Em analise",
    "respondidas": "Respondidas",
    "finalizadas": "Finalizadas",
}

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
