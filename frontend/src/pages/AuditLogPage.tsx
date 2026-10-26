import { useAuditLogs } from '../api/hooks'
import AppShell from '../components/AppShell'
import { EmptyState, ErrorState, LoadingState, PageHeader, Table } from '../components/ui'

export default function AuditLogPage() {
  const { data, isLoading, isError, error, refetch } = useAuditLogs('?limit=200')

  return (
    <AppShell>
      <PageHeader title="Audit history" subtitle="Every important action, with actor and timestamp." />
      {isLoading && <LoadingState />}
      {isError && <ErrorState message={(error as Error).message} onRetry={refetch} />}
      {data && data.results.length === 0 && (
        <EmptyState title="No audit records yet" description="Actions will be recorded as your team operates the queue." />
      )}
      {data && data.results.length > 0 && (
        <Table head={['When', 'Actor', 'Action', 'Object', 'Details']}>
          {data.results.map((log) => (
            <tr key={log.id} className="hover:bg-slate-50">
              <td className="px-4 py-3 whitespace-nowrap text-slate-500">{new Date(log.created_at).toLocaleString()}</td>
              <td className="px-4 py-3">{log.actor_email ?? 'system'}</td>
              <td className="px-4 py-3 font-medium">{log.action}</td>
              <td className="px-4 py-3 text-slate-500">{log.object_type}#{log.object_id}</td>
              <td className="max-w-xs truncate px-4 py-3 font-mono text-xs text-slate-500">
                {JSON.stringify(log.detail)}
              </td>
            </tr>
          ))}
        </Table>
      )}
    </AppShell>
  )
}
