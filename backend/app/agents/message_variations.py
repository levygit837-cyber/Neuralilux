"""
Message Variations - Banco de variações de mensagens para evitar repetição.

Fornece rotação de frases para tornar as conversas mais naturais
e remover dados mockados estáticos.
"""
import random
from typing import List, Dict, Optional

# Saudações para primeira mensagem (sem histórico)
SAUDACOES_PRIMEIRA_MENSAGEM: List[str] = [
    "Olá! 😊 Posso te mostrar o cardápio ou as categorias disponíveis. Se quiser, já te envio!",
    "Oi! Bem-vindo à Macedos! Pronto pra conhecer nossas delícias? 🍕",
    "Hey! Que bom te ver por aqui! Vamos ver o que temos de bom hoje? ✨",
    "Olá! Macedos na área! Posso te ajudar com o cardápio ou já sabe o que quer? 😊",
    "Bem-vindo! 🎉 Estou aqui pra te ajudar a escolher algo delicioso. O que te interessa?",
    "Oi! Fico feliz em te atender! Quer dar uma olhada no cardápio ou já tem algo em mente?",
]

# Saudações para conversa em andamento (com histórico)
SAUDACOES_COM_HISTORICO: List[str] = [
    "Como posso ajudar você hoje?",
    "O que mais posso fazer por você?",
    "Estou aqui! O que precisa?",
    "Pronto pra continuar?",
    "Por onde vamos seguir?",
]

# Mensagens genéricas de fallback
FALLBACK_GENERICO_COM_HISTORICO: List[str] = [
    "Como posso ajudar? Posso mostrar o cardápio ou verificar pedidos.",
    "Estou à disposição! Cardápio, pedidos ou alguma dúvida?",
    "Pra onde vamos? Posso te ajudar com o menu ou pedidos.",
    "O que você precisa? Estou aqui pra ajudar!",
]

FALLBACK_GENERICO_SEM_HISTORICO: List[str] = [
    "Posso te ajudar com o cardápio, categorias, pedidos e horários. Se quiser, já posso te mostrar o cardápio 😊",
    "Bem-vindo à Macedos! 🍕 Posso mostrar nossas opções, categorias ou ajudar com pedidos. O que prefere?",
    "Oi! Estou aqui pra facilitar seu pedido. Cardápio completo, por categoria ou já sabe o que quer? 😊",
    "Olá! Posso te mostrar tudo que temos ou ir direto ao ponto se já souber o que quer!",
]

# Saudações para cardápio/categorias
SAUDACOES_CATEGORIAS: List[str] = [
    "📋 Temos essas opções disponíveis:",
    "🍽️ Aqui está o que preparamos hoje:",
    "🔥 Dá uma olhada no nosso cardápio:",
    "✨ Separamos essas especialidades pra você:",
    "📋 Confira o que temos:",
]

# Sugestões de próximo passo após mostrar categoria
SUGESTOES_APOS_CATEGORIA: List[str] = [
    "Quer ver algum item de perto?",
    "Algum chamou sua atenção?",
    "Posso te mostrar detalhes de algum?",
    "O que achou? Algum interesse?",
    "Quer saber mais sobre algum desses?",
]

# Sugestões após mostrar resumo de categorias
SUGESTOES_APOS_RESUMO: List[str] = [
    "Qual categoria te interessa?",
    "O que te deu vontade de ver primeiro?",
    "Por onde queremos começar?",
    "Alguma categoria chamou sua atenção?",
    "Me diz o que você procura!",
]

# Sugestões após mostrar todos os itens
SUGESTOES_APOS_TODOS: List[str] = [
    "Se quiser detalhes de algum item, é só me perguntar!",
    "Posso te contar mais sobre qualquer um desses.",
    "Tem algum favorito aí? Posso detalhar!",
    "Quer saber mais sobre alguma opção?",
]

# Sugestões após busca sem resultados
SUGESTOES_BUSCA_VAZIA: List[str] = [
    "Não encontrou o que procura? Posso te mostrar as categorias disponíveis.",
    "Quer tentar outro termo ou ver as categorias primeiro?",
    "Posso te ajudar a encontrar algo similar. Quer ver as categorias?",
]

# Mensagens de erro - variações leves
ERRO_GENERICO: List[str] = [
    "Desculpe, ocorreu um erro ao processar sua mensagem. Por favor, tente novamente. 😊",
    "Ops, algo deu errado aqui. Pode tentar de novo? 🔄",
    "Tivemos um probleminha técnico. Tenta mais uma vez?",
]

ERRO_INFERENCIA: List[str] = [
    "Desculpe, estou com dificuldades para processar sua solicitação no momento. O serviço de IA pode estar indisponível. Por favor, tente novamente em alguns instantes. 🤔",
    "Estou com problemas técnicos no momento. Tenta de novo daqui a pouco? ⏳",
    "Meu sistema de processamento está instável. Pode repetir daqui a pouquinho?",
]

