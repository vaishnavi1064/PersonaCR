import { useState, useRef, KeyboardEvent } from 'react'
import { Send, Paperclip } from 'lucide-react'

interface ChatInputProps {
  onSubmit: (text: string) => void
  disabled?: boolean
}

export default function ChatInput({ onSubmit, disabled }: ChatInputProps) {
  const [value, setValue] = useState('')
  const [focused, setFocused] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleSubmit = () => {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSubmit(trimmed)
    setValue('')
    // Reset textarea height
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const handleInput = () => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = `${Math.min(ta.scrollHeight, 160)}px`
  }

  return (
    <div style={{
      padding: '12px 0 20px',
      flexShrink: 0,
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'flex-end',
        gap: 8,
        border: `1px solid ${focused ? 'var(--accent)' : 'var(--border)'}`,
        borderRadius: 12,
        padding: '8px 10px 8px 16px',
        background: 'var(--bg-primary)',
        transition: 'border-color 0.15s',
      }}>
        {/* Textarea */}
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onInput={handleInput}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          disabled={disabled}
          placeholder="Paste a repo URL, drop a file, or ask a question..."
          rows={1}
          style={{
            flex: 1,
            fontFamily: 'var(--font-body)',
            fontSize: 15,
            color: 'var(--text-primary)',
            background: 'transparent',
            border: 'none',
            outline: 'none',
            resize: 'none',
            lineHeight: 1.55,
            padding: 0,
            maxHeight: 160,
            overflowY: 'auto',
          }}
        />

        {/* Paperclip */}
        <button
          type="button"
          style={{
            width: 34,
            height: 34,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            border: '0.5px solid var(--border)',
            borderRadius: 8,
            background: 'transparent',
            color: 'var(--text-tertiary)',
            cursor: 'pointer',
            flexShrink: 0,
            transition: 'background 0.15s, color 0.15s',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'var(--bg-secondary)'
            e.currentTarget.style.color = 'var(--text-secondary)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'transparent'
            e.currentTarget.style.color = 'var(--text-tertiary)'
          }}
        >
          <Paperclip size={14} />
        </button>

        {/* Send */}
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!value.trim() || disabled}
          style={{
            width: 34,
            height: 34,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: value.trim() && !disabled ? 'var(--accent)' : 'var(--bg-secondary)',
            borderRadius: 8,
            border: 'none',
            color: value.trim() && !disabled ? 'white' : 'var(--text-tertiary)',
            cursor: value.trim() && !disabled ? 'pointer' : 'default',
            flexShrink: 0,
            transition: 'background 0.15s, color 0.15s',
          }}
        >
          <Send size={14} />
        </button>
      </div>

      <p style={{
        fontFamily: 'var(--font-body)',
        fontSize: 12,
        color: 'var(--text-tertiary)',
        textAlign: 'center',
        marginTop: 8,
        opacity: 0.7,
      }}>
        Shift + Enter for new line
      </p>
    </div>
  )
}
