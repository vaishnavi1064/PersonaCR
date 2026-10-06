import { describe, expect, it, vi } from 'vitest'

// repos.ts records imports via db.ts, which needs Supabase env — not under test here.
vi.mock('../db', () => ({ saveRepo: vi.fn() }))

const { fingerprintChips, normalizeFingerprint, parseRepoUrl } = await import('./repos')

describe('parseRepoUrl', () => {
  it.each([
    'https://github.com/pypa/sampleproject',
    'https://github.com/pypa/sampleproject/',
    'https://github.com/pypa/sampleproject.git',
    'http://www.github.com/pypa/sampleproject/tree/main/src',
    'github.com/pypa/sampleproject',
    'pypa/sampleproject',
  ])('%s', (input) => {
    expect(parseRepoUrl(input)).toEqual({
      url: 'https://github.com/pypa/sampleproject', owner: 'pypa', name: 'sampleproject', fullName: 'pypa/sampleproject',
    })
  })

  it.each(['', 'not a url', 'https://gitlab.com/a/b', 'https://github.com/onlyowner', 'a/b/c'])('rejects %j', (input) => {
    expect(parseRepoUrl(input)).toBeNull()
  })
})

describe('fingerprint', () => {
  it('chips show real values and skip missing/unknown ones', () => {
    const fp = normalizeFingerprint({ type_hint_usage: 0.79, naming_convention: 'snake_case', docstring_coverage: 0.414 })
    expect(fingerprintChips(fp)).toEqual(['79% type hints', 'snake_case', '41% docstrings'])
    expect(fingerprintChips(normalizeFingerprint({ naming_convention: 'unknown', error_handling_rate: 0 }))).toEqual(['0% error handling'])
  })

  it('drops the type-hint chip when the repo has non-Python functions (always counted as typed)', () => {
    const java = normalizeFingerprint({ type_hint_usage: 1, naming_convention: 'camelCase', language_distribution: { java: 108 } })
    expect(fingerprintChips(java)).toEqual(['camelCase'])
    const mixed = normalizeFingerprint({ type_hint_usage: 0.44, language_distribution: { python: 500, javascript: 54 } })
    expect(fingerprintChips(mixed)).toEqual([])
    const py = normalizeFingerprint({ type_hint_usage: 0.44, language_distribution: { python: 554 } })
    expect(fingerprintChips(py)).toEqual(['44% type hints'])
  })

  it('a partial cached row keeps missing fields null, not 0', () => {
    const fp = normalizeFingerprint({ avg_function_length: 15 })!
    expect(fp.avgFunctionLength).toBe(15)
    expect(fp.typeHintUsage).toBeNull()
    expect(normalizeFingerprint({})).toBeNull()
    expect(normalizeFingerprint(null)).toBeNull()
  })
})

describe('type hints on current fingerprints', () => {
  it('trusts the measured rate and treats null as not measured', () => {
    const java = normalizeFingerprint({ type_hint_usage: null, type_hint_functions: 0, naming_convention: 'camelCase', language_distribution: { java: 10 } })
    expect(fingerprintChips(java)).toEqual(['camelCase'])
    const mixed = normalizeFingerprint({ type_hint_usage: 0.5, type_hint_functions: 2, language_distribution: { python: 2, java: 3 } })
    expect(fingerprintChips(mixed)).toEqual(['50% type hints'])
  })
})
