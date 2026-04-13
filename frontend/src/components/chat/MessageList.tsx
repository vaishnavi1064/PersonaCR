import { useEffect, useRef } from 'react'
import BotMessage, { TypingIndicator } from './BotMessage'
import UserMessage from './UserMessage'

export interface ChatMessage {
  id: string
  role: 'user' | 'bot'
  text?: string
  type?: 'text' | 'fingerprint' | 'review'
  data?: Record<string, unknown>
}

interface MessageListProps {
  messages: ChatMessage[]
  loading?: boolean
}

export default function MessageList({ messages, loading }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length, loading])

  return (
    <div style={{
      flex: 1,
      overflowY: 'auto',
      padding: '24px 0 16px',
      display: 'flex',
      flexDirection: 'column',
      gap: 4,
    }}>
      {messages.map((msg) =>
        msg.role === 'user' ? (
          <UserMessage key={msg.id} text={msg.text ?? ''} />
        ) : (
          <BotMessage
            key={msg.id}
            text={msg.text}
            type={msg.type ?? 'text'}
            data={msg.data}
          />
        )
      )}
      {loading && <TypingIndicator />}
      <div ref={bottomRef} />
    </div>
  )
}
