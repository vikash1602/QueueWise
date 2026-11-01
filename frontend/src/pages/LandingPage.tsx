import { useState } from 'react'
import { Link } from 'react-router-dom'

/* Entrance animation helpers (CSS keyframes in index.css). */
const fadeUp = (delay = 0) => ({
  className: 'anim-fade-up',
  style: { animationDelay: `${delay}ms` },
})

function BrandMark({ light = false }: { light?: boolean }) {
  return (
    <span className="flex items-center gap-2">
      <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent-500 text-base font-bold text-white shadow-sm">
        Q
      </span>
      <span className={`text-xl font-semibold tracking-tight ${light ? 'text-white' : 'text-brand-900'}`}>
        Queue<span className="text-accent-500">Wise</span>
      </span>
    </span>
  )
}

/* ------------------------------------------------------------------ */
/* Interactive product preview — abstract illustrations, never live data */

type PreviewRole = 'customer' | 'staff' | 'admin'

const PREVIEW_TABS: { id: PreviewRole; label: string }[] = [
  { id: 'customer', label: 'Customer' },
  { id: 'staff', label: 'Staff' },
  { id: 'admin', label: 'Admin' },
]

function CustomerPreview() {
  const steps = ['Booked', 'Waiting', 'Called', 'Served']
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-slate-200 bg-white p-4 text-center">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Your token</p>
        <p className="mt-1 font-mono text-4xl font-bold text-brand-700">#—</p>
        <span className="mt-2 inline-flex rounded-full bg-amber-100 px-3 py-0.5 text-xs font-medium text-amber-800">
          Waiting
        </span>
      </div>
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <p className="mb-3 text-xs font-medium uppercase tracking-wide text-slate-400">Visit progress</p>
        <ol className="space-y-2">
          {steps.map((s, i) => (
            <li key={s} className="flex items-center gap-2 text-sm">
              <span
                className={`flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold ${
                  i === 0 ? 'bg-accent-500 text-white' : 'bg-slate-100 text-slate-400'
                }`}
              >
                {i + 1}
              </span>
              <span className={i === 0 ? 'font-medium text-slate-800' : 'text-slate-400'}>{s}</span>
            </li>
          ))}
        </ol>
      </div>
      <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-500">
        Position and estimated wait update live — from real queue data once you join.
      </div>
    </div>
  )
}

