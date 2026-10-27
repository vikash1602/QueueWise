import { useState } from 'react'
import { Link, NavLink } from 'react-router-dom'
import { useNotifications } from '../api/hooks'
import { useAuth, useIsOrgAdmin, useIsOrgStaff } from '../auth'
import { useLogout } from '../api/hooks'
import { Button } from './ui'

type NavItem = { to: string; label: string }

function useNavItems(): { items: NavItem[]; layout: 'console' | 'topbar' } {
  const isStaff = useIsOrgStaff()
  const isAdmin = useIsOrgAdmin()
  if (isAdmin) {
    return {
      layout: 'console',
      items: [
        { to: '/admin', label: 'Dashboard' },
        { to: '/staff', label: 'Live queue' },
        { to: '/admin/customers', label: 'Customers' },
        { to: '/admin/staff', label: 'Team' },
        { to: '/admin/settings', label: 'Services & hours' },
        { to: '/admin/analytics', label: 'Reports' },
        { to: '/admin/audit', label: 'Audit log' },
      ],
    }
  }
  if (isStaff) {
    return {
      layout: 'console',
      items: [
        { to: '/staff', label: 'Live queue' },
        { to: '/dashboard', label: 'My visits' },
        { to: '/organizations', label: 'Find services' },
      ],
    }
  }
  return {
    layout: 'topbar',
    items: [
      { to: '/organizations', label: 'Find services' },
      { to: '/dashboard', label: 'My visits' },
    ],
  }
}

function BrandMark({ compact = false }: { compact?: boolean }) {
  return (
    <Link to="/" className="flex items-center gap-2" aria-label="QueueWise home">
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent-500 text-sm font-bold text-white">
        Q
      </span>
      {!compact && (
        <span className="text-lg font-semibold tracking-tight">
          Queue<span className="text-accent-400">Wise</span>
        </span>
      )}
    </Link>
  )
}

function NotificationBell() {
  const { data: notifications } = useNotifications()
  const [open, setOpen] = useState(false)
  const unread = notifications?.unread_count ?? 0
  return (
    <div className="relative">
      <button
        aria-label={`Notifications (${unread} unread)`}
        className="relative rounded-lg p-2 text-slate-500 hover:bg-slate-100"
        onClick={() => setOpen((o) => !o)}
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 0 1-3.4 0" />
        </svg>
        {unread > 0 && (
          <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-semibold text-white">
            {unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 z-50 mt-2 w-80 rounded-xl border border-slate-200 bg-white p-2 shadow-lg">
          {(notifications?.results.length ?? 0) === 0 && (
            <p className="px-3 py-4 text-center text-sm text-slate-500">No notifications yet</p>
          )}
          {(notifications?.results ?? []).slice(0, 8).map((n) => (
            <div key={n.id} className={`rounded-lg px-3 py-2 ${n.is_read ? '' : 'bg-accent-50'}`}>
              <p className="text-sm font-medium text-slate-800">{n.title}</p>
              <p className="text-xs text-slate-500">{n.body}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function useHandleLogout(logout: () => Promise<void>, logoutMutation: { mutate: () => void }) {
  return async function () {
    await logout()
    logoutMutation.mutate()
    // Full page load so no cached data from the signed-in session remains.
    window.location.assign('/')
  }
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth()
  const { items, layout } = useNavItems()
  const logoutMutation = useLogout()
  const [drawerOpen, setDrawerOpen] = useState(false)
  const handleLogout = useHandleLogout(logout, logoutMutation)

  const identity = (
    <div className="flex items-center gap-2">
      <NotificationBell />
      <span className="hidden max-w-40 truncate text-sm text-slate-600 sm:block" title={user?.email}>
        {user?.email}
      </span>
      <Button variant="secondary" onClick={handleLogout}>
        Sign out
      </Button>
    </div>
  )

  if (layout === 'topbar') {
    return (
      <div className="min-h-screen">
        <header className="sticky top-0 z-40 border-b border-slate-200 bg-white">
          <div className="mx-auto flex h-14 max-w-6xl items-center gap-4 px-4">
            <BrandMark />
            <nav className="hidden items-center gap-1 md:flex" aria-label="Main">
              {items.map((l) => (
                <NavLink
                  key={l.to}
                  to={l.to}
                  className={({ isActive }) =>
                    `rounded-lg px-3 py-1.5 text-sm font-medium ${
                      isActive ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-100'
                    }`
                  }
                >
                  {l.label}
                </NavLink>
              ))}
            </nav>
            <div className="ml-auto flex items-center gap-2">{identity}</div>
          </div>
          <nav className="flex gap-1 overflow-x-auto border-t border-slate-100 px-4 py-2 md:hidden" aria-label="Main mobile">
            {items.map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                className={({ isActive }) =>
                  `whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium ${
                    isActive ? 'bg-brand-50 text-brand-700' : 'text-slate-600'
                  }`
                }
              >
                {l.label}
              </NavLink>
            ))}
          </nav>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
      </div>
    )
  }

  // Console layout: navy sidebar (desktop) + drawer (mobile).
  const navLinks = (onClick?: () => void) =>
    items.map((l) => (
      <NavLink
        key={l.to}
        to={l.to}
        onClick={onClick}
        className={({ isActive }) =>
          `flex items-center rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
            isActive ? 'bg-white/10 text-white' : 'text-brand-100 hover:bg-white/5 hover:text-white'
          }`
        }
      >
        {l.label}
      </NavLink>
    ))

  return (
    <div className="min-h-screen bg-slate-100">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-60 flex-col bg-brand-900 p-4 lg:flex">
        <div className="mb-8 mt-1 text-white">
          <BrandMark />
        </div>
        <nav className="flex flex-1 flex-col gap-1" aria-label="Console">
          {navLinks()}
        </nav>
        <div className="border-t border-white/10 pt-3 text-xs text-brand-200">
          <p className="truncate font-medium text-white">{user?.name || user?.email}</p>
          <p className="truncate">{user?.email}</p>
          <button onClick={handleLogout} className="mt-2 text-accent-300 hover:text-accent-200">
            Sign out
          </button>
        </div>
      </aside>

      {/* Mobile top bar with drawer */}
      <header className="sticky top-0 z-40 border-b border-slate-200 bg-brand-900 lg:hidden">
        <div className="flex h-14 items-center gap-3 px-4">
          <button
            aria-label="Open menu"
            aria-expanded={drawerOpen}
            className="rounded-lg p-2 text-white hover:bg-white/10"
            onClick={() => setDrawerOpen(true)}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <div className="text-white">
            <BrandMark />
          </div>
          <div className="ml-auto flex items-center gap-1 bg-brand-900 [&_span]:text-brand-100 [&_button]:border-brand-700 [&_button]:bg-brand-800 [&_button]:text-white">
            {identity}
          </div>
        </div>
      </header>

      {drawerOpen && (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true">
          <div className="absolute inset-0 bg-slate-900/50" onClick={() => setDrawerOpen(false)} />
          <div className="absolute inset-y-0 left-0 flex w-64 flex-col bg-brand-900 p-4">
            <div className="mb-8 text-white">
              <BrandMark />
            </div>
            <nav className="flex flex-1 flex-col gap-1" aria-label="Console mobile">
              {navLinks(() => setDrawerOpen(false))}
            </nav>
          </div>
        </div>
      )}

      <main className="px-4 py-6 lg:ml-60 lg:px-8 lg:py-8">{children}</main>
    </div>
  )
}
