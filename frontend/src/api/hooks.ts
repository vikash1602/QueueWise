import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'
import type {
  AnalyticsSummary,
  Appointment,
  AuditLogItem,
  Me,
  NotificationItem,
  Organization,
  QueueEntry,
  QueueStatus,
  Service,
  Slot,
  StaffMember,
  TrendPoint,
} from './types'

export const keys = {
  me: ['me'] as const,
  orgs: (search: string) => ['orgs', search] as const,
  org: (id: number | string) => ['org', id] as const,
  availability: (orgId: number | string, serviceId: number | string, date: string) =>
    ['availability', orgId, serviceId, date] as const,
  appointments: (scope: string) => ['appointments', scope] as const,
  myQueue: (scope: string) => ['myQueue', scope] as const,
  queueStatus: (id: number) => ['queueStatus', id] as const,
  notifications: (unread: boolean) => ['notifications', unread] as const,
  myOrg: () => ['myOrg'] as const,
  myServices: () => ['myServices'] as const,
  myHours: () => ['myHours'] as const,
  myStaff: () => ['myStaff'] as const,
  staffQueue: (params: string) => ['staffQueue', params] as const,
  staffHistory: (date: string) => ['staffHistory', date] as const,
  analytics: (params: string) => ['analytics', params] as const,
  trends: (params: string) => ['trends', params] as const,
  peakHours: (params: string) => ['peakHours', params] as const,
  audit: (params: string) => ['audit', params] as const,
}

export function useMe() {
  return useQuery({
    queryKey: keys.me,
    queryFn: () => api.get<Me>('/api/auth/me/'),
    retry: false,
  })
}

export function useOrganizations(search: string) {
  return useQuery({
    queryKey: keys.orgs(search),
    queryFn: () =>
      api.get<{ results: Organization[] }>(
        `/api/organizations/${search ? `?search=${encodeURIComponent(search)}` : ''}`,
      ),
  })
}

export function useOrganization(id: number | string | undefined) {
  return useQuery({
    queryKey: keys.org(id ?? 'none'),
    queryFn: () => api.get<Organization>(`/api/organizations/${id}/`),
    enabled: id !== undefined,
  })
}

export function useAvailability(orgId: number, serviceId: number | null, date: string) {
  return useQuery({
    queryKey: keys.availability(orgId, serviceId ?? 'none', date),
    queryFn: () =>
      api.get<{ slots: Slot[] }>(
        `/api/organizations/${orgId}/availability/?service=${serviceId}&date=${date}`,
      ),
    enabled: serviceId !== null,
  })
}

export function useAppointments(scope = '') {
  return useQuery({
    queryKey: keys.appointments(scope),
    queryFn: () => api.get<Appointment[]>(`/api/appointments/${scope ? `?scope=${scope}` : ''}`),
  })
}

export function useMyQueue(scope = '') {
  return useQuery({
    queryKey: keys.myQueue(scope),
    queryFn: () => api.get<QueueEntry[]>(`/api/queue/entries/${scope ? `?scope=${scope}` : ''}`),
  })
}

export function useQueueStatus(id: number | null) {
  return useQuery({
    queryKey: keys.queueStatus(id ?? 0),
    queryFn: () => api.get<QueueStatus>(`/api/queue/entries/${id}/`),
    enabled: id !== null,
    refetchInterval: 5000,
  })
}

export function useNotifications(unread = false) {
  return useQuery({
    queryKey: keys.notifications(unread),
    queryFn: () =>
      api.get<{ unread_count: number; results: NotificationItem[] }>(
        `/api/notifications/${unread ? '?unread=1' : ''}`,
      ),
    refetchInterval: 15000,
  })
}

export function useMyOrganization() {
  return useQuery({
    queryKey: keys.myOrg(),
    queryFn: () =>
      api.get<{
        id: number
        name: string
        slug: string
        description: string
        contact_email: string
        contact_phone: string
        address: string
        timezone: string
        role: string
        business_hours: { weekday: number; opens_at: string; closes_at: string; is_closed: boolean }[]
      }>('/api/my/organization/'),
  })
}

export function useMyServices() {
  return useQuery({
    queryKey: keys.myServices(),
    queryFn: () => api.get<(Service & { counters: [] })[]>('/api/my/services/'),
  })
}

export function useMyBusinessHours() {
  return useQuery({
    queryKey: keys.myHours(),
    queryFn: () => api.get<{ weekday: number; opens_at: string; closes_at: string; is_closed: boolean }[]>(
      '/api/my/business-hours/',
    ),
  })
}

export function useMyStaff() {
  return useQuery({
    queryKey: keys.myStaff(),
    queryFn: () => api.get<StaffMember[]>('/api/my/staff/'),
  })
}

export function useStaffQueue(params: string) {
  return useQuery({
    queryKey: keys.staffQueue(params),
    queryFn: () =>
      api.get<{ business_date: string; results: QueueEntry[] }>(`/api/staff/queue/today/${params}`),
    refetchInterval: 10000,
  })
}

export function useStaffHistory(date: string) {
  return useQuery({
    queryKey: keys.staffHistory(date),
    queryFn: () =>
      api.get<QueueEntry[]>(`/api/staff/queue/history/${date ? `?date=${date}` : ''}`),
  })
}

export function useAnalyticsSummary(params: string) {
  return useQuery({
    queryKey: keys.analytics(params),
    queryFn: () => api.get<AnalyticsSummary>(`/api/my/analytics/summary/${params}`),
  })
}

export function useTrends(params: string) {
  return useQuery({
    queryKey: keys.trends(params),
    queryFn: () => api.get<{ trends: TrendPoint[] }>(`/api/my/analytics/trends/${params}`),
  })
}

export function useAuditLogs(params: string) {
  return useQuery({
    queryKey: keys.audit(params),
    queryFn: () => api.get<{ results: AuditLogItem[] }>(`/api/my/audit-logs/${params}`),
  })
}

export function useInvalidate() {
  const qc = useQueryClient()
  return (...keyGroups: string[][]) => keyGroups.forEach((k) => qc.invalidateQueries({ queryKey: k }))
}

export function useRegister() {
  return useMutation({
    mutationFn: (body: { email: string; name: string; password: string; password2: string }) =>
      api.post<Me>('/api/auth/register/', body),
  })
}

export function useLogin() {
  return useMutation({
    mutationFn: (body: { email: string; password: string }) =>
      api.post<Me>('/api/auth/login/', body),
  })
}

export function useLogout() {
  return useMutation({ mutationFn: () => api.post<void>('/api/auth/logout/') })
}
