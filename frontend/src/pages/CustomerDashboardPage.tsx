import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { useAppointments, useMyQueue } from '../api/hooks'
import { APPOINTMENT_STATUS_LABELS, QUEUE_STATUS_LABELS } from '../api/types'
import AppShell from '../components/AppShell'
import { Button, Card, EmptyState, LoadingState, PageHeader, StatusBadge, Table, useToast } from '../components/ui'

export default function CustomerDashboardPage() {
  const upcoming = useAppointments('upcoming')
  const past = useAppointments('past')
  const activeQueue = useMyQueue('active')
  const toast = useToast()

  async function cancelAppointment(id: number) {
    try {
      await api.post(`/api/appointments/${id}/cancel/`)
      toast.push('Appointment cancelled')
    } catch (err) {
      toast.push((err as Error).message, 'error')
    }
  }

  return (
    <AppShell>
      <PageHeader
        title="My dashboard"
        subtitle="Your appointments and live queue entries."
        actions={
          <Link to="/organizations">
            <Button>Book something new</Button>
          </Link>
        }
      />

      <section className="mb-10">
        <h2 className="mb-3 text-lg font-semibold">Active queue</h2>
        {activeQueue.isLoading && <LoadingState />}
        {activeQueue.data?.length === 0 && (
          <EmptyState title="Not in any queue right now" description="Join a walk-in queue from an organization page." />
        )}
        <div className="grid gap-4 sm:grid-cols-2">
          {(activeQueue.data ?? [])
            .filter((e) => ['WAITING', 'CALLED'].includes(e.status))
            .map((entry) => (
              <Link key={entry.id} to={`/queue/${entry.id}`}>
                <Card className="p-5 transition-shadow hover:shadow-md">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-2xl font-bold text-brand-700">
                      #{entry.token_number}
                    </span>
                    <StatusBadge status={entry.status} label={QUEUE_STATUS_LABELS[entry.status]} />
                  </div>
                  <p className="mt-2 font-medium text-slate-800">{entry.service_name}</p>
                  <p className="text-sm text-slate-500">{entry.organization_name}</p>
                  <p className="mt-2 text-sm text-slate-600">
                    Est. wait ≈ <span className="font-medium">{entry.estimated_wait_minutes} min</span> (estimate)
                  </p>
                </Card>
              </Link>
            ))}
        </div>
      </section>

      <section className="mb-10">
        <h2 className="mb-3 text-lg font-semibold">Upcoming appointments</h2>
        {upcoming.isLoading && <LoadingState />}
        {upcoming.data?.length === 0 && (
          <EmptyState title="No upcoming appointments" description="Browse organizations to book your next visit." />
        )}
        {upcoming.data && upcoming.data.length > 0 && (
          <Table head={['Service', 'When', 'Status', 'Actions']}>
            {upcoming.data.map((appt) => (
              <tr key={appt.id} className="hover:bg-slate-50">
                <td className="px-4 py-3">
                  <Link to={`/appointments/${appt.id}`} className="font-medium text-brand-600 hover:underline">
                    {appt.service_name}
                  </Link>
                  <p className="text-xs text-slate-500">{appt.organization_name}</p>
                </td>
                <td className="px-4 py-3">{new Date(appt.slot_start).toLocaleString()}</td>
                <td className="px-4 py-3">
                  <StatusBadge status={appt.status} label={APPOINTMENT_STATUS_LABELS[appt.status]} />
                </td>
                <td className="px-4 py-3">
                  <Button variant="secondary" onClick={() => cancelAppointment(appt.id)}>
                    Cancel
                  </Button>
                </td>
              </tr>
            ))}
          </Table>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">History</h2>
        {past.isLoading && <LoadingState />}
        {past.data?.length === 0 && <p className="text-sm text-slate-500">Nothing here yet.</p>}
        {past.data && past.data.length > 0 && (
          <Table head={['Service', 'When', 'Status']}>
            {past.data.map((appt) => (
              <tr key={appt.id} className="hover:bg-slate-50">
                <td className="px-4 py-3">
                  <Link to={`/appointments/${appt.id}`} className="text-brand-600 hover:underline">
                    {appt.service_name}
                  </Link>
                </td>
                <td className="px-4 py-3">{new Date(appt.slot_start).toLocaleString()}</td>
                <td className="px-4 py-3">
                  <StatusBadge status={appt.status} label={APPOINTMENT_STATUS_LABELS[appt.status]} />
                </td>
              </tr>
            ))}
          </Table>
        )}
      </section>
    </AppShell>
  )
}
