import { describe, expect, it } from 'vitest'
import { countTrend, rateTrend } from '@/lib/dashboardTrend'

describe('countTrend', () => {
  it('compara com o período anterior', () => {
    expect(countTrend(15, 10)).toEqual({ direction: 'up', label: '+50%' })
    expect(countTrend(5, 10)).toEqual({ direction: 'down', label: '-50%' })
    expect(countTrend(10, 10)).toEqual({ direction: 'flat', label: '0%' })
  })

  it('some quando o período anterior está vazio, porque não há base de comparação', () => {
    expect(countTrend(7, 0)).toBeNull()
    expect(countTrend(0, 0)).toBeNull()
  })
})

describe('rateTrend', () => {
  it('é a diferença em pontos percentuais', () => {
    expect(rateTrend(75, 50)).toEqual({ direction: 'up', label: '+25 p.p.' })
    expect(rateTrend(40.5, 50)).toEqual({ direction: 'down', label: '-9.5 p.p.' })
  })

  it('some se um dos períodos não teve mensagens do Contact', () => {
    expect(rateTrend(null, 50)).toBeNull()
    expect(rateTrend(50, null)).toBeNull()
  })
})
