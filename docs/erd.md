# Database ER Diagram

```mermaid
erDiagram
    USER ||--o{ ORGANIZATION_MEMBERSHIP : "has"
    ORGANIZATION ||--o{ ORGANIZATION_MEMBERSHIP : "employs"
    ORGANIZATION ||--o{ SERVICE : "offers"
    ORGANIZATION ||--|| BUSINESS_HOURS : "operates (7 rows/week)"
    SERVICE ||--o{ SERVICE_COUNTER : "served at"
    SERVICE ||--o{ APPOINTMENT : "booked as"
    SERVICE ||--o{ QUEUE_ENTRY : "queued for"
    USER ||--o{ APPOINTMENT : "books"
    USER ||--o{ QUEUE_ENTRY : "joins (nullable for guests)"
    APPOINTMENT ||--o| QUEUE_ENTRY : "checked in as"
    SERVICE_COUNTER ||--o{ QUEUE_ENTRY : "serves"
    USER ||--o{ NOTIFICATION : "receives"
    ORGANIZATION ||--o{ AUDIT_LOG : "records"
    USER ||--o{ AUDIT_LOG : "acts in"

    USER {
        bigint id PK
        varchar email UK "login identifier, case-insensitive unique"
        varchar name
        varchar phone
        boolean is_staff "platform admin -> Django admin"
    }
    ORGANIZATION {
        bigint id PK
        varchar name
        varchar slug UK
        varchar timezone "org-local business dates and hours"
        boolean is_active
    }
    ORGANIZATION_MEMBERSHIP {
        bigint id PK
        bigint organization_id FK
        bigint user_id FK
        varchar role "ADMIN | STAFF"
        boolean is_active "suspend without deleting"
    }
    SERVICE {
        bigint id PK
        bigint organization_id FK
        varchar name
        int duration_minutes "slotting + estimation fallback"
        int buffer_minutes
        int avg_duration_minutes "rolling median, maintained on completion"
        boolean is_appointment_enabled
        boolean is_walkin_enabled
        int max_advance_days
        boolean is_active
    }
    BUSINESS_HOURS {
        bigint id PK
        bigint organization_id FK
        smallint weekday "0=Mon .. 6=Sun, UNIQUE(org, weekday)"
        time opens_at
        time closes_at
        boolean is_closed
    }
    SERVICE_COUNTER {
        bigint id PK
        bigint service_id FK
        varchar name
        boolean is_active "reduces estimated wait in parallel"
    }
    APPOINTMENT {
        bigint id PK
        bigint organization_id FK
        bigint service_id FK
        bigint customer_id FK
        timestamptz slot_start "UNIQUE(service, slot_start) WHERE live"
        timestamptz slot_end "CHECK slot_end > slot_start"
        varchar status "CONFIRMED..NO_SHOW"
        bigint cancelled_by_id FK "nullable"
        varchar cancel_reason
    }
    QUEUE_ENTRY {
        bigint id PK
        bigint organization_id FK
        bigint service_id FK
        bigint customer_id FK "nullable: staff-registered guests"
        varchar guest_name
        bigint appointment_id FK "unique, nullable (1-1 with Appointment)"
        varchar source "WALKIN | APPOINTMENT"
        int token_number "UNIQUE(org, service, business_date, token)"
        date business_date "org-local operating day"
        varchar status "WAITING..CANCELLED"
        bigint counter_id FK "nullable"
        int estimated_wait_minutes "snapshot at last state change"
        timestamptz joined_at
        timestamptz called_at
        timestamptz started_at
        timestamptz completed_at "CHECK non-null when COMPLETED"
    }
    NOTIFICATION {
        bigint id PK
        bigint user_id FK
        varchar type
        varchar title
        text body
        jsonb payload
        boolean is_read
    }
    AUDIT_LOG {
        bigint id PK
        bigint organization_id FK "nullable"
        bigint actor_id FK "nullable"
        varchar action
        varchar object_type
        varchar object_id
        jsonb detail "no credentials or tokens stored"
    }
```

## Integrity guarantees

| Concern | Mechanism |
|---|---|
| Double-booked slot | Partial unique index `uniq_live_booking_per_service_slot` on `(service, slot_start)` excluding CANCELLED/NO_SHOW — enforced by PostgreSQL even under concurrent requests |
| Duplicate tokens | Unique `uniq_token_per_org_service_day` on `(organization, service, business_date, token_number)`; token allocation additionally serialized by `SELECT ... FOR UPDATE` on the Service row inside the joining transaction |
| Invalid queue transitions | Enforced in `queues.services.ALLOWED_TRANSITIONS` (service layer) + `completed_requires_completed_at` DB check |
| Tenant isolation | All org-scoped queries filter through the requester's active `OrganizationMembership`; customer queries filter by ownership |
| Duplicate memberships | Unique `(organization, user)` |
