import { useState } from 'react'
import { useAnalyticsSummary, useMyServices, useTrends } from '../api/hooks'

import AppShell from '../components/AppShell'
import { Card, ErrorState, Field, LoadingState, PageHeader, Select } from '../components/ui'
import {
  CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'

export default function AnalyticsPage() {
  const [days, setDays] = useState(7)
  const [serviceId, setServiceId] = useState('all')
  const { data: services } = useMyServices()

  const params = new URLSearchParams({ days: String(days) })
  if (serviceId !== 'all') params.set('service', serviceId)
  const summary = useAnalyticsSummary(`?${params}`)
  const trends = useTrends(`?${params}`)

  const metric = (label: string, value: string | number | null | undefined, hint?: string) => (
    <Card key={label} className="p-5">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value ?? '—'}</p>
      {hint && <p className="mt-1 text-xs text-slate-400">{hint}</p>}
    </Card>
  )

  return (
    <AppShell>
      <PageHeader title="Analytics" subtitle="Computed from persisted records — never demo numbers." />

      <div className="mb-6 flex flex-wrap gap-3">
        <div className="w-40">
          <Field label="Period">
            <Select value={days} onChange={(e) => setDays(Number(e.target.value))}>
              <option value="1">Last 24 hours</option>
              <option value="7">Last 7 days</option>
              <option value="30">Last 30 days</option>
              <option value="90">Last 90 days</option>
            </Select>
          </Field>
        </div>
        <div className="w-56">
          <Field label="Service">
            <Select value={serviceId} onChange={(e) => setServiceId(e.target.value)}>
              <option value="all">All services</option>
              {(services ?? []).map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </Select>
          </Field>
        </div>
      </div>

      {summary.isLoading && <LoadingState />}
      {summary.isError && <ErrorState message={(summary.error as Error).message} />}

      {summary.data && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {metric('Total appointments', summary.data.total_appointments)}
            {metric('Customers served', summary.data.customers_served)}
            {metric('Active queue size', summary.data.active_queue_size, 'right now (today)')}
            {metric('Average wait', summary.data.avg_wait_minutes ? `${summary.data.avg_wait_minutes} min` : null)}
            {metric('Average service duration', summary.data.avg_service_minutes ? `${summary.data.avg_service_minutes} min` : null)}
            {metric('Cancellation rate', summary.data.cancellation_rate != null ? `${(summary.data.cancellation_rate * 100).toFixed(1)}%` : null, 'appointments')}
            {metric('No-show rate', summary.data.no_show_rate != null ? `${(summary.data.no_show_rate * 100).toFixed(1)}%` : null)}
            {metric('Cancelled queue entries', summary.data.cancelled_queue_entries)}
          </div>

          <Card className="mt-8 p-6">
            <h2 className="mb-4 font-semibold">Daily trends</h2>
            {trends.isLoading && <LoadingState />}
            {trends.data && (
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={trends.data.trends}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
                    <Tooltip />
                    <Legend />
                    <Line type="monotone" dataKey="queue_joined" name="Queue joins" stroke="#2748e4" strokeWidth={2} />
                    <Line type="monotone" dataKey="customers_served" name="Served" stroke="#059669" strokeWidth={2} />
                    <Line type="monotone" dataKey="appointments" name="Appointments" stroke="#d97706" strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </Card>
        </>
      )}
    </AppShell>
  )
}
