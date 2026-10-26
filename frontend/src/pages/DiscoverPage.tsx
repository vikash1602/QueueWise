import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useOrganizations } from '../api/hooks'
import AppShell from '../components/AppShell'
import { Card, EmptyState, ErrorState, Input, LoadingState, PageHeader } from '../components/ui'

export default function DiscoverPage() {
  const [search, setSearch] = useState('')
  const { data, isLoading, isError, error, refetch } = useOrganizations(search)

  return (
    <AppShell>
      <PageHeader title="Find a service" subtitle="Browse organizations and their bookable services." />
      <Input
        placeholder="Search organizations or services…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="mb-6 max-w-md"
        aria-label="Search organizations"
      />
      {isLoading && <LoadingState />}
      {isError && <ErrorState message={(error as Error).message} onRetry={refetch} />}
      {data && data.results.length === 0 && (
        <EmptyState
          title="No organizations found"
          description={search ? `Nothing matches “${search}”.` : 'Organizations will appear here once registered.'}
        />
      )}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {(data?.results ?? []).map((org) => (
          <Link key={org.id} to={`/organizations/${org.id}`}>
            <Card className="h-full p-5 transition-shadow hover:shadow-md">
              <h2 className="font-semibold text-slate-900">{org.name}</h2>
              <p className="mt-1 line-clamp-2 text-sm text-slate-500">{org.description || 'No description yet.'}</p>
              <div className="mt-4 flex items-center justify-between text-sm">
                <span className="text-slate-500">{org.address || '—'}</span>
                <span className="font-medium text-brand-600">
                  {org.services_count ?? 0} service{(org.services_count ?? 0) === 1 ? '' : 's'}
                </span>
              </div>
            </Card>
          </Link>
        ))}
      </div>
    </AppShell>
  )
}
