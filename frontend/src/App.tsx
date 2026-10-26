import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { queryClient } from './queryClient'
import { api } from './api/client'
import { useMe } from './api/hooks'
import type { Me } from './api/types'
import { LoadingState } from './components/ui'
import LandingPage from './pages/LandingPage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import DiscoverPage from './pages/DiscoverPage'
import OrganizationPage from './pages/OrganizationPage'
import BookingPage from './pages/BookingPage'
import CustomerDashboardPage from './pages/CustomerDashboardPage'
import AppointmentDetailPage from './pages/AppointmentDetailPage'
import QueueTrackingPage from './pages/QueueTrackingPage'
import StaffDashboardPage from './pages/StaffDashboardPage'
import AdminSettingsPage from './pages/AdminSettingsPage'
import StaffManagementPage from './pages/StaffManagementPage'
import AnalyticsPage from './pages/AnalyticsPage'
import AuditLogPage from './pages/AuditLogPage'
import NotFoundPage from './pages/NotFoundPage'
import ForbiddenPage from './pages/ForbiddenPage'
import { AuthContext, type AuthValue } from './auth'

export default function App() {
  const { data: me, isLoading } = useMe()

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <LoadingState label="Starting QueueWise…" />
      </div>
    )
  }

  const auth: AuthValue = {
    user: me ?? null,
    async refresh() {
      await queryClient.invalidateQueries({ queryKey: ['me'] })
    },
    async logout() {
      await api.post('/api/auth/logout/')
      await queryClient.invalidateQueries()
    },
  }

  const memberships = me?.memberships ?? []
  const isStaff = memberships.length > 0
  const isAdmin = memberships.some((m) => m.role === 'ADMIN')

  return (
    <AuthContext.Provider value={auth}>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/organizations" element={<DiscoverPage />} />
        <Route path="/organizations/:orgId" element={<OrganizationPage />} />
        <Route path="/organizations/:orgId/book/:serviceId" element={<BookingPage />} />

        <Route
          path="/dashboard"
          element={<RequireAuth me={me}><CustomerDashboardPage /></RequireAuth>}
        />
        <Route
          path="/appointments/:id"
          element={<RequireAuth me={me}><AppointmentDetailPage /></RequireAuth>}
        />
        <Route
          path="/queue/:entryId"
          element={<RequireAuth me={me}><QueueTrackingPage /></RequireAuth>}
        />

        <Route
          path="/staff"
          element={<RequireAuth me={me} allow={isStaff}><StaffDashboardPage /></RequireAuth>}
        />
        <Route
          path="/admin/settings"
          element={<RequireAuth me={me} allow={isAdmin}><AdminSettingsPage /></RequireAuth>}
        />
        <Route
          path="/admin/staff"
          element={<RequireAuth me={me} allow={isAdmin}><StaffManagementPage /></RequireAuth>}
        />
        <Route
          path="/admin/analytics"
          element={<RequireAuth me={me} allow={isAdmin}><AnalyticsPage /></RequireAuth>}
        />
        <Route
          path="/admin/audit"
          element={<RequireAuth me={me} allow={isAdmin}><AuditLogPage /></RequireAuth>}
        />

        <Route path="/forbidden" element={<ForbiddenPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </AuthContext.Provider>
  )
}

function RequireAuth({
  me,
  allow = true,
  children,
}: {
  me: Me | undefined
  allow?: boolean
  children: React.ReactNode
}) {
  const location = useLocation()
  if (!me) return <Navigate to="/login" state={{ from: location.pathname }} replace />
  if (!allow) return <Navigate to="/forbidden" replace />
  return <>{children}</>
}
