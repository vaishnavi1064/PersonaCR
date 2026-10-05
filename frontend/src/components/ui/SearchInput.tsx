import type { InputHTMLAttributes } from 'react'
import { Search } from 'lucide-react'
import { cn } from '../../lib/cn'

interface SearchInputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'onChange' | 'value'> {
  value: string
  onChange: (value: string) => void
  /** Accessible name; defaults to the placeholder. */
  label?: string
}

export default function SearchInput({ value, onChange, label, placeholder = 'Search', className, ...rest }: SearchInputProps) {
  return (
    <label className={cn('relative inline-flex items-center', className)}>
      <span className="sr-only">{label ?? placeholder}</span>
      <Search size={15} className="pointer-events-none absolute left-3 text-fg-3" aria-hidden />
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="h-9 w-full rounded-lg border border-line bg-surface pl-9 pr-3 text-sm text-fg placeholder:text-fg-3 hover:border-line-strong focus:border-accent focus:outline-none"
        {...rest}
      />
    </label>
  )
}
