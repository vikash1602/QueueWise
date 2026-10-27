import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useLogin } from '../api/hooks'
import { Button, ErrorState, Field, Input } from '../components/ui'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const login = useLogin()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? '/dashboard'

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    try {
      await login.mutateAsync({ email, password })
      // Full page load: guarantees no cached data from the previous session
      // survives the identity switch.
      window.location.assign(from)
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
          <h1 className="mb-6 text-xl font-semibold">Sign in</h1>
          <div className="space-y-4">
            <Field label="Email">
              <Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
            </Field>
            <Field label="Password">
              <Input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
            </Field>
            {login.isError && <ErrorState message={(login.error as Error).message} />}
            <Button type="submit" className="w-full" loading={login.isPending}>
              Sign in
            </Button>
          </div>
          <p className="mt-4 text-center text-sm text-slate-500">
            No account?{' '}
            <Link to="/register" className="font-medium text-brand-600 hover:underline">
              Create one
            </Link>
          </p>
        </form>
      </div>
    </div>
  )
}
