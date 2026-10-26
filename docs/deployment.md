# Deployment Guide

## Overview

- **Backend**: Django 5.2 under Daphne (ASGI, required for WebSockets), behind
  a reverse proxy (nginx/Caddy) or a platform that terminates TLS.
- **Frontend**: static build (`npm run build` → `dist/`) served by any static
  host or the same reverse proxy.
- **Database**: managed PostgreSQL 16+ (or self-hosted).
- **Channel layer**: Redis in production (`USE_INMEMORY_CHANNEL_LAYER=0`).

## 1. Environment variables (backend/.env)

Copy `.env.example` and set:

| Variable | Production value |
|---|---|
| `DJANGO_SECRET_KEY` | long random string (`python -c "import secrets; print(secrets.token_urlsafe(64))"`) |
| `DJANGO_DEBUG` | `0` |
| `DJANGO_ALLOWED_HOSTS` | your API hostname(s), comma-separated |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT` | your PostgreSQL instance |
| `CORS_ALLOWED_ORIGINS` | the SPA origin(s), e.g. `https://app.example.com` |
| `USE_INMEMORY_CHANNEL_LAYER` | `0` |
| `REDIS_URL` | `redis://<host>:6379/0` |
| `EMAIL_BACKEND` | `django.core.mail.backends.smtp.EmailBackend` (+ standard SMTP vars) if email copies are wanted |
| `QUEUEWISE_SEND_EMAIL_NOTIFICATIONS` | `1` to send email copies of notifications |
| `DJANGO_SSL_REDIRECT` | `1` when TLS terminates upstream |

With `DJANGO_DEBUG=0` the settings enable secure/HttpOnly session cookies,
HSTS, and `X-Frame-Options: DENY`. Never commit the real `.env`.

## 2. Backend

```bash
python -m venv venv && venv/bin/pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check --deploy          # review the deployment checklist
daphne -b 127.0.0.1 -p 8001 config.asgi:application
```

Run under a process supervisor (systemd unit / platform worker). A minimal
systemd unit:

```ini
[Unit]
Description=QueueWise ASGI
After=network.target

[Service]
User=queuewise
WorkingDirectory=/srv/queuewise/backend
EnvironmentFile=/srv/queuewise/backend/.env
ExecStart=/srv/queuewise/backend/venv/bin/daphne -b 127.0.0.1 -p 8001 config.asgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

## 3. Frontend

```bash
npm ci
npm run build     # emits dist/
```

Serve `dist/` at your SPA origin. For a single-origin deployment, proxy `/api/`
and `/ws/` from the same host to the Daphne process, so the session cookie is
first-party and no CORS is involved. The Vite dev proxy shows the exact shape:

```
/api  -> http://127.0.0.1:8001
/ws   -> ws://127.0.0.1:8001   (WebSocket upgrade)
```

SPA routing requires all unknown paths to serve `index.html` (standard
`try_files $uri /index.html;`).

## 4. Database provisioning

```sql
CREATE ROLE queuewise_app LOGIN PASSWORD '<strong password>' NOSUPERUSER;
CREATE DATABASE queuewise OWNER queuewise_app;
```

Migrations are applied with `python manage.py migrate` (idempotent). Take a
backup before each deploy: `pg_dump -Fc queuewise > backup.dump`.

## 5. Security checklist

- [ ] `DJANGO_DEBUG=0`, random `DJANGO_SECRET_KEY`, TLS everywhere.
- [ ] Database user has no superuser rights; least-privilege on the schema.
- [ ] CORS restricted to the real SPA origins (`CORS_ALLOWED_ORIGINS`).
- [ ] Redis channel layer protected with a password / private network.
- [ ] Secrets only via environment or a secret manager — never in git.
- [ ] Session cookies are HttpOnly + Secure (automatic when `DEBUG=0`).
- [ ] Rate limiting at the proxy (the app also throttles auth and API traffic).

## 6. Demo data

`python manage.py seed_demo` creates `[DEMO]`-prefixed records and
`@demo.queuewise.local` accounts. It refuses to run twice. For a clean
production deployment simply skip it.
