import { ChevronDown } from 'lucide-react'
import { cn } from '../../lib/cn'

interface Option { value: string; label: string }

interface FilterSelectProps {
  /** Accessible name, e.g. "Language". */
  label: string
  value: string
  options: Option[]
  onChange: (value: string) => void
  className?: string
}

/** Outlined dropdown filter (native <select> for keyboard + mobile support). */
export default function FilterSelect({ label, value, options, onChange, className }: FilterSelectProps) {
  return (
    <label className={cn('relative inline-flex', className)}>
      <span className="sr-only">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={cn(
          'h-9 w-full appearance-none rounded-lg border border-line bg-surface pl-3 pr-8 text-sm text-fg cursor-pointer',
          'hover:border-line-strong',
        )}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
      <ChevronDown size={14} className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-fg-3" aria-hidden />
    </label>
  )
}
