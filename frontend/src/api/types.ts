export interface Me {
  id: number
  email: string
  name: string
  phone: string
  role: string
  memberships: { organization_id: number; organization_name: string; role: string }[]
}

export interface Service {
  id: number
  name: string
  description: string
  duration_minutes: number
  buffer_minutes: number
  is_appointment_enabled: boolean
  is_walkin_enabled: boolean
  max_advance_days: number
  is_active: boolean
}

export interface Organization {
  id: number
  name: string
  slug: string
  description: string
  address: string
  contact_phone: string
  services_count?: number
  business_hours?: BusinessHours[]
  services?: Service[]
}

export interface BusinessHours {
  weekday: number
  opens_at: string
  closes_at: string
  is_closed: boolean
}

export interface Slot {
  slot_start: string
  slot_end: string
  is_available: boolean
}

export interface Appointment {
  id: number
  organization: number
  organization_name: string
  service: number
  service_name: string
  customer_email: string
  slot_start: string
  slot_end: string
  status: string
  queue_token: number | null
  cancel_reason: string
  created_at: string
}

export interface QueueEntry {
  id: number
  organization: number
  organization_name: string
  service: number
  service_name: string
  source: string
  token_number: number
  business_date: string
  status: string
  estimated_wait_minutes: number
  joined_at: string
  called_at: string | null
  started_at: string | null
  completed_at: string | null
  display_name: string
}

export interface QueueStatus {
  id: number
  token_number: number
  status: string
  position: number
  people_ahead: number
  estimated_wait_minutes: number
  now_serving: number[]
  service_name: string
  organization_name: string
  business_date: string
  updated_at: string
}

export interface NotificationItem {
  id: number
  type: string
  title: string
  body: string
  payload: Record<string, unknown>
  is_read: boolean
  created_at: string
}

export interface AnalyticsSummary {
  range: { from: string; to: string }
  total_appointments: number
  cancelled_appointments: number
  cancellation_rate: number | null
  customers_served: number
  no_show_count: number
  no_show_rate: number | null
  cancelled_queue_entries: number
  active_queue_size: number
  avg_wait_minutes: number | null
  avg_service_minutes: number | null
}

export interface TrendPoint {
  date: string
  queue_joined: number
  customers_served: number
  appointments: number
}

export interface AuditLogItem {
  id: number
  action: string
  object_type: string
  object_id: string
  detail: Record<string, unknown>
  actor_email: string | null
  created_at: string
}

export interface StaffMember {
  id: number
  user_id: number
  email: string
  name: string
  role: string
  is_active: boolean
  created_at: string
}

export const QUEUE_STATUS_LABELS: Record<string, string> = {
  WAITING: 'Waiting',
  CALLED: 'Called',
  IN_PROGRESS: 'In progress',
  COMPLETED: 'Completed',
  NO_SHOW: 'No-show',
  CANCELLED: 'Cancelled',
}

export const APPOINTMENT_STATUS_LABELS: Record<string, string> = {
  CONFIRMED: 'Confirmed',
  CHECKED_IN: 'Checked in',
  IN_PROGRESS: 'In progress',
  COMPLETED: 'Completed',
  CANCELLED: 'Cancelled',
  NO_SHOW: 'No-show',
}

export const WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
