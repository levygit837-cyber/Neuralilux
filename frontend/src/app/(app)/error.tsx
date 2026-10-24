'use client'

import { useEffect } from 'react'

export default function Error({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  useEffect(() => {
    console.error(error)
  }, [error])

  return (
    <div role="alert" className="flex flex-1 flex-col items-center justify-center gap-4 p-8 text-center">
      <h2 className="text-xl font-semibold text-text-light">Algo deu errado</h2>
      <p className="max-w-md text-sm text-text-gray">Esta página falhou ao carregar. Tente novamente.</p>
      <button
        type="button"
        onClick={() => retry()}
        className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-light"
      >
        Tentar novamente
      </button>
    </div>
  )
}
