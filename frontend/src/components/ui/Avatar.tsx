import { useState } from 'react'
import { cn } from '../../lib/cn'

interface AvatarProps {
  src?: string | null
  initials: string
  size?: number
  className?: string
}

export default function Avatar({ src, initials, size = 32, className }: AvatarProps) {
  const [failed, setFailed] = useState(false)
  const style = { width: size, height: size }
  if (src && !failed) {
    return (
      <img
        src={src}
        alt=""
        style={style}
        onError={() => setFailed(true)}
        className={cn('shrink-0 rounded-full border border-line object-cover', className)}
      />
    )
  }
  return (
    <span
      style={style}
      className={cn('flex shrink-0 items-center justify-center rounded-full bg-accent-soft font-mono text-xs font-medium text-accent', className)}
      aria-hidden
    >
      {initials}
    </span>
  )
}
