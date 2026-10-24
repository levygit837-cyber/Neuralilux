interface WidgetErrorProps {
  message: string
  onRetry: () => void
}

/** Erro de um widget só: os outros continuam na tela. */
export function WidgetError({ message, onRetry }: WidgetErrorProps) {
  return (
    <div
      role="alert"
      className="flex flex-1 flex-col items-center justify-center gap-3 rounded-lg border border-status-error/30 bg-status-error/10 px-4 py-6 text-center text-sm text-status-error"
    >
      <span>{message}</span>
      <button type="button" className="underline" onClick={onRetry}>
        Tentar de novo
      </button>
    </div>
  )
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Falha ao carregar o widget'
}
