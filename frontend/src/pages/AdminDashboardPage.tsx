import { Link } from 'react-router-dom'
import { useAdminOverview } from '../api/hooks'
import AppShell from '../components/AppShell'
import { Card, ErrorState, PageHeader, Skeleton, StatCard, Table } from '../components/ui'

const ACTION_LABELS: Record<string, string> = {
  QUEUE_JOINED: 'joined the queue',
  QUEUE_CALLED: 'called a customer',
  QUEUE_IN_PROGRESS: 'started a service',
  QUEUE_COMPLETED: 'completed a service',
  QUEUE_NO_SHOW: 'marked a no-show',
  QUEUE_CANCELLED: 'cancelled a queue entry',
  WALKIN_REGISTERED: 'registered a walk-in',
  APPOINTMENT_CREATED: 'booked an appointment',
  APPOINTMENT_CANCELLED: 'cancelled an appointment',
  APPOINTMENT_CHECKED_IN: 'checked in an appointment',
}

export default function AdminDashboardPage() {
  const { data, isLoading, isError, error, refetch } = useAdminOverview()

  if (isLoading) {
    return (
      <AppShell>
        <PageHeader title="Dashboard" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i} className="p-4">
              <Skeleton className="h-3 w-24" />
              <Skeleton className="mt-3 h-7 w-16" />
            </Card>
          ))}
        </div>
      </AppShell>
    )
  }
  if (isError) return <AppShell><ErrorState message={(error as Error).message} onRetry={refetch} /></AppShell>

  const d = data!
  return (
    <AppShell>
      <PageHeader
        title="Dashboard"
        subtitle={`Operating day ${d.today.business_date} · all metrics computed from stored records`}
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Customers" value={d.total_customers} hint="with visits on record" />
        <StatCard label="Staff members" value={d.total_staff} />
        <StatCard label="Appointments" value={d.total_appointments} hint="all time" />
        <StatCard label="Queue tickets" value={d.queue_volume_total} hint="all time" />
      </div>

      <h2 className="mb-3 mt-8 text-lg font-semibold">Today at a glance</h2>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        <StatCard label="Waiting" value={d.today.waiting} tone="warning" />
        <StatCard label="Called" value={d.today.called} />
        <StatCard label="In progress" value={d.today.in_progress} tone="accent" />
        <StatCard label="Completed" value={d.today.completed} tone="accent" />
        <StatCard label="No-shows" value={d.today.no_show} />
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-2">
        <section>
          <h2 className="mb-3 text-lg font-semibold">Service-level statistics</h2>
          <Table head={['Service', 'Completed', 'Avg duration', 'Waiting now']}>
            {d.service_stats.map((s) => (
              <tr key={s.service_id} className="hover:bg-slate-50">
                <td className="px-4 py-3 font-medium">{s.service_name}</td>
                <td className="px-4 py-3 tabular-nums">{s.completed_total}</td>
                <td className="px-4 py-3 tabular-nums">
                  {s.avg_service_minutes != null ? `${s.avg_service_minutes} min` : '—'}
                  <span className="ml-1 text-xs text-slate-400">(avg of completed)</span>
                </td>
                <td className="px-4 py-3 tabular-nums">{s.waiting_now}</td>
              </tr>
            ))}
          </Table>
          <p className="mt-2 text-xs text-slate-400">
            Last 7 days: {d.queue_joins_last_7_days} queue joins · {d.appointments_last_7_days} appointments booked
          </p>
        </section>

        <section>
          <h2 className="mb-3 text-lg font-semibold">Recent activity</h2>
          {d.recent_activity.length === 0 ? (
            <Card className="p-6 text-sm text-slate-500">No activity recorded yet.</Card>
          ) : (
            <Card className="divide-y divide-slate-100">
              {d.recent_activity.map((a) => (
                <div key={a.id} className="flex items-center justify-between gap-3 px-4 py-3 text-sm">
                  <div>
                    <p>
                      <span className="font-medium">{a.actor}</span>{' '}
                      <span className="text-slate-500">{ACTION_LABELS[a.action] ?? a.action.toLowerCase()}</span>
                    </p>
                    <p className="text-xs text-slate-400">
                      {a.object_type}#{a.object_id}
                    </p>
                  </div>
                  <span className="whitespace-nowrap text-xs text-slate-400">
                    {new Date(a.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
              ))}
            </Card>
          )}
          <Link to="/admin/audit" className="mt-3 inline-block text-sm font-medium text-brand-600 hover:underline">
            View full audit history →
          </Link>
        </section>
      </div>
    </AppShell>
  )
}
