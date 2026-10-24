'use client'

import { Plus, Trash } from '@phosphor-icons/react'
import { DAY_KEYS, DAY_LABELS, type DayKey, type Interval } from '@/types/company'
import { crossesMidnight } from './drafts'

interface Props {
  hours: Record<DayKey, Interval[]>
  onChange: (hours: Record<DayKey, Interval[]>) => void
  error?: string
}

const timeInput =
  'h-10 rounded-lg border border-brand-border bg-brand-base px-3 text-sm text-content-light focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary'

export const HOURS_ERROR_ID = 'company-business-hours-error'

export function HoursEditor({ hours, onChange, error }: Props) {
  const setDay = (day: DayKey, intervals: Interval[]) => onChange({ ...hours, [day]: intervals })

  return (
    <fieldset className="space-y-2">
      <legend className="mb-2 text-sm font-medium text-content-light">Horários de funcionamento</legend>
      {DAY_KEYS.map((day) => (
        <div key={day} className="flex items-start gap-3 border-b border-brand-border/50 pb-2">
          <span className="w-20 pt-2 text-sm text-content-gray">{DAY_LABELS[day]}</span>
          <div className="flex-1 space-y-2">
            {hours[day].length === 0 && <p className="pt-2 text-sm text-content-gray">Fechado</p>}
            {hours[day].map((interval, index) => (
              <div key={index} className="flex flex-wrap items-center gap-2">
                <input
                  type="time"
                  aria-label={`${DAY_LABELS[day]}: abre`}
                  aria-invalid={Boolean(error)}
                  aria-describedby={error ? HOURS_ERROR_ID : undefined}
                  value={interval[0]}
                  className={timeInput}
                  onChange={(e) =>
                    setDay(day, hours[day].map((it, i) => (i === index ? [e.target.value, it[1]] : it)))
                  }
                />
                <span className="text-sm text-content-gray">até</span>
                <input
                  type="time"
                  aria-label={`${DAY_LABELS[day]}: fecha`}
                  aria-invalid={Boolean(error)}
                  aria-describedby={error ? HOURS_ERROR_ID : undefined}
                  value={interval[1]}
                  className={timeInput}
                  onChange={(e) =>
                    setDay(day, hours[day].map((it, i) => (i === index ? [it[0], e.target.value] : it)))
                  }
                />
                {crossesMidnight(interval) && <span className="text-xs text-content-gray">(até o dia seguinte)</span>}
                <button
                  type="button"
                  aria-label={`${DAY_LABELS[day]}: remover intervalo`}
                  onClick={() => setDay(day, hours[day].filter((_, i) => i !== index))}
                  className="rounded-lg p-2 text-content-gray hover:text-status-error focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                >
                  <Trash className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>
            ))}
            <button
              type="button"
              onClick={() => setDay(day, [...hours[day], hours[day].length === 0 ? ['18:00', '23:00'] : ['', '']])}
              className="inline-flex items-center gap-1 text-xs font-medium text-primary-light hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              <Plus className="h-3.5 w-3.5" aria-hidden="true" /> Adicionar intervalo
            </button>
          </div>
        </div>
      ))}
      {error && (
        <p id={HOURS_ERROR_ID} role="alert" className="text-xs text-status-error">
          {error}
        </p>
      )}
    </fieldset>
  )
}
