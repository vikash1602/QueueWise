# QueueWise

**Real-time queue and appointment management for service organizations.**

QueueWise gives clinics, salons, offices, and service centers appointment
booking, walk-in queue tokens, live position tracking, and honest
waiting-time estimates — with a staff console to operate the queue and an
admin dashboard backed by real records.

- Customers register, browse organizations, book appointment slots, join
  walk-in queues, and watch their token, position, and estimate update live.
- Staff call the next customer, start and complete services, register
  walk-ins, check in appointments, and mark no-shows — every action validated
  server-side and recorded in an audit history.
- Organization admins configure services, working hours, and staff, and read
  analytics computed from persisted records.

---

## Technology stack

| Layer | Technology | Version (installed, verified) |
|---|---|---|
| Frontend | React + TypeScript + Vite | Vite 8.3.x, React 19 |
| Styling | Tailwind CSS | 4.x |
| Routing / data | React Router 7, TanStack Query 5 | |
| Charts | Recharts 3 | |
| Backend | Python + Django + DRF | Python 3.13.1, Django 5.2.6, DRF 3.16.1 |
| Real-time | Django Channels 4.3 + Daphne (ASGI) | |
| Database | PostgreSQL | 18.6 |
| API docs | drf-spectacular (OpenAPI 3) | |
| Tests | Django test runner + DRF APIClient | 65 backend tests |

No paid APIs, no AI keys, no Docker required for local development.

## Repository layout

```
backend/                 Django project (config/) + apps:
  accounts/              custom User, register/login/logout, CSRF endpoint
  organizations/         Organization, Membership (RBAC), Service, BusinessHours,
                         ServiceCounter, seed_demo management command
  appointments/          Appointment model, availability + booking services
  queues/                QueueEntry, token allocation, state machine, estimation,
                         WebSocket consumers + broadcasts
  notifications/         in-app notifications (+ optional console email)
  analytics/             summary / trends / peak-hours from persisted records
  audit/                 append-only audit log
frontend/                Vite SPA: pages for customer, staff, and admin
docs/                    architecture.md, erd.md, waiting-time.md
```

## Quick start (local, no Docker)

Prerequisites: Python 3.13+, Node 20+, and a PostgreSQL server (16+).

### 1. Database

Create a database and user (adjust credentials freely):

```sql
CREATE ROLE queuewise_app LOGIN PASSWORD 'your_password' NOSUPERUSER CREATEDB;
CREATE DATABASE queuewise OWNER queuewise_app;
```

> This project on the original dev machine uses a dedicated PostgreSQL cluster
> on port 5433 (`C:\Users\Vikash1602\pgdata\queuewise`), started with
> `schtasks /run /tn QueueWisePG`. Any reachable PostgreSQL works — set it in
> `backend/.env`.

### 2. Backend

```bash
cd backend
python -m venv venv
venv/Scripts/pip install -r requirements.txt     # or venv/bin/pip on Linux/macOS
copy .env.example .env                           # then fill DB_PASSWORD and a SECRET_KEY
venv/Scripts/python manage.py migrate
venv/Scripts/python manage.py seed_demo          # optional: labeled demo data
venv/Scripts/python manage.py runserver          # http://127.0.0.1:8000
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev                                      # http://localhost:5173 (proxies /api and /ws)
```

### 4. Demo accounts (after `seed_demo`)

| Role | Email | Password |
|---|---|---|
| Org admin | `admin@demo.queuewise.local` | `Demo!Pass123` |
| Staff | `staff@demo.queuewise.local` | `Demo!Pass123` |
| Customer | `customer@demo.queuewise.local` | `Demo!Pass123` |

All demo records are visibly prefixed `[DEMO]`. The command is idempotent and
never mixes demo data with real registrations (separate email domain).

### Tests

```bash
cd backend && venv/Scripts/python manage.py test          # 65 tests, incl. concurrency
cd frontend && npm run build && npm run lint              # type-check + production build
```

## Documentation

- [docs/architecture.md](docs/architecture.md) — system design, roles, schema decisions, API outline
- [docs/erd.md](docs/erd.md) — ER diagram and integrity guarantees
- [docs/waiting-time.md](docs/waiting-time.md) — estimation algorithm, assumptions, tests
- API schema: run the backend and open <http://127.0.0.1:8000/api/docs/>

## How correctness is enforced

1. **Booking conflicts** — a partial unique index on `(service, slot_start)`
   excluding cancelled rows makes double-booking impossible at the storage
   layer; the service layer additionally locks the service row and validates
   opening hours, past dates, and advance limits. Verified with a threaded
   concurrency test (`appointments.tests.ConcurrentBookingTests`).
2. **Token uniqueness** — unique `(organization, service, business_date,
   token_number)` plus row-lock serialization; verified with a 5-thread
   concurrent walk-in test expecting tokens 1–5.
3. **State machine** — queue transitions are whitelisted
   (WAITING→CALLED→IN_PROGRESS→COMPLETED, etc.); invalid moves return 409.
4. **Authorization** — every staff endpoint resolves the caller's active
   `OrganizationMembership`; customers only see their own appointments and
   queue entries. Cross-tenant access is covered by tests (403/404 paths).
5. **Real-time consistency** — WebSocket messages are hints; clients always
   re-sync through the REST snapshot on connect and reconnect.

## Known limitations & future work

- Email notifications default to the console backend; wiring an SMTP provider
  is configuration only (`EMAIL_BACKEND`, `QUEUEWISE_SEND_EMAIL_NOTIFICATIONS`).
- The channel layer defaults to the in-process memory layer for single-process
  dev; production must point `REDIS_URL` at Redis and set
  `USE_INMEMORY_CHANNEL_LAYER=0`.
- Counters are modeled as interchangeable; per-counter skills/speeds are not.
- No i18n; UI copy is English-only.
- Scheduled appointment reminders are a natural next step on top of the
  notification infrastructure.

## Deployment notes

See [docs/deployment.md](docs/deployment.md) for production configuration
(environment variables, ASGI service, static files, security settings).
