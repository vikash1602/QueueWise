import { Link } from 'react-router-dom'

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-brand-50 via-white to-white">
      <header className="mx-auto flex h-16 max-w-6xl items-center px-4">
        <span className="text-xl font-bold text-brand-700">
          Queue<span className="text-slate-900">Wise</span>
        </span>
        <nav className="ml-auto flex gap-2">
          <Link to="/login" className="rounded-lg px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100">
            Sign in
          </Link>
          <Link
            to="/register"
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
          >
            Get started
          </Link>
        </nav>
      </header>

      <main className="mx-auto max-w-6xl px-4">
        <section className="grid gap-10 py-16 md:grid-cols-2 md:py-24">
          <div>
            <h1 className="text-4xl font-bold tracking-tight md:text-5xl">
              Stop guessing the wait.
              <br />
              <span className="text-brand-600">See your place in line.</span>
            </h1>
            <p className="mt-5 max-w-lg text-lg text-slate-600">
              QueueWise gives clinics, salons, offices and service centers real-time
              appointment booking, live queue tokens, and honest waiting-time estimates —
              for customers and staff alike.
            </p>
            <div className="mt-8 flex gap-3">
              <Link
                to="/register"
                className="rounded-lg bg-brand-600 px-6 py-3 text-sm font-semibold text-white shadow hover:bg-brand-700"
              >
                Book your first visit
              </Link>
              <Link
                to="/organizations"
                className="rounded-lg border border-slate-300 bg-white px-6 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
              >
                Browse organizations
              </Link>
            </div>
          </div>
          <div className="flex items-center">
            <div className="w-full rounded-2xl border border-slate-200 bg-white p-6 shadow-xl">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Live queue</p>
              <div className="mt-4 space-y-3">
                {[
                  { token: 'A-014', label: 'Now serving', tone: 'bg-emerald-100 text-emerald-800' },
                  { token: 'A-015', label: 'You', tone: 'bg-brand-100 text-brand-800' },
                  { token: 'A-016', label: 'Waiting', tone: 'bg-slate-100 text-slate-600' },
                ].map((row) => (
                  <div key={row.token} className="flex items-center justify-between rounded-xl border border-slate-100 px-4 py-3">
                    <span className="font-mono text-lg font-semibold">{row.token}</span>
                    <span className={`rounded-full px-3 py-1 text-xs font-medium ${row.tone}`}>{row.label}</span>
                  </div>
                ))}
              </div>
              <p className="mt-4 text-sm text-slate-500">
                Estimated wait: <span className="font-semibold text-slate-700">≈ 25 min</span>
              </p>
            </div>
          </div>
        </section>

        <section className="grid gap-6 py-8 md:grid-cols-3">
          {[
            {
              title: 'Real appointments, real slots',
              body: 'Availability built from each organization’s working hours and service durations. Conflicts are impossible, not unlikely.',
            },
            {
              title: 'Live tokens and positions',
              body: 'Walk in or book ahead — get a token, watch your position and estimate update as the queue moves.',
            },
            {
              title: 'Tools the front desk loves',
              body: 'Call next, start, complete, no-show and skip — with a full audit history behind every action.',
            },
          ].map((f) => (
            <div key={f.title} className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
              <h3 className="font-semibold text-slate-900">{f.title}</h3>
              <p className="mt-2 text-sm text-slate-600">{f.body}</p>
            </div>
          ))}
        </section>
      </main>

      <footer className="border-t border-slate-200 py-6 text-center text-sm text-slate-400">
        QueueWise — a demonstration of production-grade queue management.
      </footer>
    </div>
  )
}
