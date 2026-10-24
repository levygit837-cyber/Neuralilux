// @vitest-environment jsdom
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import DashboardPage from '@/app/(app)/dashboard/page'
import { dashboardService } from '@/services/dashboardService'
import { HttpError } from '@/services/http'
import { useAuthStore } from '@/stores/useAuthStore'
import { queryWrapper } from '@/test/queryWrapper'
import type { DashboardOverview } from '@/types/dashboard'

vi.mock('@/services/dashboardService', () => ({
  dashboardService: {
    getOverview: vi.fn(),
    getConversationsOverTime: vi.fn(),
    getMessagesByInstance: vi.fn(),
    getHandoffs: vi.fn(),
  },
}))

const overview: DashboardOverview = {
  conversations: { current: 15, previous: 10 },
  messages: { current: 40, previous: 0 },
  handoffs: { current: 2, previous: 4 },
  response_rate: { current: 50, previous: null, received: 4, answered: 2 },
}

function renderPage() {
  const { Wrapper } = queryWrapper()
  return render(<DashboardPage />, { wrapper: Wrapper })
}

describe('DashboardPage', () => {
  beforeEach(() => {
    useAuthStore.setState({ isAuthenticated: true, hasHydrated: true })
    vi.mocked(dashboardService.getOverview).mockResolvedValue(overview)
    vi.mocked(dashboardService.getConversationsOverTime).mockResolvedValue({
      timezone: 'America/Sao_Paulo',
      data: [
        { date: '2026-10-23', count: 1 },
        { date: '2026-10-24', count: 0 },
      ],
    })
    vi.mocked(dashboardService.getMessagesByInstance).mockResolvedValue({
      instances: [{ instance_id: 'i1', name: 'Loja Centro', count: 7 }],
    })
    vi.mocked(dashboardService.getHandoffs).mockResolvedValue({ open: 1, in_progress: 0, closed: 1, expired: 0 })
  })

  afterEach(() => {
    cleanup()
    vi.resetAllMocks()
    useAuthStore.setState({ isAuthenticated: false, hasHydrated: false })
  })

  it('mostra os números do backend, o nome real da Instance e a tendência contra o período anterior', async () => {
    renderPage()

    expect(await screen.findByText('Loja Centro')).toBeTruthy()
    const summary = screen.getByRole('region', { name: 'Resumo' })
    expect(within(summary).getByText('15')).toBeTruthy()
    expect(within(summary).getByText('+50%')).toBeTruthy() // 15 contra 10
    expect(within(summary).getByText('-50%')).toBeTruthy() // Handoffs: 2 contra 4
    expect(within(summary).getByText('50%')).toBeTruthy()
    expect(within(summary).getByText('2 de 4 mensagens de clientes respondidas')).toBeTruthy()
  })

  it('expõe os valores por dia do gráfico a leitor de tela', async () => {
    renderPage()

    const table = await screen.findByRole('table', { name: 'Conversations novas por dia' })
    const rows = within(table).getAllByRole('row').slice(1)
    expect(rows.map((row) => row.textContent)).toEqual(['23/10/20261', '24/10/20260'])
  })

  it('esconde a tendência quando o período anterior não tem base de comparação', async () => {
    renderPage()

    const summary = await screen.findByRole('region', { name: 'Resumo' })
    await within(summary).findByText('40')
    // Mensagens (40 contra 0) e Taxa de resposta (sem período anterior): só Conversas e Handoffs têm tendência
    expect(within(summary).getAllByTitle('Contra o período anterior')).toHaveLength(2)
  })

  it('não tem canal, exportação nem tendência inventada', async () => {
    renderPage()
    await screen.findByText('Loja Centro')

    for (const invented of [/WhatsApp/, /Website/, /Instagram/, /Exportar/, /2\.1%/, /Satisfação/]) {
      expect(screen.queryByText(invented)).toBeNull()
    }
  })

  it('o erro de um widget aparece só nele e os outros seguem na tela', async () => {
    vi.mocked(dashboardService.getMessagesByInstance).mockRejectedValue(
      new HttpError(500, 'Erro ao carregar os dados do dashboard')
    )

    renderPage()

    const alert = await screen.findByRole('alert')
    expect(alert.textContent).toContain('Erro ao carregar os dados do dashboard')
    expect(screen.getAllByRole('alert')).toHaveLength(1)
    expect(within(screen.getByRole('region', { name: 'Gráficos' })).getByRole('alert')).toBe(alert)
    expect(await screen.findByText('15')).toBeTruthy() // o resumo carregou
    expect(screen.queryByText('Loja Centro')).toBeNull()
  })

  it('erro na visão geral aparece nos quatro cartões e "Tentar de novo" refaz só essa query', async () => {
    vi.mocked(dashboardService.getOverview).mockRejectedValueOnce(new HttpError(500, 'Erro ao carregar os dados do dashboard'))

    renderPage()

    await waitFor(() => expect(within(screen.getByRole('region', { name: 'Resumo' })).getAllByRole('alert')).toHaveLength(4))
    expect(within(screen.getByRole('region', { name: 'Gráficos' })).queryByRole('alert')).toBeNull()
    screen.getAllByRole('button', { name: 'Tentar de novo' })[0].click()

    expect(await screen.findByText('15')).toBeTruthy()
    expect(dashboardService.getOverview).toHaveBeenCalledTimes(2)
    expect(dashboardService.getHandoffs).toHaveBeenCalledTimes(1)
  })
})
