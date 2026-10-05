import { LogOut, Moon, Sun } from 'lucide-react'
import GitHubMark from '../components/ui/GitHubMark'
import { useStore } from '../store/useStore'
import { useCurrentUser } from '../lib/useCurrentUser'
import { signInWithGitHub } from '../lib/supabase'
import { capabilities, type CapabilityLevel } from '../lib/api'
import PageHeader from '../components/ui/PageHeader'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Avatar from '../components/ui/Avatar'
import StatusPill, { type PillTone } from '../components/ui/StatusPill'
import AccentPicker from '../components/ui/AccentPicker'
import { cn } from '../lib/cn'

const LEVEL: Record<CapabilityLevel, { tone: PillTone; label: string }> = {
  available:   { tone: 'success', label: 'Available' },
  partial:     { tone: 'warning', label: 'Partial' },
  unavailable: { tone: 'neutral', label: 'Coming soon' },
}

export default function SettingsPage() {
  const theme = useStore((s) => s.theme)
  const toggleTheme = useStore((s) => s.toggleTheme)
  const { guestMode, displayName, initials, email, avatarUrl, githubLogin, signOut } = useCurrentUser()

  function pickTheme(next: 'dark' | 'light') {
    if (next === theme) return
    toggleTheme()
    document.documentElement.setAttribute('data-theme', next)
  }

  return (
    <div className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6 lg:py-10">
      <PageHeader title="Settings" description="Account, appearance, and which features are live." />

      <div className="mt-8 flex flex-col gap-5">
        <Section title="Account">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex min-w-0 items-center gap-3">
              <Avatar src={avatarUrl} initials={initials} size={44} />
              <div className="min-w-0">
                <p className="truncate font-medium text-fg">{displayName}</p>
                <p className="text-sm text-fg-3 sm:truncate">
                  {guestMode
                    ? 'Guest session — repos and chats are not saved'
                    : [githubLogin && `@${githubLogin}`, email].filter(Boolean).join(' · ')}
                </p>
              </div>
            </div>
            {guestMode ? (
              <Button variant="primary" icon={<GitHubMark size={15} />} onClick={() => signInWithGitHub()}>
                Sign in with GitHub
              </Button>
            ) : (
              <Button variant="danger" icon={<LogOut size={15} />} onClick={() => signOut()}>
                Sign out
              </Button>
            )}
          </div>
        </Section>

        <Section title="Appearance">
          <Field label="Theme">
            <div role="radiogroup" aria-label="Theme" className="inline-flex self-start rounded-lg border border-line p-0.5 sm:self-auto">
              {(['dark', 'light'] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  role="radio"
                  aria-checked={theme === t}
                  onClick={() => pickTheme(t)}
                  className={cn(
                    'flex h-8 items-center gap-2 rounded-md px-3 text-sm capitalize cursor-pointer',
                    theme === t ? 'bg-surface-hover text-fg shadow-[inset_0_0_0_1px_var(--border)]' : 'text-fg-3 hover:text-fg',
                  )}
                >
                  {t === 'dark' ? <Moon size={14} aria-hidden /> : <Sun size={14} aria-hidden />}
                  {t}
                </button>
              ))}
            </div>
          </Field>
          <Field label="Accent">
            <AccentPicker />
          </Field>
        </Section>

        <Section title="Feature status" description="Features waiting on backend work show a “coming soon” state in the app.">
          <ul className="-my-1 divide-y divide-line">
            {Object.values(capabilities).map((c) => (
              <li key={c.label} className="flex items-start justify-between gap-4 py-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-fg">{c.label}</p>
                  <p className="mt-0.5 text-[13px] text-fg-3">{c.detail}</p>
                </div>
                <StatusPill tone={LEVEL[c.level].tone}>{LEVEL[c.level].label}</StatusPill>
              </li>
            ))}
          </ul>
        </Section>
      </div>
    </div>
  )
}

function Section({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return (
    <Card className="p-5 sm:p-6">
      <h2 className="text-base font-semibold text-fg">{title}</h2>
      {description && <p className="mt-0.5 text-sm text-fg-3">{description}</p>}
      <div className="mt-4 flex flex-col gap-5">{children}</div>
    </Card>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
      <span className="text-sm text-fg-2">{label}</span>
      {children}
    </div>
  )
}