ERRO_TIMEOUT: List[str] = [
    "Desculpe, o serviço de IA está demorando para responder ou está sobrecarregado. Por favor, tente novamente em alguns instantes. ⏳",
    "Está tudo muito lento por aqui. Tenta novamente em alguns segundos?",
    "Demorando mais que o normal... pode tentar de novo daqui a pouco?",
]

ERRO_CONTEXT_LOAD: List[str] = [
    "Desculpe, não consegui carregar o contexto da nossa conversa. Por favor, envie sua mensagem novamente. 🔄",
    "Perdi o fio da conversa aqui. Manda de novo?",
    "Não consegui acessar nosso histórico. Tenta novamente?",
]

ERRO_INTENT_CLASSIFICATION: List[str] = [
    "Desculpe, não consegui entender o que você quer. Poderia reformular sua mensagem? 🤷",
    "Não entendi direito. Pode dizer de outra forma?",
    "Fiquei meio confuso. Pode explicar melhor?",
]

ERRO_RESPONSE_GENERATION: List[str] = [
    "Desculpe, tive um problema ao gerar a resposta. Por favor, tente novamente. 💭",
    "Deu um bug na minha resposta. Manda de novo?",
    "Erro técnico ao responder. Tenta mais uma vez?",
]

ERRO_TOOL_EXECUTION: List[str] = [
    "Desculpe, ocorreu um erro ao executar uma ação necessária. Por favor, tente novamente. ⚙️",
    "Não consegui executar essa ação. Tenta de novo?",
    "Falha técnica na operação. Pode repetir?",
]

ERRO_EVOLUTION_API: List[str] = [
    "Desculpe, estou com problemas de comunicação. Por favor, tente novamente. 📡",
    "Problemas de conexão aqui. Tenta mais uma vez?",
    "Erro de comunicação. Manda de novo daqui a pouco?",
]

# Mensagens específicas do fluxo
MENSAGEM_SEM_COMANDA: List[str] = [
    "Não encontrei uma comanda aberta para finalizar.",
    "Não tem pedido em aberto aqui. Quer começar um?",
    "Sua comanda está vazia. Bora pedir algo?",
]

PEDIDO_VAZIO: List[str] = [
    "🛒 Seu pedido está vazio. Quer ver o cardápio para escolher algo?",
    "Ainda não tem nada no pedido. Quer dar uma olhada no cardápio?",
    "Comanda vazia! Vamos escolher algo gostoso?",
]


def get_variation(variations_list: List[str]) -> str:
    """Retorna uma variação aleatória da lista."""
    return random.choice(variations_list)


def get_saudacao(tem_historico: bool = False) -> str:
    """Retorna saudação apropriada baseada no histórico."""
    if tem_historico:
        return get_variation(SAUDACOES_COM_HISTORICO)
    return get_variation(SAUDACOES_PRIMEIRA_MENSAGEM)


def get_fallback_message(tem_historico: bool = False) -> str:
    """Retorna mensagem de fallback genérica."""
    if tem_historico:
        return get_variation(FALLBACK_GENERICO_COM_HISTORICO)
    return get_variation(FALLBACK_GENERICO_SEM_HISTORICO)


def get_error_message(error_type: str) -> str:
    """Retorna mensagem de erro baseada no tipo."""
    error_variations: Dict[str, List[str]] = {
        "generico": ERRO_GENERICO,
        "inference": ERRO_INFERENCIA,
        "timeout": ERRO_TIMEOUT,
        "context_load": ERRO_CONTEXT_LOAD,
        "intent_classification": ERRO_INTENT_CLASSIFICATION,
        "response_generation": ERRO_RESPONSE_GENERATION,
        "tool_execution": ERRO_TOOL_EXECUTION,
        "evolution_api": ERRO_EVOLUTION_API,
    }
    variations = error_variations.get(error_type, ERRO_GENERICO)
    return get_variation(variations)


def get_cardapio_saudacao() -> str:
    """Retorna saudação para apresentação de cardápio."""
    return get_variation(SAUDACOES_CATEGORIAS)


def get_sugestao_proximo_passo(contexto: str = "apos_categoria") -> str:
    """Retorna sugestão de próximo passo baseada no contexto."""
    suggestions_map: Dict[str, List[str]] = {
        "apos_categoria": SUGESTOES_APOS_CATEGORIA,
        "apos_resumo": SUGESTOES_APOS_RESUMO,
        "apos_todos": SUGESTOES_APOS_TODOS,
        "busca_vazia": SUGESTOES_BUSCA_VAZIA,
    }
    variations = suggestions_map.get(contexto, SUGESTOES_APOS_CATEGORIA)
    return get_variation(variations)


def get_mensagem_sem_comanda() -> str:
    """Retorna mensagem quando não há comanda aberta."""
    return get_variation(MENSAGEM_SEM_COMANDA)


def get_pedido_vazio_message() -> str:
    """Retorna mensagem quando pedido está vazio."""
    return get_variation(PEDIDO_VAZIO)
