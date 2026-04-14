"""
Delivery Zone Service - Gerenciamento de zonas de entrega e taxas.
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.models import DeliveryZone
import structlog

logger = structlog.get_logger()


class DeliveryZoneServiceError(Exception):
    """Exceção base para erros do serviço de zonas de entrega."""
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        self.message = message
        self.context = context or {}
        super().__init__(self.message)


class NeighborhoodNotFoundError(DeliveryZoneServiceError):
    """Lançada quando um bairro não é encontrado em nenhuma zona."""
    pass


class NoActiveZonesError(DeliveryZoneServiceError):
    """Lançada quando não há zonas de entrega ativas."""
    pass


def get_delivery_zone_by_neighborhood(db: Session, neighborhood: str) -> Optional[DeliveryZone]:
    """
    Busca uma zona de entrega pelo nome do bairro.
    
    Args:
        db: Sessão do banco de dados
        neighborhood: Nome do bairro para buscar
        
    Returns:
        DeliveryZone se encontrado, None caso contrário
    """
    try:
        # Buscar todas as zonas ativas
        zones = db.query(DeliveryZone).filter(DeliveryZone.is_active == True).all()
        
        # Normalizar o bairro para busca case-insensitive
        neighborhood_normalized = neighborhood.lower().strip()
        
        for zone in zones:
            if zone.neighborhoods:
                # Verificar se o bairro está na lista de bairros da zona
                for zone_neighborhood in zone.neighborhoods:
                    if isinstance(zone_neighborhood, str):
                        if zone_neighborhood.lower().strip() == neighborhood_normalized:
                            return zone
                    elif isinstance(zone_neighborhood, dict):
                        # Suporte para formato JSON complexo se necessário
                        zone_name = zone_neighborhood.get("name", "")
                        if zone_name.lower().strip() == neighborhood_normalized:
                            return zone
        
        return None
    except Exception as e:
        logger.error(
            "Error searching delivery zone by neighborhood",
            neighborhood=neighborhood,
            error=str(e)
        )
        raise DeliveryZoneServiceError(
            f"Erro ao buscar zona de entrega: {str(e)}",
            context={"neighborhood": neighborhood}
        ) from e


def get_delivery_fee(db: Session, neighborhood: str, order_value: float = 0) -> Dict[str, Any]:
    """
    Calcula a taxa de entrega para um bairro.
    
    Args:
        db: Sessão do banco de dados
        neighborhood: Nome do bairro
        order_value: Valor total do pedido (para verificar valor mínimo)
        
    Returns:
        Dicionário com:
        - fee: valor da taxa de entrega
        - zone_name: nome da zona
        - minimum_order_value: valor mínimo para entrega
        - meets_minimum: se o pedido atinge o valor mínimo
        
    Raises:
        NeighborhoodNotFoundError: Se o bairro não for encontrado
        NoActiveZonesError: Se não houver zonas ativas
    """
    try:
        zone = get_delivery_zone_by_neighborhood(db, neighborhood)
        
        if not zone:
            raise NeighborhoodNotFoundError(
                f"Bairro '{neighborhood}' não encontrado em nenhuma zona de entrega.",
                context={"neighborhood": neighborhood}
            )
        
        delivery_fee = float(zone.delivery_fee or 0)
        minimum_order = float(zone.minimum_order_value or 0)
        meets_minimum = order_value >= minimum_order if minimum_order > 0 else True
        
        return {
            "fee": delivery_fee,
            "zone_name": zone.name,
            "minimum_order_value": minimum_order,
            "meets_minimum": meets_minimum,
            "neighborhood": neighborhood
        }
    except NeighborhoodNotFoundError:
        raise
    except NoActiveZonesError:
        raise
    except Exception as e:
        logger.error(
            "Error calculating delivery fee",
            neighborhood=neighborhood,
            order_value=order_value,
            error=str(e)
        )
        raise DeliveryZoneServiceError(
            f"Erro ao calcular taxa de entrega: {str(e)}",
            context={"neighborhood": neighborhood, "order_value": order_value}
        ) from e


def list_active_zones(db: Session) -> List[Dict[str, Any]]:
    """
    Lista todas as zonas de entrega ativas.
    
    Args:
        db: Sessão do banco de dados
        
    Returns:
        Lista de dicionários com informações das zonas
    """
    try:
        zones = db.query(DeliveryZone).filter(DeliveryZone.is_active == True).all()
        
        if not zones:
            raise NoActiveZonesError(
                "Não há zonas de entrega ativas cadastradas."
            )
        
        return [
            {
                "id": zone.id,
                "name": zone.name,
                "neighborhoods": zone.neighborhoods,
                "delivery_fee": float(zone.delivery_fee or 0),
                "minimum_order_value": float(zone.minimum_order_value or 0)
            }
            for zone in zones
        ]
    except NoActiveZonesError:
        raise
    except Exception as e:
        logger.error("Error listing active delivery zones", error=str(e))
        raise DeliveryZoneServiceError(
            f"Erro ao listar zonas de entrega: {str(e)}"
        ) from e


def get_all_neighborhoods(db: Session) -> List[str]:
    """
    Retorna uma lista de todos os bairros atendidos.
    
    Args:
        db: Sessão do banco de dados
        
    Returns:
        Lista de nomes de bairros
    """
    try:
        zones = db.query(DeliveryZone).filter(DeliveryZone.is_active == True).all()
        
        if not zones:
            return []
        
        neighborhoods = []
        for zone in zones:
            if zone.neighborhoods:
                for neighborhood in zone.neighborhoods:
                    if isinstance(neighborhood, str):
                        neighborhoods.append(neighborhood)
                    elif isinstance(neighborhood, dict):
                        # Suporte para formato JSON complexo
                        neighborhoods.append(neighborhood.get("name", ""))
        
        return sorted(set(neighborhoods))
    except Exception as e:
        logger.error("Error getting all neighborhoods", error=str(e))
        raise DeliveryZoneServiceError(
            f"Erro ao obter lista de bairros: {str(e)}"
        ) from e
