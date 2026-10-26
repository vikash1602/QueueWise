import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import { useMyStaff } from '../api/hooks'
import type { StaffMember } from '../api/types'
import AppShell from '../components/AppShell'
import { Button, Card, ErrorState, Field, Input, LoadingState, PageHeader, Select, Table, useToast } from '../components/ui'

export default function StaffManagementPage() {
  const { data: staff, isLoading, isError, error } = useMyStaff()
  const [email, setEmail] = useState('')
  const [role, setRole] = useState('STAFF')
  const qc = useQueryClient()
  const toast = useToast()

  const add = useMutation({
    mutationFn: () => api.post<StaffMember>('/api/my/staff/', { email, role }),
    onSuccess: () => {
      toast.push(`${email} added as ${role}`)
      setEmail('')
      qc.invalidateQueries({ queryKey: ['myStaff'] })
    },
    onError: (e) => toast.push((e as Error).message, 'error'),
  })

  const update = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Record<string, unknown> }) =>
      api.patch<StaffMember>(`/api/my/staff/${id}/`, body),
    onSuccess: () => {
      toast.push('Member updated')
      qc.invalidateQueries({ queryKey: ['myStaff'] })
    },
    onError: (e) => toast.push((e as Error).message, 'error'),
  })

  return (
    <AppShell>
      <PageHeader title="Staff management" subtitle="People who can operate this organization." />

      <Card className="mb-6 max-w-xl p-5">
        <h2 className="mb-3 font-medium">Add a member</h2>
        <p className="mb-4 text-sm text-slate-500">
          The person must already have a QueueWise account (they can register first, then you add them here).
        </p>
        <div className="flex flex-wrap items-end gap-3">
          <div className="w-64">
            <Field label="Email">
              <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="colleague@example.com" />
            </Field>
          </div>
          <div className="w-40">
            <Field label="Role">
              <Select value={role} onChange={(e) => setRole(e.target.value)}>
                <option value="STAFF">Staff</option>
                <option value="ADMIN">Administrator</option>
              </Select>
            </Field>
          </div>
          <Button onClick={() => add.mutate()} loading={add.isPending} disabled={!email}>
            Add member
          </Button>
        </div>
      </Card>

      {isLoading && <LoadingState />}
      {isError && <ErrorState message={(error as Error).message} />}
      {staff && (
        <Table head={['Email', 'Name', 'Role', 'Status', 'Actions']}>
          {staff.map((m) => (
            <tr key={m.id} className="hover:bg-slate-50">
              <td className="px-4 py-3 font-medium">{m.email}</td>
              <td className="px-4 py-3">{m.name || '—'}</td>
              <td className="px-4 py-3">
                <Select
                  className="w-36"
                  value={m.role}
                  onChange={(e) => update.mutate({ id: m.id, body: { role: e.target.value } })}
                  aria-label={`Role for ${m.email}`}
                >
                  <option value="STAFF">Staff</option>
                  <option value="ADMIN">Administrator</option>
                </Select>
              </td>
              <td className="px-4 py-3">
                <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${m.is_active ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-200 text-slate-600'}`}>
                  {m.is_active ? 'Active' : 'Suspended'}
                </span>
              </td>
              <td className="px-4 py-3">
                <Button
                  variant="secondary"
                  className="!px-2.5 !py-1 text-xs"
                  onClick={() => update.mutate({ id: m.id, body: { is_active: !m.is_active } })}
                >
                  {m.is_active ? 'Suspend' : 'Reactivate'}
                </Button>
              </td>
            </tr>
          ))}
        </Table>
      )}
    </AppShell>
  )
}