function StaffPreview() {
  const lanes = [
    { label: 'Next in line', tone: 'bg-amber-100 text-amber-800' },
    { label: 'Serving', tone: 'bg-indigo-100 text-indigo-800' },
    { label: 'Done', tone: 'bg-emerald-100 text-emerald-800' },
  ]
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <div className="mb-3 flex items-center justify-between">
          <p className="text-sm font-semibold text-slate-800">Live queue</p>
          <span className="rounded-lg bg-brand-600 px-3 py-1 text-xs font-medium text-white">Call next</span>
        </div>
        <div className="space-y-2">
          {lanes.map((lane) => (
            <div key={lane.label} className="flex items-center justify-between rounded-lg border border-slate-100 px-3 py-2">
              <span className="text-sm text-slate-600">{lane.label}</span>
              <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${lane.tone}`}>customer</span>
            </div>
          ))}
        </div>
      </div>
      <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-500">
        One click moves each customer through the queue — every action is validated and recorded.
      </div>
    </div>
  )
}

function AdminPreview() {
  const bars = [42, 68, 35, 80, 55, 90, 63]
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        {['Bookings', 'Served', 'Avg wait'].map((label) => (
          <div key={label} className="rounded-xl border border-slate-200 bg-white p-3 text-center">
            <p className="text-[11px] font-medium uppercase tracking-wide text-slate-400">{label}</p>
            <p className="mt-1 text-xl font-semibold text-brand-800">—</p>
          </div>
        ))}
      </div>
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <p className="mb-3 text-xs font-medium uppercase tracking-wide text-slate-400">Weekly overview</p>
        <div className="flex h-24 items-end gap-2" aria-hidden="true">
          {bars.map((h, i) => (
            <div
              key={i}
              className="flex-1 rounded-t-md bg-brand-200 transition-colors"
              style={{ height: `${h}%` }}
            />
          ))}
        </div>
      </div>
      <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-500">
        Dashboards and audit trails are computed from your organization's real records.
      </div>
    </div>
  )
}

function ProductPreview() {
  const [role, setRole] = useState<PreviewRole>('customer')
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 shadow-xl shadow-brand-900/5">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex rounded-lg border border-slate-200 bg-white p-0.5">
          {PREVIEW_TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setRole(t.id)}
              aria-pressed={role === t.id}
              className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                role === t.id ? 'bg-brand-600 text-white' : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
        <span className="text-[11px] font-medium uppercase tracking-wide text-slate-400">Preview</span>
      </div>
      {role === 'customer' && <CustomerPreview />}
      {role === 'staff' && <StaffPreview />}
      {role === 'admin' && <AdminPreview />}
      <p className="mt-4 text-center text-xs text-slate-400">
        Illustrative preview — not live data. Real numbers appear after you sign in.
      </p>
    </div>
  )
}

/* ------------------------------------------------------------------ */

const FEATURES = [
  {
    title: 'Real slots, zero double-booking',
    body: 'Availability is built from your services and working hours, and conflicts are prevented at the database level — two people can never win the same slot.',
    icon: (
      <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" strokeLinecap="round" strokeLinejoin="round" />
    ),
  },
  {
    title: 'Live tokens and honest estimates',
    body: 'Walk in or book ahead and watch your position and waiting-time estimate update in real time — computed from actual service history, never guessed.',
    icon: <path d="M13 10V3L4 14h7v7l9-11h-7z" strokeLinecap="round" strokeLinejoin="round" />,
  },
  {
    title: 'Built-in accountability',
    body: 'Check-ins, calls, completions and no-shows are recorded with actor and timestamp, so owners can see exactly how the day ran.',
    icon: (
      <path
        d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    ),
  },
]

const STEPS = [
  { n: '1', title: 'Book or walk in', body: 'Reserve a real slot from the availability grid, or let the front desk register you in seconds.' },
  { n: '2', title: 'Get your live token', body: 'A queue token with your position and a data-driven waiting estimate — visible from anywhere.' },
  { n: '3', title: 'Get served', body: 'Staff move the queue with one click; your status updates the moment it happens.' },
]

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-brand-50 via-white to-white">
      <header className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
        <BrandMark />
        <nav className="flex gap-2">
          <Link to="/login" className="rounded-lg px-4 py-2 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-100">
            Sign in
          </Link>
          <Link
            to="/register"
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-700"
          >
            Get started
          </Link>
        </nav>
      </header>

      <main className="mx-auto max-w-6xl px-4">
        {/* Hero */}
        <section className="grid items-center gap-10 py-14 md:grid-cols-2 md:py-20">
          <div {...fadeUp(0)}>
            <span className="inline-flex items-center rounded-full border border-accent-200 bg-accent-50 px-3 py-1 text-xs font-medium text-accent-700">
              Queue &amp; appointment management
            </span>
            <h1 className="mt-5 text-4xl font-bold leading-tight tracking-tight text-slate-900 md:text-5xl">
              Stop guessing the wait.
              <br />
              <span className="text-accent-600">See your place in line.</span>
            </h1>
            <p className="mt-5 max-w-lg text-lg leading-relaxed text-slate-600">
              QueueWise gives clinics, salons and service counters real-time appointment booking, live
              queue tokens and honest waiting-time estimates — for customers, staff and owners alike.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                to="/register"
                className="rounded-lg bg-accent-600 px-6 py-3 text-sm font-semibold text-white shadow-sm transition-all hover:-translate-y-0.5 hover:bg-accent-700 hover:shadow-md"
              >
                Book your first visit
              </Link>
              <Link
                to="/organizations"
                className="rounded-lg border border-slate-300 bg-white px-6 py-3 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-50"
              >
                Browse organizations
              </Link>
            </div>
          </div>
          <div {...fadeUp(150)}>
            <ProductPreview />
          </div>
        </section>

        {/* How it works */}
        <section className="py-8">
          <h2 className="text-center text-2xl font-bold tracking-tight text-slate-900">How it works</h2>
          <div className="mt-8 grid gap-6 md:grid-cols-3">
            {STEPS.map((s, i) => (
              <div key={s.n} {...fadeUp(i * 100)} className="relative rounded-xl border border-slate-200 bg-white p-6 pt-8 text-center shadow-sm">
                <span className="absolute -top-4 left-1/2 flex h-8 w-8 -translate-x-1/2 items-center justify-center rounded-full bg-brand-600 text-sm font-bold text-white">
                  {s.n}
                </span>
                <h3 className="font-semibold text-slate-900">{s.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-slate-600">{s.body}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Features */}
        <section className="py-12">
          <h2 className="text-center text-2xl font-bold tracking-tight text-slate-900">
            Why businesses switch to QueueWise
          </h2>
          <div className="mt-8 grid gap-6 md:grid-cols-3">
            {FEATURES.map((f, i) => (
              <div
                key={f.title}
                {...fadeUp(i * 100)}
                className="group rounded-xl border border-slate-200 bg-white p-6 shadow-sm transition-all hover:-translate-y-1 hover:shadow-md"
              >
                <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-600 transition-colors group-hover:bg-accent-50 group-hover:text-accent-600">
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    {f.icon}
                  </svg>
                </span>
                <h3 className="mt-4 font-semibold text-slate-900">{f.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-slate-600">{f.body}</p>
              </div>
            ))}
          </div>
        </section>

        {/* CTA strip */}
        <section className="py-8">
          <div {...fadeUp()} className="rounded-2xl bg-brand-900 px-8 py-10 text-center">
            <h2 className="text-2xl font-bold text-white">Ready to see the queue clearly?</h2>
            <p className="mx-auto mt-2 max-w-md text-sm text-brand-100">
              Create an account and book your first visit in under a minute.
            </p>
            <Link
              to="/register"
              className="mt-6 inline-block rounded-lg bg-accent-500 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-accent-600"
            >
              Get started free
            </Link>
          </div>
        </section>
      </main>

      <footer className="border-t border-slate-200 py-8">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-4 text-sm text-slate-400 sm:flex-row">
          <BrandMark />
          <p>© {new Date().getFullYear()} QueueWise. All rights reserved.</p>
        </div>
      </footer>
    </div>
  )
}
