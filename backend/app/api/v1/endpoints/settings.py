"""
Settings API - Endpoints para configurações do sistema.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Literal
import structlog

from app.core.config import settings

logger = structlog.get_logger()

router = APIRouter()


# Request/Response Models
class InferenceConfig(BaseModel):
    """Configuração de provedor de inferência."""
    provider: Literal["gemini", "lm_studio"]
    local_model: Optional[Literal["nemotron", "qwen"]] = "nemotron"
    gemini_api_key: Optional[str] = None
    gemini_model: Optional[str] = "gemini-3.1-flash-preview"
    lm_studio_url: Optional[str] = "http://localhost:1234"


class InferenceConfigResponse(BaseModel):
    """Resposta com configuração atual de inferência."""
    provider: str
    local_model: str
    gemini_api_key_configured: bool
    gemini_model: str
    lm_studio_url: str
    available_providers: list[str]


@router.get("/inference", response_model=InferenceConfigResponse)
async def get_inference_config():
    """
    Retorna a configuração atual de provedor de inferência.
    """
    return InferenceConfigResponse(
        provider=settings.AGENT_INFERENCE_PROVIDER,
        local_model=settings.LM_STUDIO_MODEL,
        gemini_api_key_configured=bool(settings.GEMINI_API_KEY),
        gemini_model=settings.GEMINI_MODEL,
        lm_studio_url=settings.LM_STUDIO_URL,
        available_providers=["gemini", "lm_studio"],
    )


@router.put("/inference")
async def update_inference_config(config: InferenceConfig):
    """
    Atualiza a configuração de provedor de inferência.
    
    Nota: As alterações são aplicadas apenas em memória durante a execução.
    Para persistir as alterações, atualize o arquivo .env manualmente.
    """
    try:
        # Atualizar configurações em memória
        settings.AGENT_INFERENCE_PROVIDER = config.provider
        
        if config.local_model:
            settings.LM_STUDIO_MODEL = config.local_model
            
        if config.gemini_api_key:
            settings.GEMINI_API_KEY = config.gemini_api_key
            
        if config.gemini_model:
            settings.GEMINI_MODEL = config.gemini_model
            
        if config.lm_studio_url:
            settings.LM_STUDIO_URL = config.lm_studio_url
        
        # Reinicializar o serviço de inferência globalmente
        import app.services.inference_service as inference_module
        inference_module.inference_service = inference_module.get_inference_service()
        
        # Verificar qual serviço foi selecionado
        selected_service = inference_module.inference_service
        service_type = type(selected_service).__name__
        
        logger.info(
            "Inference config updated",
            provider=config.provider,
            local_model=config.local_model,
            gemini_model=config.gemini_model,
            service_type=service_type,
            lm_studio_url=settings.LM_STUDIO_URL,
        )
        
        return {
            "status": "success",
            "message": "Configuração de inferência atualizada",
            "config": {
                "provider": settings.AGENT_INFERENCE_PROVIDER,
                "local_model": settings.LM_STUDIO_MODEL,
                "gemini_model": settings.GEMINI_MODEL,
                "lm_studio_url": settings.LM_STUDIO_URL,
                "service_type": service_type,
            },
        }
        
    except Exception as e:
        logger.error("Failed to update inference config", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao atualizar configuração: {str(e)}"
        )


@router.get("/models")
async def list_available_models():
    """
    Lista os modelos disponíveis para cada provedor.
    """
    return {
        "lm_studio": {
            "models": [
                {"id": "nemotron", "name": "Nemotron", "description": "NVIDIA Nemotron-3-nano-4b"},
                {"id": "qwen", "name": "Qwen 3.5", "description": "qwen3.5-4b-claude-4.6-opus-reasoning-distilled-v2"},
            ],
            "url": settings.LM_STUDIO_URL,
            "status": "available" if settings.LM_STUDIO_URL else "not_configured",
        },
        "gemini": {
            "models": [
                {"id": "gemini-3.1-flash-preview", "name": "Gemini 3.1 Flash", "description": "Modelo rápido e eficiente"},
                {"id": "gemini-3.1-flash-lite-preview", "name": "Gemini 3.1 Flash Lite", "description": "Modelo mais leve"},
                {"id": "gemini-pro", "name": "Gemini Pro", "description": "Modelo avançado"},
                {"id": "gemini-pro-vision", "name": "Gemini Pro Vision", "description": "Modelo com suporte a imagens"},
            ],
            "api_key_configured": bool(settings.GEMINI_API_KEY),
            "status": "available" if settings.GEMINI_API_KEY else "api_key_required",
        },
    }
