/**
 * Timers que apagam o Thinking de uma Conversation depois do `thinking_end`. Ficam fora do Zustand: um
 * `setTimeout` não é estado da tela, e um só por Conversation garante que o timer da rodada anterior
 * nunca apague o Thinking da rodada seguinte (quem começa uma rodada, ou reabre o resumo, cancela o pendente).
 */
export const THINKING_CLEAR_DELAY_MS = 5000

const timers = new Map<string, ReturnType<typeof setTimeout>>()

export function cancelThinkingClear(conversationId: string): void {
  const timer = timers.get(conversationId)
  if (timer === undefined) return
  clearTimeout(timer)
  timers.delete(conversationId)
}

/** Agenda `clear` para daqui a `THINKING_CLEAR_DELAY_MS`, cancelando o timer anterior da mesma Conversation. */
export function scheduleThinkingClear(conversationId: string, clear: () => void): void {
  cancelThinkingClear(conversationId)
  timers.set(
    conversationId,
    setTimeout(() => {
      timers.delete(conversationId)
      clear()
    }, THINKING_CLEAR_DELAY_MS)
  )
}

export function cancelAllThinkingClears(): void {
  timers.forEach((timer) => clearTimeout(timer))
  timers.clear()
}
