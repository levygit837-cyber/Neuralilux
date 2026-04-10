"""
Endpoints para inferência e modelos do LM Studio.
"""
import httpx
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
import structlog

from app.core.config import settings

logger = structlog.get_logger()
router = APIRouter()


class ModelInfo(BaseModel):
    """Informações sobre um modelo disponível."""
    id: str
    name: str
    provider: str = "lm_studio"
    max_tokens: Optional[int] = None
    context_window: Optional[int] = None


class ModelsResponse(BaseModel):
    """Resposta com lista de modelos disponíveis."""
    models: List[ModelInfo]
    count: int
    source: str = "lm_studio"
    error: Optional[str] = None


class ModelStatusResponse(BaseModel):
    """Status de conectividade com LM Studio."""
    connected: bool
    url: str
    error: Optional[str] = None
    latency_ms: Optional[float] = None


@router.get("/models", response_model=ModelsResponse)
async def list_models() -> ModelsResponse:
    """
    Lista os modelos disponíveis no LM Studio.
    
    Consulta o endpoint /v1/models do LM Studio e retorna
    a lista de modelos carregados e disponíveis para inferência.
    
    Returns:
        ModelsResponse com lista de modelos ou erro se LM Studio não estiver disponível
    """
    lm_studio_url = settings.LM_STUDIO_URL.rstrip("/")
    models_url = f"{lm_studio_url}/v1/models"
    
    logger.info(
        "Fetching models from LM Studio",
        url=models_url,
    )
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(models_url)
            
            if response.status_code != 200:
                logger.warning(
                    "LM Studio models endpoint returned error",
                    status_code=response.status_code,
                    response=response.text[:200],
                )
                return ModelsResponse(
                    models=[],
                    count=0,
                    error=f"LM Studio returned status {response.status_code}",
                )
            
            data = response.json()
            models_data = data.get("data", [])
            
            models: List[ModelInfo] = []
            for model in models_data:
                model_id = model.get("id", "unknown")
                
                # Extrair informações adicionais se disponíveis
                model_info = model.get("info", {})
                max_tokens = model_info.get("max_tokens")
                context_window = model_info.get("context_window")
                
                # Usar id como name se não houver um nome mais amigável
                name = model_id
                if "/" in model_id:
                    # Extrair nome do formato "owner/model"
                    name = model_id.split("/")[-1]
                
                models.append(ModelInfo(
                    id=model_id,
                    name=name,
                    provider="lm_studio",
                    max_tokens=max_tokens,
                    context_window=context_window,
                ))
            
            logger.info(
                "Successfully fetched models from LM Studio",
                count=len(models),
            )
            
            return ModelsResponse(
                models=models,
                count=len(models),
            )
            
    except httpx.TimeoutException:
        logger.error("Timeout connecting to LM Studio")
        return ModelsResponse(
            models=[],
            count=0,
            error="Timeout connecting to LM Studio. Is it running?",
        )
    except httpx.ConnectError as e:
        logger.error("Connection error to LM Studio", error=str(e))
        return ModelsResponse(
            models=[],
            count=0,
            error=f"Cannot connect to LM Studio at {lm_studio_url}. Is it running?",
        )
    except Exception as e:
        logger.error("Error fetching models from LM Studio", error=str(e))
        return ModelsResponse(
            models=[],
            count=0,
            error=f"Error: {str(e)}",
        )


@router.get("/models/status", response_model=ModelStatusResponse)
async def get_model_status() -> ModelStatusResponse:
    """
    Verifica o status de conectividade com o LM Studio.
    
    Faz uma requisição simples para verificar se o LM Studio
    está acessível e respondendo.
    
    Returns:
        ModelStatusResponse com informações de conectividade
    """
    import time
    
    lm_studio_url = settings.LM_STUDIO_URL.rstrip("/")
    models_url = f"{lm_studio_url}/v1/models"
    
    start_time = time.time()
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(models_url)
            latency_ms = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                return ModelStatusResponse(
                    connected=True,
                    url=lm_studio_url,
                    latency_ms=round(latency_ms, 2),
                )
            else:
                return ModelStatusResponse(
                    connected=False,
                    url=lm_studio_url,
                    error=f"HTTP {response.status_code}",
                    latency_ms=round(latency_ms, 2),
                )
                
    except httpx.TimeoutException:
        return ModelStatusResponse(
            connected=False,
            url=lm_studio_url,
            error="Timeout - LM Studio não respondeu em 5s",
        )
    except httpx.ConnectError:
        return ModelStatusResponse(
            connected=False,
            url=lm_studio_url,
            error="Connection refused - LM Studio não está rodando",
        )
    except Exception as e:
        return ModelStatusResponse(
            connected=False,
            url=lm_studio_url,
            error=str(e),
        )


@router.get("/models/current", response_model=ModelInfo)
async def get_current_model() -> ModelInfo:
    """
    Retorna informações sobre o modelo atualmente configurado.
    
    Returns:
        ModelInfo com o modelo definido nas configurações
    """
    model_id = settings.LM_STUDIO_MODEL
    
    # Extrair nome amigável
    name = model_id
    if "/" in model_id:
        name = model_id.split("/")[-1]
    
    return ModelInfo(
        id=model_id,
        name=name,
        provider="lm_studio",
        max_tokens=settings.LM_STUDIO_MAX_TOKENS,
    )
