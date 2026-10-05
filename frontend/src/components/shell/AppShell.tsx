import { useEffect, useState } from 'react'
import { Outlet } from 'react-router-dom'
import NavSidebar from './NavSidebar'
import TopBar from './TopBar'

/** Signed-in layout: sidebar (drawer below lg) + top bar + routed page. */
export default function AppShell() {
  const [drawerOpen, setDrawerOpen] = useState(false)

  useEffect(() => {
    if (!drawerOpen) return
    function onKey(e: KeyboardEvent) { if (e.key === 'Escape') setDrawerOpen(false) }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [drawerOpen])

  const close = () => setDrawerOpen(false)

  return (
    <div className="flex h-dvh overflow-hidden bg-canvas text-fg">
      <NavSidebar className="hidden lg:flex" />

      {drawerOpen && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <div className="absolute inset-0 bg-black/50" onClick={close} aria-hidden />
          <NavSidebar className="relative z-10 shadow-pop" onNavigate={close} onClose={close} />
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar onOpenMenu={() => setDrawerOpen(true)} />
        <main className="relative min-h-0 flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
