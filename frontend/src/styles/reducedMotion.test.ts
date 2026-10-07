/// <reference types="node" />
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

// Read from disk: Vitest stubs CSS imports (even ?raw) to an empty string.
const css = readFileSync(new URL('./globals.css', import.meta.url), 'utf8')

// The landing ticker and login dial are `infinite` CSS loops. Shrinking their
// duration under reduced motion without capping iterations makes them cycle
// every frame (looks like racing) instead of stopping.
describe('prefers-reduced-motion override', () => {
  const block = css.match(/@media \(prefers-reduced-motion: reduce\)\s*\{[\s\S]*?\}\s*\}/)?.[0] ?? ''

  it('exists', () => {
    expect(block).not.toBe('')
  })

  it('stops infinite animations instead of speeding them up', () => {
    expect(block).toMatch(/animation-duration:\s*0\.01ms\s*!important/)
    expect(block).toMatch(/animation-iteration-count:\s*1\s*!important/)
  })
})
