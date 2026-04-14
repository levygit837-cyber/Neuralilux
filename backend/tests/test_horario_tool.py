"""
Testes para a ferramenta de horário de funcionamento (horario_tool).
"""
import pytest
from unittest.mock import MagicMock, patch
from app.agents.tools.horario_tool import horario_tool, _get_dia_semana, _calcular_tempo_para_abrir
from app.models.models import Company
from datetime import datetime, timezone, timedelta


class TestHorarioTool:
    """Testa a ferramenta de horário de funcionamento."""

    def test_horario_tool_without_company_id(self, db):
        """Testa consulta sem company_id (usa primeira empresa)."""
        # Criar empresa de teste
        company = Company(
            name="Test Company",
            address="Rua Teste, 123",
            phone="5511999999999",
            is_active=True
        )
        db.add(company)
        db.commit()
        db.refresh(company)

        # Chamar tool sem company_id
        result = horario_tool.invoke({"company_id": ""})

        assert result is not None
        assert "HORÁRIO DE FUNCIONAMENTO" in result
        assert "Test Company" in result
        assert "Segunda" in result
        assert "ABERTO AGORA" in result or "FECHADO AGORA" in result

        # Cleanup
        db.delete(company)
        db.commit()

    def test_horario_tool_with_company_id(self, db):
        """Testa consulta com company_id específico."""
        company = Company(
            name="Specific Company",
            address="Av. Specific, 456",
            phone="5511888888888",
            is_active=True
        )
        db.add(company)
        db.commit()
        db.refresh(company)

        result = horario_tool.invoke({"company_id": company.id})

        assert result is not None
        assert "Specific Company" in result
        assert "Av. Specific, 456" in result
        assert "5511888888888" in result

        # Cleanup
        db.delete(company)
        db.commit()

    def test_horario_tool_no_company_found(self, db):
        """Testa quando não encontra empresa."""
        result = horario_tool.invoke({"company_id": "non-existent-id"})

        assert result is not None
        assert "não foi possível encontrar" in result.lower()

    def test_horario_tool_includes_all_days(self, db):
        """Testa que todos os dias da semana são incluídos."""
        company = Company(name="Test", is_active=True)
        db.add(company)
        db.commit()

        result = horario_tool.invoke({"company_id": company.id})

        dias_semana = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
        for dia in dias_semana:
            assert dia in result, f"Dia {dia} não encontrado no resultado"

        # Cleanup
        db.delete(company)
        db.commit()

    def test_horario_tool_shows_current_day_marker(self, db):
        """Testa que marca o dia atual."""
        company = Company(name="Test", is_active=True)
        db.add(company)
        db.commit()

        result = horario_tool.invoke({"company_id": company.id})

        # Deve ter marcador "👈 Hoje" para o dia atual
        assert "👈 Hoje" in result

        # Cleanup
        db.delete(company)
        db.commit()

    def test_horario_tool_shows_open_closed_status(self, db):
        """Testa que mostra status aberto/fechado."""
        company = Company(name="Test", is_active=True)
        db.add(company)
        db.commit()

        result = horario_tool.invoke({"company_id": company.id})

        # Deve mostrar status atual
        assert "🟢 *ABERTO AGORA*" in result or "🔴 *FECHADO AGORA*" in result

        # Cleanup
        db.delete(company)
        db.commit()


class TestHorarioToolHelpers:
    """Testa funções auxiliares do horario_tool."""

    def test_get_dia_semana(self):
        """Testa conversão de weekday para nome do dia."""
        assert _get_dia_semana(0) == "Segunda"
        assert _get_dia_semana(1) == "Terça"
        assert _get_dia_semana(2) == "Quarta"
        assert _get_dia_semana(3) == "Quinta"
        assert _get_dia_semana(4) == "Sexta"
        assert _get_dia_semana(5) == "Sábado"
        assert _get_dia_semana(6) == "Domingo"

    def test_calcular_tempo_para_abrir_before_hours(self):
        """Testa cálculo de tempo antes do horário de abertura."""
        # 15:00, abre às 18:00
        agora = datetime(2026, 4, 14, 15, 0, 0)
        resultado = _calcular_tempo_para_abrir(agora)
        
        assert "3h" in resultado
        assert "min" in resultado

    def test_calcular_tempo_para_abrir_after_hours(self):
        """Testa cálculo de tempo após horário de fechamento."""
        # 23:30, abre às 18:00 no dia seguinte
        agora = datetime(2026, 4, 14, 23, 30, 0)
        resultado = _calcular_tempo_para_abrir(agora)
        
        assert "h" in resultado
        assert "min" in resultado


class TestHorarioToolErrorHandling:
    """Testa tratamento de erros no horario_tool."""

    def test_horario_tool_database_error(self, db):
        """Testa erro de banco de dados."""
        with patch('app.agents.tools.horario_tool.SessionLocal') as mock_session:
            mock_session.side_effect = Exception("Database error")
            
            result = horario_tool.invoke({"company_id": ""})
            
            assert result is not None
            assert "Erro ao consultar horário" in result

    def test_horario_tool_with_missing_company_fields(self, db):
        """Testa empresa sem campos opcionais."""
        company = Company(
            name="Minimal Company",
            is_active=True
            # Sem address e phone
        )
        db.add(company)
        db.commit()

        result = horario_tool.invoke({"company_id": company.id})

        assert result is not None
        assert "Minimal Company" in result
        # Não deve ter endereço nem telefone
        assert "Endereço:" not in result
        assert "Telefone:" not in result

        # Cleanup
        db.delete(company)
        db.commit()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
