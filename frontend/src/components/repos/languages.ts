// GitHub linguist colors for the languages the ingestor reads.
const COLORS: Record<string, string> = {
  python: '#3572A5', typescript: '#3178C6', javascript: '#F1E05A', go: '#00ADD8',
  java: '#B07219', rust: '#DEA584', ruby: '#701516', c: '#555555', cpp: '#F34B7D',
  csharp: '#178600', php: '#4F5D95', kotlin: '#A97BFF', swift: '#F05138', scala: '#C22D40',
}

const LABELS: Record<string, string> = {
  python: 'Python', typescript: 'TypeScript', javascript: 'JavaScript', go: 'Go', java: 'Java',
  rust: 'Rust', ruby: 'Ruby', c: 'C', cpp: 'C++', csharp: 'C#', php: 'PHP', kotlin: 'Kotlin',
  swift: 'Swift', scala: 'Scala',
}

export function languageColor(lang: string): string {
  return COLORS[lang.toLowerCase()] ?? 'var(--text-tertiary)'
}

export function languageLabel(lang: string): string {
  return LABELS[lang.toLowerCase()] ?? lang
}
