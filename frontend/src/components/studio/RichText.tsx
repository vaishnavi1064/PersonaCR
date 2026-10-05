import type { ReactNode } from 'react'

/**
 * Minimal rendering for LLM answers: ``` fences → code blocks, `inline` → code,
 * **bold** → strong, newlines kept. No HTML is ever injected.
 */
export default function RichText({ text }: { text: string }) {
  const parts: ReactNode[] = []
  const fence = /```[\w+-]*\n?([\s\S]*?)```/g
  let last = 0
  let m: RegExpExecArray | null
  let k = 0
  while ((m = fence.exec(text))) {
    if (m.index > last) parts.push(<Inline key={k++} text={text.slice(last, m.index)} />)
    parts.push(
      <pre key={k++} className="my-2 overflow-x-auto rounded-lg border border-line bg-canvas px-3 py-2 font-mono text-[12.5px] leading-6 text-fg-2">
        {m[1].replace(/\n$/, '')}
      </pre>,
    )
    last = fence.lastIndex
  }
  if (last < text.length) parts.push(<Inline key={k++} text={text.slice(last)} />)
  return <div className="text-sm leading-6 text-fg">{parts}</div>
}

function Inline({ text }: { text: string }) {
  const tokens = text.split(/(`[^`\n]+`|\*\*[^*\n]+\*\*)/g)
  return (
    <span className="whitespace-pre-wrap break-words">
      {tokens.map((t, i) => {
        if (t.startsWith('`') && t.endsWith('`') && t.length > 2) {
          return <code key={i} className="rounded bg-raised px-1 py-0.5 font-mono text-[12.5px] text-fg">{t.slice(1, -1)}</code>
        }
        if (t.startsWith('**') && t.endsWith('**') && t.length > 4) return <strong key={i} className="font-semibold">{t.slice(2, -2)}</strong>
        return t
      })}
    </span>
  )
}
