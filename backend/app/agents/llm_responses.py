"""
LLM Responses - Wrappers para geração de respostas com retry e fallback.

Fornece funções para gerar respostas via LLM com:
- Retry automático com LLM alternativo
- Fallback para variações de banco
- Tracking de métricas
"""
import structlog
from typing import Optional, Dict, Any, List
import asyncio

from app.services.inference_service import get_inference_service_with_fallback
from app.agents.exceptions import (
    InferenceError,
)
from app.agents.message_variations import (
    get_saudacao,
    get_fallback_message,
    get_error_message,
    get_cardapio_saudacao,
    get_sugestao_proximo_passo,
)

logger = structlog.get_logger()

# Prompts para geração LLM
SAUDACAO_LLM_PROMPT = """Você é Macedinho, atendente virtual da Macedos no WhatsApp.

Gere uma saudação única e natural, variando do padrão.

Contexto: {"tem_historico": {tem_historico}}
Restrições:
- Máximo 2 frases curtas
- Tom amigável, proativo, natural (não robótico)
- Emoji opcional (não obrigatório)
- NÃO mencione "sistema", "IA", "modelo", "tecnologia"
- NÃO use exatamente estas frases: "Posso te mostrar o cardápio", "bem-vindo", "na área"

Gere algo fresco e diferente agora:"""

FALLBACK_LLM_PROMPT = """Você é Macedinho da Macedos. O cliente enviou uma mensagem que não entendi bem.

Mensagem do cliente: {mensagem}
Intenção detectada: {intent}
Tem histórico: {tem_historico}

Gere uma resposta gentil pedindo para o cliente reformular ou oferecendo ajuda com:
- Cardápio/categorias
- Fazer pedido
- Ver comanda
- Horários

Restrições:
- 1-2 frases curtas
- NÃO saudar se já houver histórico
- Ofereça opções concretas
- Tom natural e humano"""


async def _try_llm_with_service(
    service_name: str,
    prompt: str,
    max_tokens: int = 100,
    temperature: float = 0.3,
) -> Optional[str]:
    """Tenta gerar resposta com um serviço LLM específico."""
    try:
        inference_service = get_inference_service_with_fallback(service_name)
        result = await inference_service.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        content = result.get("content", "").strip()
        if content:
            logger.info(
                "LLM response generated",
                service=service_name,
                response_length=len(content),
            )
            return content
    except Exception as e:
        logger.warning(
            "LLM service failed",
            service=service_name,
            error=str(e),
        )
    return None


async def generate_saudacao_with_fallback(
    tem_historico: bool = False,
    max_retries: int = 2,
) -> str:
    """
    Gera saudação via LLM com retry e fallback para variações.
    
    Estratégia:
    1. Tenta LLM primário (Gemini)
    2. Tenta LLM alternativo (Vertex)
    3. Fallback para variações de banco
    
    Args:
        tem_historico: Se há histórico de conversa
        max_retries: Número de retries por serviço
        
    Returns:
        String com saudação
    """
    prompt = SAUDACAO_LLM_PROMPT.format(tem_historico=tem_historico)
    
    # Tentar serviços com retry
    for attempt in range(max_retries):
        # Tentar Gemini
        result = await _try_llm_with_service("whatsapp_agent", prompt)
        if result:
            logger.info(
                "Saudacao gerada via LLM",
                source="llm_gemini",
                tem_historico=tem_historico,
            )
            return result
        
        # Tentar Vertex como alternativo
        try:
            result = await _try_llm_with_service("vertex_agent", prompt)
            if result:
                logger.info(
                    "Saudacao gerada via LLM alternativo",
                    source="llm_vertex",
                    tem_historico=tem_historico,
                )
                return result
        except Exception:
            pass
        
        if attempt < max_retries - 1:
            await asyncio.sleep(0.1 * (attempt + 1))  # Backoff incremental
    
    # Fallback para variações de banco
    logger.info(
        "Saudacao usando variacoes de banco",
        source="variations",
        tem_historico=tem_historico,
    )
    return get_saudacao(tem_historico)


async def generate_fallback_response_with_fallback(
    mensagem: str,
    intent: str,
    tem_historico: bool = False,
    max_retries: int = 2,
) -> str:
    """
    Gera resposta de fallback via LLM com retry.
    
    Args:
        mensagem: Mensagem do cliente
        intent: Intenção detectada
        tem_historico: Se há histórico de conversa
        max_retries: Número de retries
        
    Returns:
        String com resposta de fallback
    """
    prompt = FALLBACK_LLM_PROMPT.format(
        mensagem=mensagem,
        intent=intent,
        tem_historico=tem_historico,
    )
    
    # Tentar LLM
    for attempt in range(max_retries):
        result = await _try_llm_with_service("whatsapp_agent", prompt, max_tokens=80)
        if result:
            logger.info(
                "Fallback gerado via LLM",
                source="llm",
                intent=intent,
            )
            return result
        
        if attempt < max_retries - 1:
            await asyncio.sleep(0.1)
    
    # Fallback para variações
    logger.info(
        "Fallback usando variacoes de banco",
        source="variations",
        intent=intent,
    )
    return get_fallback_message(tem_historico)


def get_error_message_with_tracking(error_type: str) -> str:
    """
    Retorna mensagem de erro com tracking de métricas.
    
    Args:
        error_type: Tipo do erro
        
    Returns:
        String com mensagem de erro
    """
    logger.info(
        "Error message requested",
        error_type=error_type,
        source="variations",
    )
    return get_error_message(error_type)


def get_cardapio_context_with_variations(
    base_data: str,
    contexto: str = "apos_categoria",
) -> str:
    """
    Monta contexto de cardápio com variações de sugestão.
    
    Args:
        base_data: Dados estruturados do cardápio
        contexto: Contexto da sugestão (apos_categoria, apos_resumo, etc)
        
    Returns:
        String formatada com dados + sugestão variada
    """
    sugestao = get_sugestao_proximo_passo(contexto)
    return f"{base_data}\n\n💡 {sugestao}"


async def generate_horario_response_with_fallback(
    company_data: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Gera resposta de horário via LLM ou fallback.
    
    Args:
        company_data: Dados da empresa (opcional)
        
    Returns:
        String com informações de horário
    """
    if company_data:
        prompt = f"""Você é Macedinho da Macedos.

Informações do estabelecimento:
- Nome: {company_data.get('name', 'Macedos')}
- Horário: {company_data.get('hours', 'Seg-Sáb 18h-23h, Dom 18h-23h')}
- Status agora: {company_data.get('status', 'verificar')}

Gere uma mensagem amigável sobre horário de funcionamento.
Restrições:
- Use emoji 🕐 no início
- Máximo 2 frases
- Natural, não robótico"""
        
        result = await _try_llm_with_service("whatsapp_agent", prompt, max_tokens=60)
        if result:
            return result
    
    # Fallback: chamar a ferramenta real
    from app.agents.tools.horario_tool import horario_tool
    try:
        return horario_tool.invoke({})
    except Exception as e:
        logger.error("Horario tool failed", error=str(e))
        return "🕐 Estamos de segunda a domingo, das 18h às 23h. Posso te ajudar com mais informações!"
