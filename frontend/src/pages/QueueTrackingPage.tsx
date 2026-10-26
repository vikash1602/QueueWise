import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQueueStatus } from '../api/hooks'
import type { QueueStatus } from '../api/types'
import { QUEUE_STATUS_LABELS } from '../api/types'
import AppShell from '../components/AppShell'
import { Button, Card, ErrorState, LoadingState, Modal, PageHeader, StatusBadge, useToast } from '../components/ui'
import { api } from '../api/client'
import { queryClient } from '../queryClient'

/** WebSocket hint channel: any event re-syncs via the REST snapshot, so a
 * missed or dropped message never leaves the client out of sync. */
function useQueueSocket(entryId: number | null, onEvent: () => void) {
  const [connected, setConnected] = useState(false)
  const handlerRef = useRef(onEvent)

  useEffect(() => {
    handlerRef.current = onEvent
  }, [onEvent])

  useEffect(() => {
    if (!entryId) return
    let closed = false
    let retry: number | undefined

    function connect() {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      const ws = new WebSocket(`${proto}://${location.host}/ws/queue/${entryId}/`)
      ws.onopen = () => setConnected(true)
      ws.onmessage = () => handlerRef.current()
      ws.onclose = () => {
        setConnected(false)
        if (!closed) retry = window.setTimeout(connect, 3000)
      }
    }
    connect()
    return () => {
      closed = true
      if (retry) clearTimeout(retry)
    }
  }, [entryId])

  return connected
}

export default function QueueTrackingPage() {
  const { entryId } = useParams()
  const id = Number(entryId)
  const { data: status, isLoading, isError, error, dataUpdatedAt } = useQueueStatus(id)
  const toast = useToast()
  const [confirmCancel, setConfirmCancel] = useState(false)
  const [cancelling, setCancelling] = useState(false)

  useQueueSocket(id, () => {
    // Re-fetch the authoritative snapshot on any pushed event.
    queryClient.invalidateQueries({ queryKey: ['queueStatus', id] })
  })

  if (isLoading) return <AppShell><LoadingState label="Loading your token…" /></AppShell>
  if (isError)
    return (
      <AppShell>
        <ErrorState message={(error as Error).message} />
      </AppShell>
    )

  const s: QueueStatus = status!
  const live = ['WAITING', 'CALLED'].includes(s.status)

  async function cancelEntry() {
    setCancelling(true)
    try {
      await api.post(`/api/queue/entries/${id}/cancel/`)
      toast.push('Queue entry cancelled')
      setConfirmCancel(false)
    } catch (err) {
      toast.push((err as Error).message, 'error')
    } finally {
      setCancelling(false)
    }
  }

  return (
    <AppShell>
      <PageHeader
        title="Your queue status"
        subtitle={`${s.service_name} at ${s.organization_name}`}
        actions={
          live ? (
            <Button variant="danger" onClick={() => setConfirmCancel(true)}>
              Leave queue
            </Button>
          ) : undefined
        }
      />

      <div className="grid gap-6 md:grid-cols-3">
        <Card className="p-8 text-center md:col-span-1">
          <p className="text-sm uppercase tracking-wide text-slate-400">Your token</p>
          <p className="mt-2 font-mono text-6xl font-bold text-brand-700">#{s.token_number}</p>
          <div className="mt-3">
            <StatusBadge status={s.status} label={QUEUE_STATUS_LABELS[s.status]} />
          </div>
        </Card>

        <Card className="p-8 md:col-span-2">
          <div className="grid gap-6 sm:grid-cols-3">
            <div>
              <p className="text-sm text-slate-500">People ahead</p>
              <p className="mt-1 text-3xl font-semibold">{s.people_ahead}</p>
            </div>
            <div>
              <p className="text-sm text-slate-500">Estimated wait</p>
              <p className="mt-1 text-3xl font-semibold">
                {live ? `≈ ${s.estimated_wait_minutes} min` : '—'}
              </p>
              <p className="text-xs text-slate-400">estimate, not a guarantee</p>
            </div>
            <div>
              <p className="text-sm text-slate-500">Now serving</p>
              <p className="mt-1 font-mono text-3xl font-semibold">
                {s.now_serving.length ? `#${s.now_serving[0]}` : '—'}
              </p>
            </div>
          </div>
          <div className="mt-6 flex items-center justify-between border-t border-slate-100 pt-4 text-xs text-slate-400">
            <span>Updated {new Date(dataUpdatedAt ?? s.updated_at).toLocaleTimeString()}</span>
            <span>Position {s.position}</span>
          </div>
        </Card>
      </div>

      {s.status === 'CALLED' && (
        <Card className="mt-6 border-blue-300 bg-blue-50 p-6 text-center">
          <p className="text-lg font-semibold text-blue-800">You are being called — please approach the counter.</p>
        </Card>
      )}

      <Modal
        open={confirmCancel}
        title="Leave the queue?"
        onClose={() => setConfirmCancel(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setConfirmCancel(false)}>Stay</Button>
            <Button variant="danger" onClick={cancelEntry} loading={cancelling}>Leave queue</Button>
          </>
        }
      >
        <p>Your token #{s.token_number} will be cancelled. You would need to rejoin for a new token.</p>
      </Modal>

      <Link to="/dashboard" className="mt-6 inline-block text-sm font-medium text-brand-600 hover:underline">
        ← Back to dashboard
      </Link>
    </AppShell>
  )
}
