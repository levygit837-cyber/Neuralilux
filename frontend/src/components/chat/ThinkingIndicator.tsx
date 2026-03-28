'use client'

import { useEffect, useState } from 'react'

export function ThinkingIndicator() {
  const [dotIndex, setDotIndex] = useState(0)

  useEffect(() => {
    const interval = setInterval(() => {
      setDotIndex((prev) => (prev + 1) % 3)
    }, 400)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="flex items-center gap-3 py-2">
      <div className="flex items-center gap-3 rounded-full border border-[#8B5CF630] bg-[#120F27] px-4 py-3">
        {/* Icon circle with 3 dots */}
        <div className="flex h-[30px] w-[30px] items-center justify-center rounded-full bg-primary">
          <div className="flex gap-[3px]">
            <span
              className="h-1 w-1 rounded-full bg-white transition-opacity duration-200"
              style={{ opacity: dotIndex === 0 ? 1 : 0.35 }}
            />
            <span
              className="h-1 w-1 rounded-full bg-white transition-opacity duration-200"
              style={{ opacity: dotIndex === 1 ? 1 : 0.35 }}
            />
            <span
              className="h-1 w-1 rounded-full bg-white transition-opacity duration-200"
              style={{ opacity: dotIndex === 2 ? 1 : 0.35 }}
            />
          </div>
        </div>

        {/* Label */}
        <span className="text-sm font-semibold text-text-light">Pensando...</span>

        {/* Pulsing dots */}
        <div className="flex gap-1">
          <span
            className="h-1.5 w-1.5 rounded-full bg-primary transition-opacity duration-300"
            style={{ opacity: 1 }}
          />
          <span
            className="h-1.5 w-1.5 rounded-full bg-primary transition-opacity duration-300"
            style={{ opacity: 0.6 }}
          />
          <span
            className="h-1.5 w-1.5 rounded-full bg-primary transition-opacity duration-300"
            style={{ opacity: 0.35 }}
          />
        </div>
      </div>
    </div>
  )
}