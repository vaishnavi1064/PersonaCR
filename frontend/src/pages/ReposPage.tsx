import { Link } from 'react-router-dom'
import { FolderGit2 } from 'lucide-react'
import PageHeader from '../components/ui/PageHeader'
import EmptyState from '../components/ui/EmptyState'
import { buttonClass } from '../components/ui/styles'

// Placeholder route for the app-shell slice. The real Repositories page
// (import, status, fingerprint chips, Open / Start chat / Reanalyze) is slice 2.
export default function ReposPage() {
  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:py-10">
      <PageHeader title="Repositories" description="Repos PersonaCR has learned your style from." />
      <EmptyState
        className="mt-8"
        icon={<FolderGit2 size={20} />}
        title="The repository view is being rebuilt"
        description="Importing and managing repos here comes in the next update. Until then, paste a GitHub repo URL into a chat to import it."
        action={<Link to="/chat" className={buttonClass('primary')}>Go to Chats</Link>}
      />
    </div>
  )
}
