"""
Horario Tool - Verificação de horário de funcionamento.
Permite ao agente consultar se o estabelecimento está aberto.
"""
from app.core.langchain_compat import patch_forward_ref_evaluate_for_python312

patch_forward_ref_evaluate_for_python312()

from langchain_core.tools import tool
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.core.database import SessionLocal
from app.models.models import Company


# Fuso horário de Fortaleza (UTC-3)
FORTALEZA_TZ = timezone(timedelta(hours=-3))


@tool
def horario_tool(company_id: str = "") -> str:
    """
    Verifica o horário de funcionamento do estabelecimento e se está aberto agora.
    Use esta ferramenta quando o cliente perguntar sobre horário de funcionamento ou se a loja está aberta.

    Args:
        company_id: ID da empresa (opcional, usa a primeira empresa se não informado)

    Returns:
        Informações sobre horário de funcionamento e status atual.
    """
    db = SessionLocal()
    try:
        # Buscar empresa
        query = db.query(Company)
        if company_id:
            query = query.filter(Company.id == company_id)
        empresa = query.first()

        if not empresa:
            return "Não foi possível encontrar as informações do estabelecimento."

        agora = datetime.now(FORTALEZA_TZ)
        dia_semana = _get_dia_semana(agora.weekday())

        resultado = "🕐 *HORÁRIO DE FUNCIONAMENTO*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        resultado += f"📍 *{empresa.name}*\n\n"

        # Horários por dia
        horarios = {
            "Segunda": "18:00 às 23:00",
            "Terça": "18:00 às 23:00",
            "Quarta": "18:00 às 23:00",
            "Quinta": "18:00 às 23:00",
            "Sexta": "18:00 às 00:00",
            "Sábado": "18:00 às 00:00",
            "Domingo": "18:00 às 23:00",
        }

        for dia, horario in horarios.items():
            marcador = " 👈 Hoje" if dia == dia_semana else ""
            resultado += f"• {dia}: {horario}{marcador}\n"

        # Verificar se está aberto
        hora_atual = agora.hour
        aberto = False

        if dia_semana in ["Sexta", "Sábado"]:
            aberto = 18 <= hora_atual or hora_atual < 0
        else:
            aberto = 18 <= hora_atual < 23

        resultado += f"\n{'🟢 *ABERTO AGORA*' if aberto else '🔴 *FECHADO AGORA*'}\n"

        if not aberto:
            resultado += f"\n⏰ Faltam {_calcular_tempo_para_abrir(agora)} para abrir!"

        resultado += "\n━━━━━━━━━━━━━━━━━━━━"

        # Endereço
        if empresa.address:
            resultado += f"\n📍 Endereço: {empresa.address}"
        if empresa.phone:
            resultado += f"\n📞 Telefone: {empresa.phone}"

        return resultado

    except Exception as e:
        return f"Erro ao consultar horário: {str(e)}"
    finally:
        db.close()


def _get_dia_semana(weekday: int) -> str:
    """Converte weekday number para nome do dia."""
    dias = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
    return dias[weekday]


def _calcular_tempo_para_abrir(agora: datetime) -> str:
    """Calcula quanto tempo falta para abrir."""
    hora_abertura = 18
    if agora.hour < hora_abertura:
        horas = hora_abertura - agora.hour
        minutos = 60 - agora.minute
        return f"{horas}h {minutos}min"
    else:
        horas = 24 - agora.hour + hora_abertura
        minutos = 60 - agora.minute
        return f"{horas}h {minutos}min"
