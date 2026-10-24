export interface Trend {
  direction: 'up' | 'down' | 'flat'
  label: string
}

function direction(delta: number): Trend['direction'] {
  if (delta > 0) return 'up'
  if (delta < 0) return 'down'
  return 'flat'
}

const signed = (value: number): string => (value > 0 ? `+${value}` : `${value}`)

/**
 * Variação percentual contra o período anterior. Sem base de comparação (período anterior em zero) não há
 * tendência honesta: devolve `null` e o card não mostra nada.
 */
export function countTrend(current: number, previous: number): Trend | null {
  if (previous <= 0) return null
  const percent = Math.round(((current - previous) / previous) * 100)
  return { direction: direction(percent), label: `${signed(percent)}%` }
}

/** Diferença em pontos percentuais entre duas taxas; `null` se uma delas não existe no período. */
export function rateTrend(current: number | null, previous: number | null): Trend | null {
  if (current === null || previous === null) return null
  const points = Math.round((current - previous) * 10) / 10
  return { direction: direction(points), label: `${signed(points)} p.p.` }
}
