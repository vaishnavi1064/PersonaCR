import { describe, expect, it } from 'vitest'
import { historyFor } from './chats'

describe('historyFor', () => {
  it('turns this chat into bounded Q&A turns; code is described, errors skipped', () => {
    const msgs = [
      { role: 'user' as const, type: 'text', text: 'How do we name things?', data: { mode: 'ask' } },
      { role: 'bot' as const, type: 'text', text: 'snake_case.', data: {} },
      { role: 'user' as const, type: 'text', text: 'def f():\n    pass', data: { mode: 'review', language: 'python' } },
      { role: 'bot' as const, type: 'review', data: { overall_score: 72.4, issues: [{}, {}] } },
      { role: 'bot' as const, type: 'text', text: 'Could not reach the server', data: { error: true } },
    ]
    expect(historyFor(msgs)).toEqual([
      { role: 'user', content: 'How do we name things?' },
      { role: 'assistant', content: 'snake_case.' },
      { role: 'user', content: '[Submitted 2 lines of code for review]' },
      { role: 'assistant', content: '[Review result: score 72/100, 2 findings]' },
    ])
  })

  it('keeps only the most recent 8 turns', () => {
    const msgs = Array.from({ length: 20 }, (_, i) => ({ role: (i % 2 ? 'bot' : 'user') as 'bot' | 'user', type: 'text', text: `m${i}`, data: {} }))
    const h = historyFor(msgs)
    expect(h).toHaveLength(8)
    expect(h.at(-1)!.content).toBe('m19')
  })
})
