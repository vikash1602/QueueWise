import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { useRegister } from '../api/hooks'
import { Button, ErrorState, Field, Input } from '../components/ui'

export default function RegisterPage() {
  const [form, setForm] = useState({ email: '', name: '', password: '', password2: '' })
  const register = useRegister()
  const navigate = useNavigate()
  const qc = useQueryClient()

  function set(key: keyof typeof form) {
    return (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [key]: e.target.value })
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    try {
      await register.mutateAsync(form)
      await qc.invalidateQueries({ queryKey: ['me'] })
      navigate('/dashboard', { replace: true })
    } catch {
      /* error surfaced below */
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-sm">
        <Link to="/" className="mb-8 block text-center text-2xl font-bold text-brand-700">
          Queue<span className="text-slate-900">Wise</span>
        </Link>
        <form onSubmit={submit} className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h1 className="mb-6 text-xl font-semibold">Create your account</h1>
          <div className="space-y-4">
            <Field label="Full name">
              <Input required value={form.name} onChange={set('name')} autoComplete="name" />
            </Field>
            <Field label="Email">
              <Input type="email" required value={form.email} onChange={set('email')} autoComplete="email" />
            </Field>
            <Field label="Password" hint="At least 8 characters, not a common password.">
              <Input type="password" required value={form.password} onChange={set('password')} autoComplete="new-password" />
            </Field>
            <Field label="Confirm password">
              <Input type="password" required value={form.password2} onChange={set('password2')} autoComplete="new-password" />
            </Field>
            {register.isError && <ErrorState message={(register.error as Error).message} />}
            <Button type="submit" className="w-full" loading={register.isPending}>
              Create account
            </Button>
          </div>
          <p className="mt-4 text-center text-sm text-slate-500">
            Already registered?{' '}
            <Link to="/login" className="font-medium text-brand-600 hover:underline">
              Sign in
            </Link>
          </p>
        </form>
      </div>
    </div>
  )
}
