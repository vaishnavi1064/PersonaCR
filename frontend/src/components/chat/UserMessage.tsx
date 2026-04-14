import { motion } from 'framer-motion'

export default function UserMessage({ text }: { text: string }) {
  const isCode = text.includes('\n') && /\b(def |function |class |import |const |let |var )\b/.test(text)

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
      style={{ display: 'flex', justifyContent: 'flex-end', padding: '4px 0' }}
    >
      <div style={{
        maxWidth: '80%',
        background: 'var(--bg-secondary)',
        border: '0.5px solid var(--border)',
        borderRadius: '14px 14px 4px 14px',
        padding: '10px 16px',
        overflow: 'hidden',
      }}>
        {isCode ? (
          <pre style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 13,
            color: 'var(--text-primary)',
            margin: 0,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            lineHeight: 1.6,
          }}>
            {text}
          </pre>
        ) : (
          <p style={{
            fontFamily: 'var(--font-body)',
            fontSize: 15,
            color: 'var(--text-primary)',
            margin: 0,
            lineHeight: 1.55,
          }}>
            {text}
          </p>
        )}
      </div>
    </motion.div>
  )
}
