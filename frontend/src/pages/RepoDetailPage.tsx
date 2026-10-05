import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, FileCode2 } from 'lucide-react'
import { useStore } from '../store/useStore'
import PageHeader from '../components/ui/PageHeader'
import EmptyState from '../components/ui/EmptyState'
import Button from '../components/ui/Button'
import { buttonClass } from '../components/ui/styles'

// Route target for "Open" on a repo card. The full page (summary, Convention
// Atlas, chats, reviews) is a later slice of the redesign.
export default function RepoDetailPage() {
  const { owner = '', name = '' } = useParams()
  const navigate = useNavigate()
  const requestNewChat = useStore((s) => s.requestNewChat)
  const url = `https://github.com/${owner}/${name}`

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-8 sm:px-6 lg:py-10">
      <Link to="/repos" className="mb-4 inline-flex items-center gap-1.5 text-sm text-fg-3 hover:text-fg">
        <ArrowLeft size={14} aria-hidden /> Repositories
      </Link>
      <PageHeader
        title={name}
        description={<a href={url} target="_blank" rel="noreferrer" className="hover:underline">{owner}/{name}</a>}
        actions={<Button variant="primary" onClick={() => { requestNewChat(url); navigate('/chat') }}>Start chat</Button>}
      />
      <EmptyState
        className="mt-8"
        icon={<FileCode2 size={20} />}
        title="The repo page is next in the redesign"
        description="Its summary, full Convention Atlas, chats and reviews will live here. The repo card already shows its fingerprint highlights."
        action={<Link to="/repos" className={buttonClass('outline')}>Back to repositories</Link>}
      />
    </div>
  )
}
