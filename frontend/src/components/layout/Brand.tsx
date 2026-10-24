import { Brain, Sparkle } from '@phosphor-icons/react/dist/ssr'

export function Brand() {
  return (
    <div className="flex items-center gap-3">
      <div className="relative flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-secondary shadow-glow">
        <Brain weight="fill" className="text-lg text-white" />
        <Sparkle weight="fill" className="absolute -right-1 -top-1 text-[10px] text-accent" />
      </div>
      <span className="bg-gradient-to-r from-content-light to-content-gray bg-clip-text text-sm font-bold uppercase tracking-[0.15em] text-transparent">
        NeuraliLux
      </span>
    </div>
  )
}
