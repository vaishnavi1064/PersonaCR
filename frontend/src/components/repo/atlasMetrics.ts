// Convention Atlas catalogue: every fingerprint field, grouped, with how it is
// measured (backend/src/core/pattern_extractor.py). Descriptions state what the
// extractor actually does, including its shortcuts.

export type MetricKind =
  | 'pct'      // 0–1 fraction → "79.0%"
  | 'ratio'    // unitless decimal, e.g. 0.083
  | 'lines'    // count of lines
  | 'chars'    // characters
  | 'count'    // integer count
  | 'score'    // decimal score
  | 'text'

export interface MetricDef {
  key: string
  label: string
  kind: MetricKind
  description: string
  /** Only measured for Python functions. */
  pythonOnly?: 'measured' | 'assumed'
}

export interface MetricGroup { id: string; title: string; metrics: MetricDef[] }

export const ATLAS_GROUPS: MetricGroup[] = [
  {
    id: 'size',
    title: 'Function size & complexity',
    metrics: [
      { key: 'total_functions', label: 'Functions measured', kind: 'count', description: 'Functions with at least one non-blank line. File-level chunks are excluded.' },
      { key: 'avg_function_length', label: 'Average function length', kind: 'lines', description: 'Mean non-blank lines per function.' },
      { key: 'max_function_length', label: 'Longest function', kind: 'lines', description: 'Non-blank lines in the longest function.' },
      { key: 'change_concentration_gini', label: 'Length concentration (Gini)', kind: 'ratio', description: 'Gini coefficient of function lengths: 0 = all functions similar in size, 1 = code concentrated in a few long functions.' },
      { key: 'avg_complexity', label: 'Estimated complexity', kind: 'score', description: 'Mean of 1 + branch keywords (if, elif, else, for, while, and, or, case, switch, catch, except) per function. An estimate, not true cyclomatic complexity.' },
    ],
  },
  {
    id: 'naming-typing',
    title: 'Naming & typing',
    metrics: [
      { key: 'naming_convention', label: 'Naming convention', kind: 'text', description: 'Most common style among function names (snake_case, camelCase or PascalCase).' },
      { key: 'type_hint_usage', label: 'Type hints', kind: 'pct', pythonOnly: 'assumed', description: 'Share of Python and TypeScript functions with a parameter or return annotation. Not measured for languages that always declare types (Java, Go, Rust, C#, Kotlin, C/C++) or for plain JavaScript.' },
    ],
  },
  {
    id: 'docs',
    title: 'Documentation & comments',
    metrics: [
      { key: 'docstring_coverage', label: 'Docstring coverage', kind: 'pct', description: 'Python: a docstring (from the AST). Other languages: a doc comment directly above the function — /** … */ or /// (Go: any // comment line).' },
      { key: 'comment_density', label: 'Comment density', kind: 'pct', description: 'Comment lines ÷ all lines, averaged per function.' },
      { key: 'comment_to_code_ratio', label: 'Comment-to-code ratio', kind: 'ratio', description: 'All comment lines ÷ all code lines, across every function.' },
      { key: 'inline_comment_ratio', label: 'Inline comments', kind: 'pct', description: 'Share of comments that share a line with code, rather than standing on their own line (whole-line comments and docstring lines).' },
    ],
  },
  {
    id: 'control',
    title: 'Error handling & control flow',
    metrics: [
      { key: 'error_handling_rate', label: 'Error handling', kind: 'pct', description: 'Share of functions containing try together with except or catch.' },
      { key: 'conditionals_per_100_lines', label: 'Conditionals per 100 lines', kind: 'score', description: 'Conditional keywords per 100 lines, averaged per function.' },
      { key: 'conditional_density', label: 'Conditional density', kind: 'ratio', description: 'Conditional keywords (if, elif, else, switch, case…) per line, averaged per function.' },
      { key: 'loop_density', label: 'Loop density', kind: 'ratio', description: 'for/while loops per line, averaged per function.' },
      { key: 'for_to_while_ratio', label: 'for vs while', kind: 'pct', description: 'Share of loops that are for loops (for ÷ all loops).' },
      { key: 'comprehension_ratio', label: 'Comprehensions', kind: 'pct', pythonOnly: 'measured', description: 'Comprehensions and generator expressions ÷ (those + explicit for loops), averaged over Python functions only (0 when the repo has none).' },
    ],
  },
  {
    id: 'format',
    title: 'Formatting',
    metrics: [
      { key: 'indentation_consistency', label: 'Indentation consistency', kind: 'pct', description: 'Share of functions using the repo’s dominant indentation (spaces or tabs).' },
      { key: 'primary_indent_depth', label: 'Average indent width', kind: 'chars', description: 'Mean leading spaces on indented lines, averaged per function.' },
      { key: 'avg_line_length', label: 'Average line length', kind: 'chars', description: 'Mean length of non-blank lines, averaged per function.' },
      { key: 'max_line_length', label: 'Longest line', kind: 'chars', description: 'Longest non-blank line in any function.' },
      { key: 'std_line_length', label: 'Line length spread', kind: 'chars', description: 'Standard deviation of line length, averaged per function.' },
      { key: 'lines_over_80', label: 'Lines over 80 chars', kind: 'pct', description: 'Share of lines longer than 80 characters, averaged per function.' },
      { key: 'lines_over_120', label: 'Lines over 120 chars', kind: 'pct', description: 'Share of lines longer than 120 characters, averaged per function.' },
    ],
  },
  {
    id: 'imports',
    title: 'Imports',
    metrics: [
      { key: 'import_density', label: 'Import density', kind: 'ratio', description: 'Import statements per line, across all files and functions.' },
      { key: 'wildcard_import_ratio', label: 'Wildcard imports', kind: 'pct', description: 'Share of imports of the form “from x import *”.' },
    ],
  },
]

/** Fields shown elsewhere on the page (languages, patterns) or not useful as rows. */
export const ATLAS_SPECIAL_KEYS = new Set(['languages', 'language_distribution', 'common_patterns', 'pattern_frequency', 'type_hint_functions', 'repo_summary', 'repo_summary_generated_at'])

export const PATTERN_LABEL: Record<string, string> = {
  early_return: 'Early return',
  builder: 'Builder',
  singleton: 'Singleton',
  custom_exceptions: 'Raises named exceptions',
  decorators: '@staticmethod / @classmethod / @property',
}

export function formatMetric(kind: MetricKind, v: unknown): { value: string; exact: string | null } {
  if (v == null) return { value: '—', exact: null }
  if (kind === 'text') return { value: String(v), exact: null }
  if (typeof v !== 'number' || !Number.isFinite(v)) return { value: String(v), exact: null }
  const raw = String(v)
  switch (kind) {
    case 'pct': return { value: `${(v * 100).toFixed(1)}%`, exact: raw }
    case 'count': return { value: v.toLocaleString('en-US'), exact: null }
    case 'lines': return { value: `${v.toLocaleString('en-US', { maximumFractionDigits: 1 })} lines`, exact: null }
    case 'chars': return { value: `${v.toLocaleString('en-US', { maximumFractionDigits: 1 })} chars`, exact: null }
    default: return { value: v.toLocaleString('en-US', { maximumFractionDigits: 3 }), exact: null }
  }
}
