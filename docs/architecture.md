# Accountant architecture

This repository contains only the Accountant FastAPI backend. The React
frontend lives in the separate `accountant-frontend` repository and communicates
with this service only through the HTTP API.

## Local containers

Backend Docker Compose starts `accountant-backend` on port 3001 and
`accountant-postgres` on port 5432. The API reaches PostgreSQL through the
Compose service name `postgres`. PostgreSQL data is stored in a named volume and
survives `docker compose down`. The frontend has its own Docker project.

## Backend dependency direction

```text
presentation -> application -> domain
infrastructure -> application/domain
```

- `domain`: entities, value objects and business rules; no FastAPI or database imports
- `application`: use cases and ports for database, clock and email operations
- `infrastructure`: SQLAlchemy repositories and Gmail SMTP adapter
- `presentation`: FastAPI routes and future scheduled-job entry points

The current `system` module is the smallest example of this direction. Business
modules will be added one phase at a time.

## Frontend structure

The React app is built by Vite. As features are introduced, each feature will
contain its own components, API calls and view models. Server-side rendering and
Next.js are intentionally not used.

## Initial bounded contexts

- Identity and access
- Ledger and categories
- Recurring transactions
- Budgets
- Savings
- Notifications
- Administration and audit

## Identity and access

Identity is persisted in `users`, `roles`, `permissions`, `user_roles`,
`role_permissions` and `refresh_tokens` tables. New registrations receive the
`USER` role. The role currently has `finance.read.self` and
`finance.write.self` permissions. The `ADMIN` role additionally receives
`finance.read.any`, `users.read` and `users.manage`.

Registration only ever grants the `USER` role, and no endpoint hands out
`ADMIN`; that role is assigned directly in the database.

Passwords are hashed with Argon2. Authentication uses a 15-minute signed access
JWT and a 30-day opaque refresh token stored in separate HTTP-only, same-site
cookies so browser JavaScript cannot read either token. Refresh tokens rotate on
use; only their SHA-256 hashes are persisted and logout revokes the active
refresh token. FastAPI permission dependencies load current roles and
permissions from PostgreSQL for each protected request.

## Financial rules

- Monetary values are stored as integer minor units (kuruş), never floating point.
- Dates are persisted in UTC and interpreted using the user's time zone.
- Scheduled transactions and posted transactions are separate concepts.
- Savings transfers do not count as spending.

## Ledger and categories

`categories` contains shared defaults and user-owned custom categories.
`transactions` contains posted income and expense records, always scoped by
`user_id`. Category ownership and income/expense type matching are enforced in
the application layer, while positive minor-unit amounts and valid types are
also protected by database constraints. List queries require an explicit time
range and filter by the authenticated user; category and kind are optional
extra filters. Posted transactions can be edited and deleted one by one, and
an edit revalidates category ownership and kind exactly like a new record.

Each user also carries a signed `opening_balance_minor`, the money held before
the account existed. It is added to the current balance wherever a balance is
reported, but it is not a transaction, so it never appears in a list, a monthly
cash flow or a savings month.

## Recurring subscriptions

`subscriptions` stores active monthly payment definitions separately from
posted `transactions`. Due processing catches up every unpaid month, advances
the next charge date while preserving the original billing day, and links each
generated expense back to its subscription. A unique
`subscription_id + subscription_charge_date` constraint makes processing
idempotent. Removing a subscription is a soft deactivation so historical
transactions remain intact.

## Administration

Administration reuses the identity and ledger tables instead of owning storage.
Read endpoints require both `users.read` and `finance.read.any` and stay
read-only: an administrator sees another user's totals, recent transactions,
category spending and active subscriptions but cannot change their records.

The single write is switching a user active or inactive, which requires
`users.manage` and is guarded in the application layer so an administrator
cannot deactivate their own account. Role changes are deliberately not exposed,
so the panel can never widen anyone's access.

## Notifications

Daily summaries will be scheduled inside the Python application. Email will be
sent directly with Gmail SMTP and Python's standard `smtplib`; no external email
delivery provider will be introduced. For the first deployment, the scheduler
will run as a single application process to avoid duplicate jobs.
