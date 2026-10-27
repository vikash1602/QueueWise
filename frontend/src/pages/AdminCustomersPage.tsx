import { useState } from 'react'
import { useAdminCustomers } from '../api/hooks'
import AppShell from '../components/AppShell'
import { Button, EmptyState, ErrorState, Input, LoadingState, PageHeader, Table } from '../components/ui'

export default function AdminCustomersPage() {
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const { data, isLoading, isError, error, refetch } = useAdminCustomers(query, page)

  const totalPages = data ? Math.max(1, Math.ceil(data.count / data.page_size)) : 1

  return (
    <AppShell>
      <PageHeader
        title="Customers"
        subtitle="People with visits at your organization. Read-only directory — passwords are never shown."
      />

      <form
        className="mb-4 flex max-w-md gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          setPage(1)
          setQuery(search)
        }}
      >
        <Input
          placeholder="Search name, email or phone…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search customers"
        />
        <Button type="submit">Search</Button>
      </form>

      {isLoading && <LoadingState />}
      {isError && <ErrorState message={(error as Error).message} onRetry={refetch} />}
      {data && data.results.length === 0 && (
        <EmptyState
          title="No customers found"
          description={query ? `Nothing matches “${query}”.` : 'Customers appear here after their first visit or booking.'}
        />
      )}

      {data && data.results.length > 0 && (
        <>
          <Table head={['Name', 'Email', 'Phone', 'Appointments', 'Queue visits', 'Last visit']}>
            {data.results.map((c) => (
              <tr key={c.id} className="hover:bg-slate-50">
                <td className="px-4 py-3 font-medium">{c.name || '—'}</td>
                <td className="px-4 py-3">{c.email}</td>
                <td className="px-4 py-3">{c.phone || '—'}</td>
                <td className="px-4 py-3 tabular-nums">{c.appointment_count}</td>
                <td className="px-4 py-3 tabular-nums">{c.queue_count}</td>
                <td className="px-4 py-3 whitespace-nowrap text-slate-500">
                  {c.last_visit ? new Date(c.last_visit).toLocaleDateString() : '—'}
                </td>
              </tr>
            ))}
          </Table>
          <div className="mt-4 flex items-center justify-between text-sm text-slate-500">
            <span>
              {data.count} customer{data.count === 1 ? '' : 's'} · page {data.page} of {totalPages}
            </span>
            <div className="flex gap-2">
              <Button variant="secondary" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                ← Previous
              </Button>
              <Button variant="secondary" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
                Next →
              </Button>
            </div>
          </div>
        </>
      )}
    </AppShell>
  )
}
