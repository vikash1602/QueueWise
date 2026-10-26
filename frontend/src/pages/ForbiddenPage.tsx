import { Link } from 'react-router-dom'

export default function ForbiddenPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-slate-50 px-4 text-center">
      <p className="text-6xl font-bold text-rose-200">403</p>
      <h1 className="mt-4 text-2xl font-semibold">Access denied</h1>
      <p className="mt-2 max-w-sm text-slate-500">
        Your account does not have permission to view this area. If you believe this is
        wrong, ask your organization administrator to check your role.
      </p>
      <Link to="/" className="mt-6 rounded-lg bg-brand-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-brand-700">
        Back to home
      </Link>
    </div>
  )
}
