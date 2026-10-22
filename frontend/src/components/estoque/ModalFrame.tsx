import type { ReactNode } from 'react'
import { X } from 'lucide-react'

export function ModalFrame({
  title,
  description,
  onClose,
  children,
}: {
  title: string
  description: string
  onClose: () => void
  children: ReactNode
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-dark/80 px-4 backdrop-blur-sm">
      <div className="w-full max-w-2xl rounded-3xl border border-border-color bg-card shadow-2xl">
        <div className="flex items-start justify-between border-b border-border-color px-6 py-5">
          <div>
            <h2 className="text-xl font-semibold text-text-light">{title}</h2>
            <p className="mt-1 text-sm text-text-muted">{description}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full bg-hover p-2 text-text-muted transition-colors hover:bg-border-color hover:text-text-light"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="max-h-[80vh] overflow-y-auto px-6 py-6">{children}</div>
      </div>
    </div>
  )
}
