import { Check } from 'lucide-react'
import { useStore } from '../../store/useStore'
import { cn } from '../../lib/cn'

const accents: { key: 'purple' | 'blue' | 'teal' | 'coral'; label: string; color: string }[] = [
  { key: 'purple', label: 'Violet', color: '#8B7CF6' },
  { key: 'blue',   label: 'Blue',   color: '#5B8DEF' },
  { key: 'teal',   label: 'Teal',   color: '#4ECDC4' },
  { key: 'coral',  label: 'Coral',  color: '#F07167' },
]

export default function AccentPicker() {
  const { accent, setAccent } = useStore()

  const handlePick = (key: typeof accents[0]['key']) => {
    setAccent(key)
    document.documentElement.setAttribute('data-accent', key)
  }

  return (
    <div role="radiogroup" aria-label="Accent color" className="flex flex-wrap gap-2">
      {accents.map((a) => {
        const selected = accent === a.key
        return (
          <button
            key={a.key}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => handlePick(a.key)}
            className={cn(
              'flex h-9 items-center gap-2 rounded-lg border px-3 text-sm cursor-pointer',
              selected ? 'border-line-strong bg-surface-hover text-fg' : 'border-line text-fg-2 hover:border-line-strong',
            )}
          >
            <span className="flex h-4 w-4 items-center justify-center rounded-full" style={{ background: a.color }} aria-hidden>
              {selected && <Check size={10} strokeWidth={3} color="#0A0A0B" />}
            </span>
            {a.label}
          </button>
        )
      })}
    </div>
  )
}
