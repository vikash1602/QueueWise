# QueueWise — Architecture & Design

## 1. System Overview

QueueWise is a full-stack web application for real-time queue and appointment management.

```
┌─────────────────────────┐        HTTP/REST + WebSocket         ┌──────────────────────────┐
│  React SPA (Vite + TS)  │ ◄──────────────────────────────────► │  Django 5.2 + DRF        │
│  - React Router         │      /api/...  (JSON, session auth)  │  - DRF viewsets          │
│  - TanStack Query       │      /ws/queue/... (Channels)        │  - Channels (daphne/ASGI)│
│  - Tailwind CSS         │                                      │  - service-layer logic   │
└─────────────────────────┘                                      └────────────┬─────────────┘
                                                                              │ Django ORM
                                                                              ▼
                                                              ┌──────────────────────────┐
                                                              │  PostgreSQL 18           │
                                                              │  - FKs, unique, partial  │
                                                              │  - indexes, transactions │
                                                              └──────────────────────────┘
```

- **Auth**: Django session authentication (HttpOnly cookie) + DRF SessionAuth. CSRF is enforced on unsafe methods with the token surfaced to the SPA. Chosen over JWT for a browser-first product: no token storage in JS, simple revocation, built-in expiry.
- **Real-time**: Django Channels over ASGI (daphne in dev). Every queue mutation persists to PostgreSQL first, then broadcasts. Clients resync via REST snapshot on connect/reconnect — WebSocket messages are hints, never the source of truth.
- **Estimation**: deterministic algorithm (median of last N completed durations, capped rolling average fallback, counter-aware) — documented in `docs/waiting-time.md`.

## 2. Roles

| Role | Model source | Capabilities |
|---|---|---|
| Customer | `User(role=CUSTOMER)` | browse, book, join queue, track own tokens |
| Staff | `OrganizationMembership(role=STAFF)` | operate queues for their org only |
| Org admin | `OrganizationMembership(role=ADMIN)` | org config, staff mgmt, analytics, audit |
| Platform admin | `User(is_staff=True)` | Django admin only |

A user may be a customer platform-wide and hold memberships in one or more organizations. Staff actions are always authorized against `OrganizationMembership`, never against client-asserted state.

## 3. Data Model

```
User(id, email*, name, phone, role[CUSTOMER], password, timestamps)
Organization(id, name, slug*, description, contact_email, contact_phone,
             timezone, is_active, timestamps)
OrganizationMembership(id, organization FK, user FK, role[ADMIN|STAFF],
             is_active, timestamps)   UNIQUE(organization, user)
Service(id, organization FK, name, description, duration_minutes,
             buffer_minutes, is_appointment_enabled, is_walkin_enabled,
             avg_duration_minutes /* rolling, maintained on completion */,
             is_active, timestamps)
BusinessHours(id, organization FK, weekday 0-6, opens_at TIME, closes_at TIME,
             is_closed)   UNIQUE(organization, weekday)
ServiceCounter(id, service FK, name, is_active, timestamps)

Appointment(id, organization FK, service FK, customer FK, slot_start TIMESTZ,
             slot_end TIMESTZ, status[PENDING|CONFIRMED|CHECKED_IN|IN_PROGRESS|
             COMPLETED|CANCELLED|NO_SHOW], queue_entry FK nullable, timestamps,
             cancelled_by FK nullable, cancel_reason)
             UNIQUE(service, slot_start) WHERE status NOT IN (CANCELLED, NO_SHOW)  ← partial unique index

QueueEntry(id, organization FK, service FK, customer FK nullable,
             guest_name, token_number INT,
             business_date DATE,   ← org-local operating day
             status[WAITING|CALLED|IN_PROGRESS|COMPLETED|NO_SHOW|CANCELLED],
             source[WALKIN|APPOINTMENT], appointment FK nullable,
             counter FK nullable,
             joined_at, called_at, started_at, completed_at,
             estimated_wait_minutes, timestamps)
             UNIQUE(organization, service, business_date, token_number)

ServiceSession(id, queue_entry FK 1-1, counter FK nullable, started_at,
             completed_at, duration_minutes)   ← historical durations feed estimation

Notification(id, user FK, type, title, body, payload JSONB, is_read,
             created_at)   index (user, is_read), (user, -created_at)

AuditLog(id, organization FK nullable, actor FK nullable, action, object_type,
             object_id, detail JSONB, created_at)
             index (organization, -created_at)
```

