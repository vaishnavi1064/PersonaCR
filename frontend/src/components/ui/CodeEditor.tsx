import { useEffect, useRef } from 'react'
import { Compartment, EditorState } from '@codemirror/state'
import {
  EditorView, drawSelection, highlightActiveLine, highlightActiveLineGutter, keymap, lineNumbers,
  placeholder as placeholderExt,
} from '@codemirror/view'
import { defaultKeymap, history, historyKeymap, indentWithTab } from '@codemirror/commands'
import { bracketMatching, indentOnInput, indentUnit, syntaxHighlighting } from '@codemirror/language'
import { classHighlighter } from '@lezer/highlight'
import { loadLanguage } from '../../lib/highlight'

interface CodeEditorProps {
  value: string
  onChange: (value: string) => void
  language: string
  /** Ctrl/Cmd+Enter. */
  onSubmit?: () => void
  placeholder?: string
  ariaLabel: string
  disabled?: boolean
}

// Colors come from CSS variables, so one theme serves dark and light.
const theme = EditorView.theme({
  '&': { backgroundColor: 'var(--bg-primary)', color: 'var(--text-primary)', fontSize: '12.5px', maxHeight: '45vh' },
  '&.cm-focused': { outline: 'none' },
  '.cm-scroller': { fontFamily: 'var(--font-mono)', lineHeight: '1.6', minHeight: '168px' },
  '.cm-content': { caretColor: 'var(--accent)', padding: '8px 0' },
  '.cm-gutters': { backgroundColor: 'var(--bg-primary)', color: 'var(--text-tertiary)', border: 'none', paddingLeft: '4px' },
  '.cm-activeLine': { backgroundColor: 'var(--accent-surface)' },
  '.cm-activeLineGutter': { backgroundColor: 'transparent', color: 'var(--text-secondary)' },
  '.cm-cursor': { borderLeftColor: 'var(--accent)' },
  '&.cm-focused .cm-selectionBackground, .cm-selectionBackground, ::selection': { backgroundColor: 'var(--accent-glow) !important' },
  '.cm-placeholder': { color: 'var(--text-tertiary)' },
  '.cm-matchingBracket': { backgroundColor: 'var(--accent-glow)', outline: 'none' },
})

/** CodeMirror 6 editor: line numbers, syntax highlighting, Tab to indent (Esc then Tab leaves). */
export default function CodeEditor({ value, onChange, language, onSubmit, placeholder, ariaLabel, disabled }: CodeEditorProps) {
  const host = useRef<HTMLDivElement>(null)
  const view = useRef<EditorView | null>(null)
  const langConf = useRef(new Compartment())
  const editableConf = useRef(new Compartment())
  const handlers = useRef({ onChange, onSubmit })
  useEffect(() => { handlers.current = { onChange, onSubmit } })

  // Create once
  useEffect(() => {
    if (!host.current) return
    const v = new EditorView({
      parent: host.current,
      state: EditorState.create({
        doc: value,
        extensions: [
          lineNumbers(), highlightActiveLineGutter(), highlightActiveLine(), drawSelection(),
          history(), indentOnInput(), bracketMatching(), indentUnit.of('    '),
          syntaxHighlighting(classHighlighter),
          keymap.of([
            { key: 'Mod-Enter', run: () => { handlers.current.onSubmit?.(); return true } },
            indentWithTab, ...defaultKeymap, ...historyKeymap,
          ]),
          placeholderExt(placeholder ?? ''),
          EditorView.contentAttributes.of({ 'aria-label': ariaLabel, 'aria-multiline': 'true' }),
          EditorView.updateListener.of((u) => { if (u.docChanged) handlers.current.onChange(u.state.doc.toString()) }),
          langConf.current.of([]),
          editableConf.current.of(EditorView.editable.of(!disabled)),
          theme,
        ],
      }),
    })
    view.current = v
    return () => { v.destroy(); view.current = null }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // External value changes (e.g. cleared after submit)
  useEffect(() => {
    const v = view.current
    if (v && v.state.doc.toString() !== value) {
      v.dispatch({ changes: { from: 0, to: v.state.doc.length, insert: value } })
    }
  }, [value])

  useEffect(() => {
    view.current?.dispatch({ effects: editableConf.current.reconfigure(EditorView.editable.of(!disabled)) })
  }, [disabled])

  useEffect(() => {
    let alive = true
    loadLanguage(language).then((support) => {
      if (alive) view.current?.dispatch({ effects: langConf.current.reconfigure(support ?? []) })
    })
    return () => { alive = false }
  }, [language])

  return <div ref={host} className="overflow-hidden" />
}
