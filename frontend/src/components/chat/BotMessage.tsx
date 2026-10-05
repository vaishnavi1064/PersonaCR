import { motion } from 'framer-motion'
import FingerprintCard from './FingerprintCard'
import ReviewResult from './ReviewResult'
import { LogoMark } from '../ui/Logo'

function BotAvatar() {
  return (
    <div style={{
      width: 26,
      height: 26,
      borderRadius: '50%',
      background: 'var(--accent-surface)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      flexShrink: 0,
      marginTop: 2,
    }}>
      <LogoMark size={11} innerFill="var(--accent-surface)" />
    </div>
  )
}

// 3-dot typing indicator
export function TypingIndicator() {
  return (
    <div style={{ display: 'flex', gap: 10, padding: '4px 0', alignItems: 'flex-start' }}>
      <BotAvatar />
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 5,
        padding: '12px 16px',
        background: 'var(--bg-secondary)',
        border: '0.5px solid var(--border)',
        borderRadius: '4px 14px 14px 14px',
      }}>
        <style>{`
          @keyframes dot-bounce {
            0%, 60%, 100% { transform: translateY(0); }
            30%            { transform: translateY(-5px); }
          }
        `}</style>
        {[0, 0.18, 0.36].map((delay, i) => (
          <div key={i} style={{
            width: 6, height: 6,
            borderRadius: '50%',
            background: 'var(--text-tertiary)',
            animation: `dot-bounce 1.1s ease-in-out ${delay}s infinite`,
          }} />
        ))}
      </div>
    </div>
  )
}

interface BotMessageProps {
  text?: string
  type?: 'text' | 'fingerprint' | 'review'
  data?: Record<string, unknown>
}

export default function BotMessage({ text, type = 'text', data }: BotMessageProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
      style={{ display: 'flex', gap: 10, padding: '4px 0', alignItems: 'flex-start' }}
    >
      <BotAvatar />

      <div style={{ flex: 1, minWidth: 0 }}>
        {/* Plain text (always shown if present) */}
        {text && (
          <p style={{
            fontFamily: 'var(--font-body)',
            fontSize: 15,
            color: 'var(--text-primary)',
            lineHeight: 1.6,
            margin: 0,
            marginBottom: (type === 'fingerprint' || type === 'review') ? 0 : undefined,
          }}>
            {text}
          </p>
        )}

        {/* Rich card */}
        {type === 'fingerprint' && data && (
          <FingerprintCard data={data as Parameters<typeof FingerprintCard>[0]['data']} />
        )}
        {type === 'review' && data && (
          <ReviewResult data={data as unknown as Parameters<typeof ReviewResult>[0]['data']} />
        )}
      </div>
    </motion.div>
  )
}
