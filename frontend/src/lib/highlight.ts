// Lazy syntax support. Parsers load on first use so the main bundle stays small.
import type { LanguageSupport } from '@codemirror/language'

export async function loadLanguage(lang: string): Promise<LanguageSupport | null> {
  switch (lang) {
    case 'python': return (await import('@codemirror/lang-python')).python()
    case 'javascript': return (await import('@codemirror/lang-javascript')).javascript({ jsx: true })
    case 'typescript': return (await import('@codemirror/lang-javascript')).javascript({ jsx: true, typescript: true })
    case 'java': return (await import('@codemirror/lang-java')).java()
    case 'go': return (await import('@codemirror/lang-go')).go()
    case 'rust': return (await import('@codemirror/lang-rust')).rust()
    case 'c':
    case 'cpp': return (await import('@codemirror/lang-cpp')).cpp()
    default: return null // kotlin, csharp, ruby: plain text
  }
}

export interface Token { text: string; cls: string }

/** Split code into lines of classed tokens (tok-keyword, tok-string, …). null = unsupported language. */
export async function highlightLines(code: string, lang: string): Promise<Token[][] | null> {
  const support = await loadLanguage(lang)
  if (!support) return null
  const { highlightCode, classHighlighter } = await import('@lezer/highlight')
  const tree = support.language.parser.parse(code)
  const lines: Token[][] = [[]]
  highlightCode(
    code, tree, classHighlighter,
    (text, cls) => { lines[lines.length - 1].push({ text, cls }) },
    () => { lines.push([]) },
  )
  return lines
}
