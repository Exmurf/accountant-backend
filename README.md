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
