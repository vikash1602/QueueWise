import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { useOrganization } from '../api/hooks'
import type { QueueEntry } from '../api/types'
import { WEEKDAYS } from '../api/types'
import AppShell from '../components/AppShell'
import { Button, Card, ErrorState, LoadingState, Modal, PageHeader, StatusBadge, useToast } from '../components/ui'

export default function OrganizationPage() {
  const { orgId } = useParams()
  const { data: org, isLoading, isError, error, refetch } = useOrganization(orgId)

  if (isLoading) return <AppShell><LoadingState /></AppShell>
  if (isError) return <AppShell><ErrorState message={(error as Error).message} onRetry={refetch} /></AppShell>

  return (
    <AppShell>
      <PageHeader title={org!.name} subtitle={org!.description || undefined} />
      {org!.profile_incomplete && (
        <Card className="mb-6 border-amber-200 bg-amber-50 p-4 text-sm text-amber-700">
          This organization is completing its profile. Booking is fully functional —
          the business details shown here will be filled in by the organization.
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <h2 className="mb-3 text-lg font-semibold">Services</h2>
          {org!.services?.length === 0 && (
            <Card className="p-6 text-sm text-slate-500">This organization has not listed any services yet.</Card>
          )}
          <div className="space-y-3">
            {(org!.services ?? []).map((svc) => (
              <Card key={svc.id} className="flex flex-wrap items-center justify-between gap-4 p-5">
                <div>
                  <h3 className="font-medium text-slate-900">{svc.name}</h3>
                  <p className="text-sm text-slate-500">{svc.description || `About ${svc.duration_minutes} minutes`}</p>
                </div>
                <div className="flex flex-col items-end gap-2">
                  <p className="text-sm text-slate-500">
                    {svc.duration_minutes} min{svc.buffer_minutes ? ` + ${svc.buffer_minutes} min buffer` : ''}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {svc.is_appointment_enabled && (
                      <Link to={`/organizations/${orgId}/book/${svc.id}`}>
                        <Button>Book appointment</Button>
                      </Link>
                    )}
                    {svc.is_walkin_enabled && <JoinWalkInButton serviceId={svc.id} serviceName={svc.name} />}
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </div>

        <div>
          <h2 className="mb-3 text-lg font-semibold">Opening hours</h2>
          <Card className="divide-y divide-slate-100 p-2">
            {(org!.business_hours ?? []).map((h) => (
              <div key={h.weekday} className="flex items-center justify-between px-3 py-2 text-sm">
                <span className="text-slate-700">{WEEKDAYS[h.weekday]}</span>
                {h.is_closed ? (
                  <StatusBadge status="CANCELLED" label="Closed" />
                ) : (
                  <span className="font-medium text-slate-600">{h.opens_at.slice(0, 5)} – {h.closes_at.slice(0, 5)}</span>
                )}
              </div>
            ))}
          </Card>
          {org!.address && (
            <>
              <h2 className="mb-3 mt-6 text-lg font-semibold">Contact</h2>
              <Card className="space-y-1 p-4 text-sm text-slate-600">
                <p>{org!.address}</p>
                {org!.contact_phone && <p>{org!.contact_phone}</p>}
              </Card>
            </>
          )}
        </div>
      </div>
    </AppShell>
  )
}

function JoinWalkInButton({ serviceId, serviceName }: { serviceId: number; serviceName: string }) {
  const navigate = useNavigate()
  const toast = useToast()
  const [confirming, setConfirming] = useState(false)
  const [joining, setJoining] = useState(false)
  const [joinError, setJoinError] = useState<string | null>(null)

  async function join() {
    setJoining(true)
    setJoinError(null)
    try {
      const entry = await api.post<QueueEntry>('/api/queue/entries/', { service: serviceId })
      setConfirming(false)
      toast.push(`Joined the queue — token ${entry.token_number}`)
      navigate(`/queue/${entry.id}`)
    } catch (err) {
      setJoinError((err as Error).message)
    } finally {
      setJoining(false)
    }
  }

  return (
    <>
      <Button variant="secondary" onClick={() => setConfirming(true)}>
        Join walk-in queue
      </Button>
      <Modal
        open={confirming}
        title={`Join walk-in queue — ${serviceName}`}
        onClose={() => setConfirming(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setConfirming(false)}>
              Not now
            </Button>
            <Button onClick={join} loading={joining}>
              Join queue
            </Button>
          </>
        }
      >
        <p>
          You will receive a token for today’s queue. Your position and estimated
          waiting time will update live. You can cancel any time before you are called.
        </p>
        {joinError && <p className="mt-3 text-sm text-red-600">{joinError}</p>}
      </Modal>
    </>
  )
}
