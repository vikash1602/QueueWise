import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { useAvailability, useOrganization } from '../api/hooks'
import type { Appointment, Slot } from '../api/types'
import AppShell from '../components/AppShell'
import { Button, Card, ErrorState, LoadingState, Modal, PageHeader, useToast } from '../components/ui'

function localDateStr(offsetDays = 0): string {
  const d = new Date()
  d.setDate(d.getDate() + offsetDays)
  return d.toISOString().slice(0, 10)
}

export default function BookingPage() {
  const { orgId, serviceId } = useParams()
  const [dayOffset, setDayOffset] = useState(0)
  const date = useMemo(() => localDateStr(dayOffset), [dayOffset])
  const { data: org } = useOrganization(orgId)
  const { data: availability, isLoading, isError, error } = useAvailability(
    Number(orgId),
    Number(serviceId),
    date,
  )
  const [selected, setSelected] = useState<Slot | null>(null)
  const [confirming, setConfirming] = useState(false)
  const [booking, setBooking] = useState(false)
  const [bookError, setBookError] = useState<string | null>(null)
  const navigate = useNavigate()
  const toast = useToast()

  const service = org?.services?.find((s) => s.id === Number(serviceId))
  const slots = availability?.slots ?? []

  async function confirmBooking() {
    if (!selected) return
    setBooking(true)
    setBookError(null)
    try {
      const appt = await api.post<Appointment>('/api/appointments/', {
        service: Number(serviceId),
        slot_start: selected.slot_start,
      })
      setConfirming(false)
      toast.push('Appointment confirmed')
      navigate(`/appointments/${appt.id}`)
    } catch (err) {
      setBookError((err as Error).message)
    } finally {
      setBooking(false)
    }
  }

  return (
    <AppShell>
      <PageHeader
        title={`Book: ${service?.name ?? 'Service'}`}
        subtitle={`at ${org?.name ?? ''} — choose an available slot`}
      />
      <div className="mb-4 flex items-center gap-2">
        <Button variant="secondary" onClick={() => setDayOffset((d) => Math.max(0, d - 1))} disabled={dayOffset === 0}>
          ← Previous day
        </Button>
        <span className="px-2 font-medium">{date}</span>
        <Button variant="secondary" onClick={() => setDayOffset((d) => d + 1)}>
          Next day →
        </Button>
      </div>

      {isLoading && <LoadingState label="Loading availability…" />}
      {isError && <ErrorState message={(error as Error).message} />}
      {!isLoading && slots.length === 0 && (
        <Card className="p-8 text-center text-sm text-slate-500">
          No bookable slots on this day — the organization may be closed or fully past.
        </Card>
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
        {slots.map((slot) => {
          const time = new Date(slot.slot_start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          return (
            <button
              key={slot.slot_start}
              disabled={!slot.is_available}
              onClick={() => setSelected(slot)}
              className={`rounded-lg border px-3 py-3 text-sm font-medium transition-colors ${
                !slot.is_available
                  ? 'cursor-not-allowed border-slate-100 bg-slate-50 text-slate-300 line-through'
                  : selected === slot
                    ? 'border-brand-600 bg-brand-600 text-white'
                    : 'border-slate-300 bg-white text-slate-700 hover:border-brand-400'
              }`}
            >
              {time}
            </button>
          )
        })}
      </div>

      {selected && (
        <Card className="mt-6 flex flex-wrap items-center justify-between gap-4 p-5">
          <div>
            <p className="font-medium">
              Selected: {new Date(selected.slot_start).toLocaleString([], { weekday: 'long', hour: '2-digit', minute: '2-digit' })}
            </p>
            <p className="text-sm text-slate-500">{service?.name} · {service?.duration_minutes} minutes</p>
          </div>
          <Button onClick={() => setConfirming(true)}>Confirm booking</Button>
        </Card>
      )}

      <Modal
        open={confirming}
        title="Confirm your appointment"
        onClose={() => setConfirming(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setConfirming(false)}>Back</Button>
            <Button onClick={confirmBooking} loading={booking}>Book now</Button>
          </>
        }
      >
        {selected && (
          <>
            <p>{service?.name} at {new Date(selected.slot_start).toLocaleString()}.</p>
            <p className="mt-2">You can cancel from your dashboard if plans change.</p>
          </>
        )}
        {bookError && <p className="mt-3 text-sm text-red-600">{bookError}</p>}
      </Modal>
    </AppShell>
  )
}
