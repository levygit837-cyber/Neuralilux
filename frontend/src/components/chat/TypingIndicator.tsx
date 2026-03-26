export function TypingIndicator() {
  return (
    <div className="flex items-center gap-3 py-3">
      <div className="flex items-center gap-1 rounded-md border border-border-color bg-card px-4 py-3">
        <div className="flex gap-1">
          <span className="h-2 w-2 animate-bounce rounded-full bg-text-muted [animation-delay:-0.3s]"></span>
          <span className="h-2 w-2 animate-bounce rounded-full bg-text-muted [animation-delay:-0.15s]"></span>
          <span className="h-2 w-2 animate-bounce rounded-full bg-text-muted"></span>
        </div>
      </div>
    </div>
  )
}
