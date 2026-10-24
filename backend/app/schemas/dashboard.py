"""Respostas do dashboard. A definição de cada número está em `docs/dashboard.md`."""
from typing import Optional

from pydantic import BaseModel


class CountMetric(BaseModel):
    current: int
    previous: int  # o mesmo número no período anterior, de igual tamanho; base da tendência


class ResponseRateMetric(BaseModel):
    current: Optional[float] = None  # % de 0 a 100; None quando nenhum Contact escreveu no período
    previous: Optional[float] = None
    received: int  # Messages do Contact no período
    answered: int  # destas, as que tiveram uma resposta depois


class DashboardOverview(BaseModel):
    conversations: CountMetric
    messages: CountMetric
    handoffs: CountMetric
    response_rate: ResponseRateMetric


class ConversationsPerDay(BaseModel):
    date: str  # YYYY-MM-DD, dia no fuso da Company do usuário
    count: int


class ConversationsOverTime(BaseModel):
    timezone: str
    data: list[ConversationsPerDay]


class InstanceMessages(BaseModel):
    instance_id: str
    name: str
    count: int


class MessagesByInstance(BaseModel):
    instances: list[InstanceMessages]


class HandoffsByStatus(BaseModel):
    open: int
    in_progress: int
    closed: int
    expired: int
