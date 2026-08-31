# Accountant API

FastAPI backend for Accountant. The source is split into domain, application,
infrastructure and presentation layers.

## Local setup

```bash
cd accountant-backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 3001
```

API documentation is available at `http://localhost:3001/api/docs`.

## Docker

This repository owns both the FastAPI service and its local PostgreSQL
dependency. Start them from the backend project root:

```bash
cp .env.example .env
docker compose up -d --build
```

Stop them without deleting PostgreSQL data:

```bash
docker compose down
```

Run migrations manually when the API is not started through Docker:

```bash
alembic upgrade head
```

The Docker container applies migrations automatically before Uvicorn starts.

When run independently, settings are read from `.env`. The file is ignored by
Git; create it from `.env.example` for a fresh checkout. The
backend Docker Compose passes the same settings through container environment
variables. The frontend is a separate repository and is not required to build
or start this project.

The example contains only values that belong to the operator-managed `.env`.
Compose derives `DATABASE_URL` from the PostgreSQL settings and injects
`REDIS_URL`; production also forces secure cookies and its trusted proxy range.
Those generated values are deliberately not duplicated in `.env`.

### Cloudflare-only production origin

Production publishes only the Caddy container on ports 80 and 443. After the
domain is proxied through Cloudflare, install
`ops/cloudflare-origin-firewall.sh` and its systemd unit on the VM to reject
direct web requests to the Azure address while leaving SSH untouched:

```bash
sudo install -m 0755 ops/cloudflare-origin-firewall.sh \
  /usr/local/sbin/accountant-cloudflare-origin-firewall
sudo install -m 0644 ops/accountant-cloudflare-firewall.service \
  /etc/systemd/system/accountant-cloudflare-firewall.service
sudo systemctl daemon-reload
sudo systemctl enable --now accountant-cloudflare-firewall.service
```

The allowlist comes from Cloudflare's published IPv4 and IPv6 ranges. Verify it
with `sudo accountant-cloudflare-origin-firewall status`. To recover direct
origin access, run `sudo systemctl stop accountant-cloudflare-firewall`.

## Tests

The development image carries the test runner, so the suite runs where the
application runs:

```bash
docker compose exec backend pytest
```

It has two halves. The unit tests cover the use cases in `app/application`
against in-memory stand-ins for their ports, need nothing running, and finish
in under a second. The API tests go through HTTP with `TestClient` and need
PostgreSQL, which is why they are marked:

```bash
docker compose exec backend pytest -m "not api"   # unit only
docker compose exec backend pytest -m api         # HTTP only
```

They use a database of their own, named after the configured one with a `_test`
suffix, created and migrated on first run. Every API test empties the tables
first, so the suite refuses to start unless the name ends in `_test` — pointed
at the real database it would destroy it. Set `TEST_DATABASE_URL` to override
where it goes.

Nothing leaves the process. `tests/conftest.py` blanks the mail credentials
before the application is imported, and the tests that need mail switched on
replace the sender itself, so a working Gmail app password in `.env` can never
turn a test run into real mail.

`tests/api/test_authorization.py` compares the application's own route list
against a table of which endpoints are public and which require a session, so
an endpoint added without deciding who may call it fails the suite rather than
slipping through review.

To run the suite on the host instead, install the test dependencies alongside
the application's:

```bash
pip install -r requirements-dev.txt
pytest
```

## Gmail notifications

Accountant sends mail directly through Gmail SMTP; no additional mail service
is required. Create a Google App Password for the sender account and add these
values to the local `.env` file:

```env
MAIL_USERNAME=sender@gmail.com
MAIL_APP_PASSWORD=your_16_character_app_password
```

Do not use or share the Gmail account's normal password. `.env` is ignored by
Git. When both mail values are present, the API sends one expense summary per
active user after that user's selected local time and one warning when a
category first exceeds its monthly limit. New users default to 21:00 and can
change the time from the application settings. Example-domain accounts are
skipped.

If the service is stopped when a summary was due, the sweep still catches it:
it looks back `DAILY_SUMMARY_CATCHUP_DAYS` days and sends any day with no
delivery recorded, oldest first, naming the date rather than calling it today.
Set it to `0` to send only the current day. A budget warning is keyed by
category, month and limit, so it arrives once per limit: raising a limit opens
a fresh warning for the new ceiling, while leaving it alone keeps the account
quiet for the rest of the month.

Paste the app password without the spaces Google shows it with. Docker Compose
passes `env_file` values through untouched, so a stray trailing space becomes
part of the password and Gmail answers `535 Authentication failed`.

## Caching

Docker Compose starts Redis alongside PostgreSQL and the API. Ledger reads are
served from it and invalidated automatically when anything is written, so
nothing has to be cleared by hand.

When running Uvicorn directly on the host instead of through Docker, opt into
the host Redis instance explicitly:

```env
REDIS_URL=redis://localhost:6379/0
CACHE_TTL_SECONDS=300
```

Leave `REDIS_URL` empty to run without a cache; every read then goes straight
to PostgreSQL and the application behaves the same way. Redis being down is not
an outage either — reads fall through and one warning is written to the log.

## Rate limiting

Sign-in, registration and password change are limited per source address, and
sign-in additionally per email address. Only failed sign-ins count, so a
correct password never costs a user their quota and clears the account's
counter. Exceeding a limit answers `429` with a `Retry-After` header. The
defaults below can be tuned in `.env`, and `RATE_LIMIT_ENABLED=false` turns the
whole mechanism off for local work.

```env
LOGIN_MAX_ATTEMPTS=5          # per email, per window
LOGIN_IP_MAX_ATTEMPTS=30      # per source address, per window
LOGIN_WINDOW_SECONDS=900
REGISTER_MAX_ATTEMPTS=5
REGISTER_WINDOW_SECONDS=3600
```

The counters are held in the API process, so restarting it clears every
outstanding lockout.

## Password reset

`POST /auth/password/forgot` mails a single-use link and always answers `202`,
whether or not the address is registered. The link expires after
`PASSWORD_RESET_TOKEN_MINUTES` and lands on the web app with a `reset_token`
query parameter, which opens the reset screen; `POST /auth/password/reset`
spends it. Requesting a new link retires the previous one, and completing a
reset signs out every other session.

The link is built from `WEB_ORIGIN`, so that value has to match the address the
browser actually uses or the mail will point somewhere unreachable. Mail must be
configured for any of this to work; without it the request is logged and
dropped.

## Changing an address

`POST /auth/email/change` needs a session and the account's current password,
and mails a confirmation link to the new address while telling the old one what
was requested. Nothing changes until `POST /auth/email/confirm` spends the
token, which the web app does on its own when it is opened with an
`email_token` query parameter. An address already in use is refused outright,
both when the change is asked for and again when the link is followed.
