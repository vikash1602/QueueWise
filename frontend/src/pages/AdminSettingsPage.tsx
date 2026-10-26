import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { useMyBusinessHours, useMyOrganization, useMyServices } from '../api/hooks'
import type { Service } from '../api/types'
import { WEEKDAYS } from '../api/types'
import AppShell from '../components/AppShell'
import {
  Button, Card, ErrorState, Field, Input, LoadingState, Modal, PageHeader, StatusBadge, Textarea, useToast,
} from '../components/ui'

export default function AdminSettingsPage() {
  const org = useMyOrganization()
  const services = useMyServices()
  const hours = useMyBusinessHours()
  const qc = useQueryClient()
  const [tab, setTab] = useState<'organization' | 'services' | 'hours'>('organization')

  function refresh() {
    qc.invalidateQueries({ queryKey: ['myOrg'] })
    qc.invalidateQueries({ queryKey: ['myServices'] })
    qc.invalidateQueries({ queryKey: ['myHours'] })
  }

  if (org.isLoading) return <AppShell><LoadingState /></AppShell>
  if (org.isError) return <AppShell><ErrorState message={(org.error as Error).message} /></AppShell>

  return (
    <AppShell>
      <PageHeader title="Organization settings" subtitle={org.data?.name} />
      <div className="mb-6 flex rounded-lg border border-slate-300 p-0.5">
        {(['organization', 'services', 'hours'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded-md px-4 py-1.5 text-sm font-medium capitalize ${
              tab === t ? 'bg-brand-600 text-white' : 'text-slate-600'
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === 'organization' && <OrganizationForm org={org.data!} onSaved={refresh} />}
      {tab === 'services' && <ServicesPanel services={services.data ?? []} onSaved={refresh} />}
      {tab === 'hours' && <HoursForm hours={hours.data ?? []} onSaved={refresh} />}
    </AppShell>
  )
}

function OrganizationForm({ org, onSaved }: { org: { name: string; description: string; contact_email: string; contact_phone: string; address: string; timezone: string }; onSaved: () => void }) {
  const [form, setForm] = useState(org)
  const toast = useToast()
  const save = useMutation({
    mutationFn: () => api.put('/api/my/organization/', form),
    onSuccess: () => {
      toast.push('Organization updated')
      onSaved()
    },
    onError: (e) => toast.push((e as Error).message, 'error'),
  })

  return (
    <Card className="max-w-xl p-6">
      <div className="space-y-4">
        <Field label="Name">
          <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </Field>
        <Field label="Description">
          <Textarea rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Contact email">
            <Input type="email" value={form.contact_email} onChange={(e) => setForm({ ...form, contact_email: e.target.value })} />
          </Field>
          <Field label="Contact phone">
            <Input value={form.contact_phone} onChange={(e) => setForm({ ...form, contact_phone: e.target.value })} />
          </Field>
        </div>
        <Field label="Address">
          <Input value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />
        </Field>
        <Button onClick={() => save.mutate()} loading={save.isPending}>Save changes</Button>
      </div>
    </Card>
  )
}

function ServicesPanel({ services, onSaved }: { services: (Service & { counters: [] })[]; onSaved: () => void }) {
  const toast = useToast()
  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState<Service | null>(null)
  const [form, setForm] = useState({ name: '', description: '', duration_minutes: 15, buffer_minutes: 0, is_appointment_enabled: true, is_walkin_enabled: true, max_advance_days: 14 })

  const create = useMutation({
    mutationFn: () => api.post('/api/my/services/', form),
    onSuccess: () => {
      toast.push('Service created')
      setCreating(false)
      onSaved()
    },
    onError: (e) => toast.push((e as Error).message, 'error'),
  })
  const update = useMutation({
    mutationFn: () => api.patch(`/api/my/services/${editing!.id}/`, form),
    onSuccess: () => {
      toast.push('Service updated')
      setEditing(null)
      onSaved()
    },
    onError: (e) => toast.push((e as Error).message, 'error'),
  })
  const deactivate = useMutation({
    mutationFn: (id: number) => api.delete(`/api/my/services/${id}/`),
    onSuccess: () => {
      toast.push('Service deactivated')
      onSaved()
    },
    onError: (e) => toast.push((e as Error).message, 'error'),
  })

  function openCreate() {
    setForm({ name: '', description: '', duration_minutes: 15, buffer_minutes: 0, is_appointment_enabled: true, is_walkin_enabled: true, max_advance_days: 14 })
    setCreating(true)
  }
  function openEdit(svc: Service) {
    setForm({ ...svc })
    setEditing(svc)
  }

  return (
    <div>
      <Button className="mb-4" onClick={openCreate}>New service</Button>
      <div className="space-y-3">
        {services.map((svc) => (
          <Card key={svc.id} className="flex flex-wrap items-center justify-between gap-4 p-5">
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-medium">{svc.name}</h3>
                {!svc.is_active && <StatusBadge status="CANCELLED" label="Inactive" />}
              </div>
              <p className="text-sm text-slate-500">
                {svc.duration_minutes} min{svc.buffer_minutes ? ` + ${svc.buffer_minutes} buffer` : ''}
                {' · '}
                {svc.is_appointment_enabled ? 'appointments' : 'no appointments'}
                {' · '}
                {svc.is_walkin_enabled ? 'walk-in' : 'no walk-in'}
              </p>
            </div>
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => openEdit(svc)}>Edit</Button>
              {svc.is_active && (
                <Button variant="ghost" className="text-red-600" onClick={() => deactivate.mutate(svc.id)}>
                  Deactivate
                </Button>
              )}
            </div>
          </Card>
        ))}
      </div>

      <Modal
        open={creating || editing !== null}
        title={editing ? `Edit ${editing.name}` : 'New service'}
        onClose={() => { setCreating(false); setEditing(null) }}
        footer={
          <>
            <Button variant="secondary" onClick={() => { setCreating(false); setEditing(null) }}>Cancel</Button>
            <Button
              loading={create.isPending || update.isPending}
              onClick={() => (editing ? update.mutate() : create.mutate())}
            >
              {editing ? 'Save' : 'Create'}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Field label="Name">
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </Field>
          <Field label="Description">
            <Textarea rows={2} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </Field>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Duration (minutes)">
              <Input type="number" min={1} value={form.duration_minutes} onChange={(e) => setForm({ ...form, duration_minutes: Number(e.target.value) })} />
            </Field>
            <Field label="Buffer (minutes)">
              <Input type="number" min={0} value={form.buffer_minutes} onChange={(e) => setForm({ ...form, buffer_minutes: Number(e.target.value) })} />
            </Field>
          </div>
          <div className="flex gap-6">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={form.is_appointment_enabled} onChange={(e) => setForm({ ...form, is_appointment_enabled: e.target.checked })} />
              Appointments enabled
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={form.is_walkin_enabled} onChange={(e) => setForm({ ...form, is_walkin_enabled: e.target.checked })} />
              Walk-in enabled
            </label>
          </div>
        </div>
      </Modal>
    </div>
  )
}

function HoursForm({ hours, onSaved }: { hours: { weekday: number; opens_at: string; closes_at: string; is_closed: boolean }[]; onSaved: () => void }) {
  const [rows, setRows] = useState(() =>
    WEEKDAYS.map((_, i) => hours.find((h) => h.weekday === i) ?? { weekday: i, opens_at: '09:00', closes_at: '17:00', is_closed: false }),
  )
  const toast = useToast()
  const save = useMutation({
    mutationFn: () => api.put('/api/my/business-hours/', rows),
    onSuccess: () => {
      toast.push('Operating hours saved')
      onSaved()
    },
    onError: (e) => toast.push((e as Error).message, 'error'),
  })

  function update(i: number, patch: Partial<(typeof rows)[0]>) {
    setRows(rows.map((r, idx) => (idx === i ? { ...r, ...patch } : r)))
  }

  return (
    <Card className="max-w-xl divide-y divide-slate-100 p-2">
      {rows.map((row, i) => (
        <div key={row.weekday} className="flex flex-wrap items-center gap-3 p-3">
          <span className="w-24 text-sm font-medium">{WEEKDAYS[row.weekday]}</span>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={row.is_closed}
              onChange={(e) => update(i, { is_closed: e.target.checked })}
              aria-label={`${WEEKDAYS[row.weekday]} closed`}
            />
            Closed
          </label>
          {!row.is_closed && (
            <>
              <Input type="time" className="w-32" value={row.opens_at} onChange={(e) => update(i, { opens_at: e.target.value })} aria-label="opens" />
              <span className="text-slate-400">–</span>
              <Input type="time" className="w-32" value={row.closes_at} onChange={(e) => update(i, { closes_at: e.target.value })} aria-label="closes" />
            </>
          )}
        </div>
      ))}
      <div className="p-3">
        <Button onClick={() => save.mutate()} loading={save.isPending}>Save hours</Button>
      </div>
    </Card>
  )
}
