import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { useMyServices, useStaffQueue, useStaffHistory, useStaffCheckIns } from '../api/hooks'
import type { QueueEntry } from '../api/types'
import { QUEUE_STATUS_LABELS } from '../api/types'
import AppShell from '../components/AppShell'
import {
  Button, Card, EmptyState, ErrorState, Field, Input, LoadingState, Modal, PageHeader,
  Select, StatCard, StatusBadge, Table, useToast,
} from '../components/ui'

export default function StaffDashboardPage() {
  const { data: services } = useMyServices()
  const [serviceId, setServiceId] = useState<number | 'all'>('all')
  const [view, setView] = useState<'today' | 'history'>('today')
  const [search, setSearch] = useState('')
  const toast = useToast()
  const qc = useQueryClient()
  const [walkInOpen, setWalkInOpen] = useState(false)
  const [entryToCancel, setEntryToCancel] = useState<QueueEntry | null>(null)

  const params = new URLSearchParams()
  if (serviceId !== 'all') params.set('service', String(serviceId))
  if (search) params.set('search', search)
  const today = useStaffQueue(params.toString() ? `?${params}` : '')
  const history = useStaffHistory('')
  // Org-scoped list of today's confirmed appointments awaiting check-in.
  const checkIns = useStaffCheckIns('')
  const checkinable = checkIns.data?.results ?? []

  function refresh() {
    qc.invalidateQueries({ queryKey: ['staffCheckIns'] })
    qc.invalidateQueries({ queryKey: ['staffQueue'] })
    qc.invalidateQueries({ queryKey: ['myQueue'] })
    qc.invalidateQueries({ queryKey: ['staffHistory'] })
  }

  const callNext = useMutation({
    mutationFn: (service: number) => api.post<QueueEntry>('/api/staff/queue/call-next/', { service }),
    onSuccess: (entry) => {
      toast.push(`Called token #${entry.token_number}`)
      refresh()
    },
    onError: (err) => toast.push((err as Error).message, 'error'),
  })

  const walkIn = useMutation({
    mutationFn: (body: { service: number; guest_name: string }) =>
      api.post<QueueEntry>('/api/staff/queue/walk-in/', body),
    onSuccess: (entry) => {
      toast.push(`Registered token #${entry.token_number}`)
      setWalkInOpen(false)
      refresh()
    },
    onError: (err) => toast.push((err as Error).message, 'error'),
  })

  const checkIn = useMutation({
    mutationFn: (appointmentId: number) =>
      api.post<QueueEntry>(`/api/staff/queue/check-in/${appointmentId}/`),
    onSuccess: (entry) => {
      toast.push(`Checked in — token #${entry.token_number}`)
      refresh()
    },
    onError: (err) => toast.push((err as Error).message, 'error'),
  })

  const action = useMutation({
    mutationFn: ({ entry, act }: { entry: QueueEntry; act: string }) =>
      api.post<QueueEntry>(`/api/staff/queue/entries/${entry.id}/${act}/`),
    onSuccess: (_data, vars) => {
      toast.push(
        vars.act === 'complete'
          ? `Service completed for #${vars.entry.token_number}`
          : `Token #${vars.entry.token_number} updated`,
      )
      refresh()
    },
    onError: (err) => toast.push((err as Error).message, 'error'),
  })

  const service = serviceId === 'all' ? services?.[0]?.id : serviceId
  const rows = view === 'today' ? (today.data?.results ?? []) : (history.data ?? [])

  return (
    <AppShell>
      <PageHeader
        title="Staff console"
        subtitle={today.data?.business_date ? `Operating day: ${today.data.business_date}` : undefined}
        actions={
          <>
            <Button variant="secondary" onClick={() => setWalkInOpen(true)}>
              Register walk-in
            </Button>
            <Button
              onClick={() => service && callNext.mutate(service)}
              loading={callNext.isPending}
              disabled={service === undefined}
            >
              Call next
            </Button>
          </>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="w-64">
          <Field label="Service">
            <Select
              value={serviceId === 'all' ? 'all' : String(serviceId)}
              onChange={(e) => setServiceId(e.target.value === 'all' ? 'all' : Number(e.target.value))}
            >
              <option value="all">All services</option>
              {(services ?? []).map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </Select>
          </Field>
        </div>
        {view === 'today' && (
          <div className="w-64">
            <Field label="Search">
              <Input placeholder="Name or email…" value={search} onChange={(e) => setSearch(e.target.value)} />
            </Field>
          </div>
        )}
        <div className="ml-auto flex rounded-lg border border-slate-300 p-0.5">
          {(['today', 'history'] as const).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`rounded-md px-3 py-1.5 text-sm font-medium capitalize ${
                view === v ? 'bg-brand-600 text-white' : 'text-slate-600'
              }`}
            >
              {v}
            </button>
          ))}
        </div>
      </div>

      {view === 'today' && rows.length > 0 && (
        <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatCard label="Waiting" value={rows.filter((r) => r.status === 'WAITING').length} tone="warning" />
          <StatCard label="Called" value={rows.filter((r) => r.status === 'CALLED').length} />
          <StatCard label="In progress" value={rows.filter((r) => r.status === 'IN_PROGRESS').length} tone="accent" />
          <StatCard label="Completed today" value={rows.filter((r) => r.status === 'COMPLETED').length} />
        </div>
      )}

      {checkinable.length > 0 && view === 'today' && (
        <Card className="mb-4 p-4">
          <p className="mb-2 text-sm font-medium text-slate-700">Arrived with an appointment? Check them in:</p>
          <div className="flex flex-wrap gap-2">
            {checkinable.slice(0, 6).map((appt) => (
              <Button key={appt.id} variant="secondary" onClick={() => checkIn.mutate(appt.id)}>
                Check in {appt.customer_name} · {appt.service_name} · {new Date(appt.slot_start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </Button>
            ))}
          </div>
        </Card>
      )}

      {today.isLoading && <LoadingState />}
      {today.isError && <ErrorState message={(today.error as Error).message} />}
      {rows.length === 0 && !today.isLoading && (
        <EmptyState
          title={view === 'today' ? 'Queue is empty' : 'No history yet'}
          description={view === 'today' ? 'Register a walk-in or wait for bookings.' : undefined}
        />
      )}

      {rows.length > 0 && (
        <Table head={['Token', 'Customer', 'Service', 'Status', 'Wait est.', view === 'today' ? 'Actions' : 'Completed']}>
          {rows.map((entry) => (
            <tr key={entry.id} className="hover:bg-slate-50">
              <td className="px-4 py-3 font-mono font-semibold">#{entry.token_number}</td>
              <td className="px-4 py-3">{entry.display_name}</td>
              <td className="px-4 py-3">{entry.service_name}</td>
              <td className="px-4 py-3">
                <StatusBadge status={entry.status} label={QUEUE_STATUS_LABELS[entry.status]} />
              </td>
              <td className="px-4 py-3 whitespace-nowrap text-slate-500">
                {new Date(entry.joined_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </td>
              <td className="px-4 py-3 tabular-nums">
                {['WAITING', 'CALLED'].includes(entry.status)
                  ? `${Math.max(0, Math.round((Date.now() - +new Date(entry.joined_at)) / 60000))} min`
                  : '—'}
              </td>
              <td className="px-4 py-3">
                {view === 'today' ? (
                  <div className="flex flex-wrap gap-1.5">
                    {entry.status === 'WAITING' && (
                      <Button className="!px-2.5 !py-1 text-xs" onClick={() => action.mutate({ entry, act: 'call' })}>
                        Call
                      </Button>
                    )}
                    {entry.status === 'CALLED' && (
                      <>
                        <Button className="!px-2.5 !py-1 text-xs" onClick={() => action.mutate({ entry, act: 'start' })}>
                          Start
                        </Button>
                        <Button variant="secondary" className="!px-2.5 !py-1 text-xs" onClick={() => action.mutate({ entry, act: 'no-show' })}>
                          No-show
                        </Button>
                        <Button variant="secondary" className="!px-2.5 !py-1 text-xs" onClick={() => action.mutate({ entry, act: 'cancel' })}>
                          Skip
                        </Button>
                      </>
                    )}
                    {entry.status === 'IN_PROGRESS' && (
                      <Button className="!px-2.5 !py-1 text-xs" onClick={() => action.mutate({ entry, act: 'complete' })}>
                        Complete
                      </Button>
                    )}
                    {['WAITING', 'CALLED'].includes(entry.status) && (
                      <Button variant="ghost" className="!px-2.5 !py-1 text-xs text-red-600" onClick={() => setEntryToCancel(entry)}>
                        Cancel
                      </Button>
                    )}
                  </div>
                ) : (
                  entry.completed_at && new Date(entry.completed_at).toLocaleTimeString()
                )}
              </td>
            </tr>
          ))}
        </Table>
      )}

      <Modal
        open={walkInOpen}
        title="Register walk-in"
        onClose={() => setWalkInOpen(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setWalkInOpen(false)}>Cancel</Button>
            <Button
              loading={walkIn.isPending}
              onClick={() =>
                walkIn.mutate({
                  service: Number((document.getElementById('walkin-service') as HTMLSelectElement)?.value),
                  guest_name: (document.getElementById('walkin-name') as HTMLInputElement)?.value ?? '',
                })
              }
            >
              Create token
            </Button>
          </>
        }
      >
        <WalkInForm services={services ?? []} error={walkIn.error ? (walkIn.error as Error).message : null} />
      </Modal>

      <Modal
        open={entryToCancel !== null}
        title={`Cancel token #${entryToCancel?.token_number}?`}
        onClose={() => setEntryToCancel(null)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setEntryToCancel(null)}>Keep entry</Button>
            <Button
              variant="danger"
              onClick={async () => {
                if (entryToCancel) await action.mutateAsync({ entry: entryToCancel, act: 'cancel' })
                setEntryToCancel(null)
              }}
            >
              Cancel entry
            </Button>
          </>
        }
      >
        <p>The customer will lose their place in today’s queue.</p>
      </Modal>
    </AppShell>
  )
}

function WalkInForm({ services, error }: { services: { id: number; name: string }[]; error: string | null }) {
  return (
    <div className="space-y-4">
      <Field label="Customer name">
        <Input id="walkin-name" placeholder="Guest name" />
      </Field>
      <Field label="Service">
        <Select id="walkin-service" defaultValue={services[0]?.id}>
          {services.map((s) => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </Select>
      </Field>
      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  )
}
