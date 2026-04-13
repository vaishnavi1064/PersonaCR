import { useStore } from '../../store/useStore'

const accents: { key: 'purple' | 'blue' | 'teal' | 'coral'; color: string }[] = [
  { key: 'purple', color: '#8B7CF6' },
  { key: 'blue',   color: '#5B8DEF' },
  { key: 'teal',   color: '#4ECDC4' },
  { key: 'coral',  color: '#F07167' },
]

export default function AccentPicker() {
  const { accent, setAccent } = useStore()

  const handlePick = (key: typeof accents[0]['key']) => {
    setAccent(key)
    document.documentElement.setAttribute('data-accent', key)
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      {accents.map((a) => (
        <button
          key={a.key}
          title={a.key}
          onClick={() => handlePick(a.key)}
          style={{
            width: 12,
            height: 12,
            borderRadius: '50%',
            background: a.color,
            border: 'none',
            cursor: 'pointer',
            padding: 0,
            flexShrink: 0,
            boxShadow:
              accent === a.key
                ? `0 0 0 2px var(--bg-primary), 0 0 0 4px ${a.color}`
                : 'none',
            transition: 'box-shadow 0.15s ease',
          }}
        />
      ))}
    </div>
  )
}