### Key integrity decisions

1. **Appointment conflicts** — a *partial unique index* on `(service, slot_start)` restricted to live statuses makes double-booking impossible at the storage layer, even under concurrent requests. Booking wraps validation + insert in `transaction.atomic()` with `select_for_update` on the service row as a write serializer for slot-range overlap checks (start/end ranges with buffer).
2. **Token uniqueness** — `UNIQUE(organization, service, business_date, token_number)`. Tokens are allocated inside a transaction with `select_for_update` on the org+service+day "token sequence" row (implemented via the service row + `business_date` lock) so concurrent walk-ins get gapless, unique tokens per scope.
3. **Queue state machine** — allowed transitions are enforced in the service layer (`queues.services.transition()`), e.g. `WAITING→CALLED→IN_PROGRESS→COMPLETED`; `WAITING→NO_SHOW|CANCELLED`; `CALLED→NO_SHOW`. Invalid transitions raise 409.
4. **Tenant isolation** — every org-scoped queryset goes through membership-filtered managers; DRF permission classes verify membership per object. Customer data is filtered by ownership.
5. **No redundant denormalization** beyond `avg_duration_minutes` (justified: avoids full-table scans for estimation) and `estimated_wait_minutes` snapshot (justified: shows the estimate as of the last state change).

## 4. API Outline

All endpoints under `/api/`, JSON, session-authenticated. Consistent error envelope:
`{"detail": string}` or `{"field": [errors]}`. Pagination: `?page=&page_size=` (default 20).

| Group | Endpoints |
|---|---|
| Auth | `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` |
| Organizations (public) | `GET /organizations`, `GET /organizations/{id}`, `GET /organizations/{id}/services`, `GET /organizations/{id}/availability?service=&date=` |
| Org management (admin) | `GET/PUT /my/organization`, `GET/POST /my/services`, `PATCH/DELETE /my/services/{id}`, `PUT /my/business-hours`, `GET/POST /my/counters`, `GET/POST/PATCH /my/staff` |
| Appointments | `GET/POST /appointments`, `GET /appointments/{id}`, `POST /appointments/{id}/cancel` |
| Queue (customer) | `GET /queue/entries` (mine), `POST /queue/entries` (join), `POST /queue/entries/{id}/cancel`, `GET /queue/entries/{id}/status` (polling) |
| Queue (staff) | `GET /staff/queue/today`, `POST /staff/queue/call-next`, `POST /staff/queue/entries/{id}/call|start|complete|no-show|cancel|skip`, `POST /staff/walk-in`, `POST /staff/check-in/{appointment_id}` |
| Notifications | `GET /notifications`, `POST /notifications/{id}/read`, `POST /notifications/read-all` |
| Analytics | `GET /my/analytics/summary?from=&to=&service=`, `GET /my/analytics/trends`, `GET /my/analytics/peak-hours` |
| Audit | `GET /my/audit-logs` (admin only) |

WebSocket: `ws/queue/{queue_entry_id}/` (owner or org staff), `ws/org/{org_id}/queue/` (staff) — auth checked in `connect()`; clients always re-fetch REST snapshot after (re)connect.

## 5. Milestones

Phases 1–10 as specified (see README checklist). Each phase ends with passing tests + a commit.

## 6. Local topology (this machine)

- PostgreSQL binaries: `C:\Program Files\PostgreSQL\18\bin`
- Dedicated cluster: `C:\Users\Vikash1602\pgdata\queuewise`, port **5433** (the system-wide service on 5432 is left untouched)
- Start/stop: `schtasks /run /tn QueueWisePG` / `pg_ctl -D C:\Users\Vikash1602\pgdata\queuewise stop`
- App DB role: `queuewise_app` / database `queuewise` — credentials live in `backend/.env` (never committed)
