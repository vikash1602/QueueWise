import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { useQueryClient } from '@tanstack/react-query'
import { useAppointments } from '../api/hooks'
import { APPOINTMENT_STATUS_LABELS } from '../api/types'
import AppShell from '../components/AppShell'
import { Button, Card, ErrorState, LoadingState, PageHeader, StatusBadge, useToast } from '../components/ui'

export default function AppointmentDetailPage() {
  const { id } = useParams()
  const { data: appointments, isLoading, isError, error } = useAppointments()
  const qc = useQueryClient()
  const toast = useToast()

  const appt = appointments?.find((a) => a.id === Number(id))

  if (isLoading) return <AppShell><LoadingState /></AppShell>
  if (isError) return <AppShell><ErrorState message={(error as Error).message} /></AppShell>
  if (!appt) return <AppShell><ErrorState message="Appointment not found." /></AppShell>

  const cancellable = ['CONFIRMED', 'CHECKED_IN'].includes(appt.status)

  async function cancel() {
    try {
      await api.post(`/api/appointments/${appt!.id}/cancel/`)
      await qc.invalidateQueries({ queryKey: ['appointments'] })
      toast.push('Appointment cancelled')
    } catch (err) {
      toast.push((err as Error).message, 'error')
    }
  }

  return (
    <AppShell>
      <PageHeader
        title={appt.service_name}
        subtitle={`at ${appt.organization_name}`}
        actions={cancellable ? <Button variant="danger" onClick={cancel}>Cancel appointment</Button> : undefined}
      />
      <Card className="max-w-lg divide-y divide-slate-100 p-2">
        {[
          ['Status', <StatusBadge key="s" status={appt.status} label={APPOINTMENT_STATUS_LABELS[appt.status]} />],
          ['When', new Date(appt.slot_start).toLocaleString()],
          ['Duration', `${Math.round((+new Date(appt.slot_end) - +new Date(appt.slot_start)) / 60000)} minutes`],
          ['Queue token', appt.queue_token ? `#${appt.queue_token}` : '— not checked in yet'],
        ].map(([label, value]) => (
          <div key={label as string} className="flex items-center justify-between px-3 py-3 text-sm">
            <span className="text-slate-500">{label}</span>
            <span className="font-medium text-slate-800">{value}</span>
          </div>
        ))}
      </Card>
      {appt.cancel_reason && (
        <p className="mt-4 max-w-lg text-sm text-slate-500">Cancellation reason: {appt.cancel_reason}</p>
      )}
      <Link to="/dashboard" className="mt-6 inline-block text-sm font-medium text-brand-600 hover:underline">
        ← Back to dashboard
      </Link>
    </AppShell>
  )
}
