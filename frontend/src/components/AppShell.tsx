import { useState } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useNotifications, useLogout } from '../api/hooks'
import { useAuth, useIsOrgAdmin, useIsOrgStaff } from '../auth'
import { Button, useToast } from './ui'

export default function AppShell({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth()
  const isStaff = useIsOrgStaff()
  const isAdmin = useIsOrgAdmin()
  const navigate = useNavigate()
  const toast = useToast()
  const logoutMutation = useLogout()
  const { data: notifications } = useNotifications()
  const [bellOpen, setBellOpen] = useState(false)

  const links = [
    { to: '/organizations', label: 'Find services' },
    { to: '/dashboard', label: 'My dashboard' },
    ...(isStaff ? [{ to: '/staff', label: 'Staff console' }] : []),
    ...(isAdmin
      ? [
          { to: '/admin/analytics', label: 'Analytics' },
          { to: '/admin/settings', label: 'Settings' },
          { to: '/admin/staff', label: 'Team' },
          { to: '/admin/audit', label: 'Audit log' },
        ]
      : []),
  ]

  async function handleLogout() {
    await logout()
    logoutMutation.mutate()
    toast.push('Signed out')
    navigate('/')
  }

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-4 px-4">
          <Link to="/" className="text-lg font-bold tracking-tight text-brand-700">
            Queue<span className="text-slate-900">Wise</span>
          </Link>
          <nav className="hidden items-center gap-1 md:flex">
            {links.map((l) => (
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
          <div className="ml-auto flex items-center gap-2">
            <div className="relative">
              <button
                aria-label={`Notifications (${notifications?.unread_count ?? 0} unread)`}
                className="relative rounded-lg p-2 text-slate-500 hover:bg-slate-100"
                onClick={() => setBellOpen((o) => !o)}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 0 1-3.4 0" />
                </svg>
                {(notifications?.unread_count ?? 0) > 0 && (
                  <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-semibold text-white">
                    {notifications!.unread_count}
                  </span>
                )}
              </button>
              {bellOpen && (
                <div className="absolute right-0 mt-2 w-80 rounded-xl border border-slate-200 bg-white p-2 shadow-lg">
                  {(notifications?.results.length ?? 0) === 0 && (
                    <p className="px-3 py-4 text-center text-sm text-slate-500">No notifications yet</p>
                  )}
                  {(notifications?.results ?? []).slice(0, 8).map((n) => (
                    <div key={n.id} className={`rounded-lg px-3 py-2 ${n.is_read ? '' : 'bg-brand-50'}`}>
                      <p className="text-sm font-medium text-slate-800">{n.title}</p>
                      <p className="text-xs text-slate-500">{n.body}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <span className="hidden text-sm text-slate-600 sm:block">{user?.email}</span>
            <Button variant="secondary" onClick={handleLogout}>
              Sign out
            </Button>
          </div>
        </div>
        <nav className="flex gap-1 overflow-x-auto border-t border-slate-100 px-4 py-2 md:hidden">
          {links.map((l) => (
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
