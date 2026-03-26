'use client'

import { Header } from '@/components/layout/Header'
import { MetricCard } from '@/components/dashboard/MetricCard'
import { ActivityItem } from '@/components/dashboard/ActivityItem'
import { BusinessMetricCard } from '@/components/dashboard/BusinessMetricCard'
import type { Metric, Activity, BusinessMetric } from '@/types/dashboard'

// Mock data
const metrics: Metric[] = [
  {
    label: 'Conversas Ativas',
    value: '1,247',
    change: '+18%',
    trend: 'up',
  },
  {
    label: 'Tempo de Resposta',
    value: '2.3s',
    change: '-24%',
    trend: 'up',
  },
  {
    label: 'Taxa de Conversão',
    value: '68%',
    change: '+5%',
    trend: 'up',
  },
  {
    label: 'Satisfação (NPS)',
    value: '8.7',
    change: '+0.3',
    trend: 'up',
  },
]

const activities: Activity[] = [
  {
    id: '1',
    title: 'Nova conversa iniciada',
    description: 'Maria Silva - Clínica Saúde Total',
    timestamp: '2 min',
    type: 'message',
  },
  {
    id: '2',
    title: 'Agendamento confirmado',
    description: 'João Pedro - Consulta às 14h',
    timestamp: '5 min',
    type: 'appointment',
  },
  {
    id: '3',
    title: 'Venda concluída',
    description: 'Loja Fashion - R$ 450,00',
    timestamp: '15 min',
    type: 'sale',
  },
]

const businessMetrics: BusinessMetric[] = [
  {
    id: '1',
    name: 'Clínica Saúde Total',
    metrics: [
      { label: 'Consultas Hoje', value: '12' },
      { label: 'Taxa de Confirmação', value: '94%' },
      { label: 'Tempo Médio', value: '3.2min' },
    ],
  },
  {
    id: '2',
    name: 'Loja Fashion Store',
    metrics: [
      { label: 'Vendas Hoje', value: 'R$ 3.547' },
      { label: 'Conversões', value: '23' },
      { label: 'Ticket Médio', value: 'R$ 154' },
    ],
  },
  {
    id: '3',
    name: 'Varejo Express',
    metrics: [
      { label: 'Atendimentos', value: '45' },
      { label: 'Satisfação', value: '4.8/5' },
      { label: 'Tempo Resposta', value: '1.8min' },
    ],
  },
]

export default function DashboardPage() {
  return (
    <div className="flex min-h-screen flex-col bg-dark">
      <Header />
      <main className="flex-1 p-8">
        <div className="mx-auto max-w-7xl space-y-8">
          {/* Metrics Section */}
          <section>
            <h2 className="mb-4 text-xl font-bold text-text-light">Visão Geral</h2>
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
              {metrics.map((metric, index) => (
                <MetricCard key={index} metric={metric} />
              ))}
            </div>
          </section>

          {/* Business Metrics Section */}
          <section>
            <h2 className="mb-4 text-xl font-bold text-text-light">
              Métricas de Atendimento
            </h2>
            <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
              {businessMetrics.map((businessMetric) => (
                <BusinessMetricCard
                  key={businessMetric.id}
                  businessMetric={businessMetric}
                />
              ))}
            </div>
          </section>

          {/* Recent Activity Section */}
          <section>
            <h2 className="mb-4 text-xl font-bold text-text-light">
              Atividade Recente
            </h2>
            <div className="rounded-lg border border-border-color bg-card p-6">
              <div className="divide-y divide-border">
                {activities.map((activity) => (
                  <ActivityItem key={activity.id} activity={activity} />
                ))}
              </div>
            </div>
          </section>
        </div>
      </main>
    </div>
  )
}
