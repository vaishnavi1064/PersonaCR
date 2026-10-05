import { Link } from 'react-router-dom'
import { LogoMark } from '../components/ui/Logo'
import { buttonClass } from '../components/ui/styles'

export default function NotFoundPage() {
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center gap-4 bg-canvas px-4 text-center">
      <LogoMark size={36} innerFill="var(--bg-primary)" />
      <h1 className="text-2xl font-bold tracking-tight text-fg">Page not found</h1>
      <p className="text-sm text-fg-3">That address doesn’t match anything in PersonaCR.</p>
      <div className="flex gap-2">
        <Link to="/" className={buttonClass('outline')}>Home</Link>
        <Link to="/repos" className={buttonClass('primary')}>Repositories</Link>
      </div>
    </div>
  )
}
