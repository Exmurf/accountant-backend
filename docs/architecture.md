# Accountant architecture

This repository contains only the Accountant FastAPI backend. The React
frontend lives in the separate `accountant-frontend` repository and communicates
with this service only through the HTTP API.

## Local containers

Backend Docker Compose starts `accountant-backend` on port 3001 and
`accountant-postgres` on port 5432. The API reaches PostgreSQL through the
Compose service name `postgres`. PostgreSQL data is stored in a named volume and
survives `docker compose down`. The frontend has its own Docker project.

## Production containers

`docker-compose.prod.yml` runs the same services with the development
affordances removed: no bind mount, no published database port, no reloading
server. A fourth container fronts them with Caddy, which serves the built
frontend and proxies `/api` to the API, so both halves share one origin and the
session cookies are first-party. See `docs/deploy.md`.

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

Changing a password ends every other session. The stored refresh tokens are
revoked, and `users.password_changed_at` records the moment so an access token
minted before it is refused on its next request rather than living out its
fifteen minutes. Because a JWT `iat` is a whole number of seconds, the marker is
stored at the same resolution and the session that made the change keeps the
token it was just handed.

Sign-in, registration and password change are rate limited in the API process.
Sign-in counts only failures, so repeatedly signing in successfully never costs
a user their quota, and a correct password clears the account's counter. Two
keys are held at once: one per email address, which catches guessing spread
across many source addresses, and a wider one per source address, which catches
one caller scanning many accounts. A correct password clears only the account
key, so signing in cannot wipe a scan run from the same address. An unknown
address and a wrong password are indistinguishable to the caller, so the limit
cannot be read as an answer to whether an account exists. Password change is
keyed by user because reaching it already requires a session.

The window lives in memory rather than in PostgreSQL. One process serves the
API, so a process-local count is enough, and a restart forgiving outstanding
lockouts is the safe direction for a mechanism that can shut a real user out of
their own account. `X-Forwarded-For` is deliberately ignored: nothing in front
of this service is trusted to set it, and honouring a caller-controlled header
would let an attacker rotate their own key. A trusted-proxy list belongs here
before the service runs behind a reverse proxy.

A forgotten password is recovered through `password_reset_tokens`, which holds
only the SHA-256 digest of a link that was mailed once, so the table cannot be
turned back into a working link. Requesting a reset retires whatever the user
already had, because asking again is how somebody recovers from a mail that
never arrived and a forwarded older link must not still open the account.
Spending a token happens in the transaction that reads it, so two requests
carrying the same link cannot both succeed, and an expired or already-used one
is refused. A completed reset revokes every refresh token and stamps
`password_changed_at`, on the assumption that the reason for the reset was
somebody else getting in.

The request endpoint answers the same way for an address that is registered and
one that is not, and does all of its work after the response has been sent, so
neither the reply nor its timing answers whether an account exists. Reserved
example domains are skipped, so a seeded account never has an unusable token
issued for it. Following the link does not open a session: it proves the caller
holds the mailbox, not that they are at a trusted device, so they sign in with
the new password like anyone else.

Changing an address works the same way and differs on purpose in three places.
The confirmation link goes to the new address, because holding that mailbox is
the only thing that proves it belongs to the person asking, and the address
being left behind is told separately, without a link, so its owner notices a
change they did not make. The current password is required: mail is the
recovery channel, so a stolen session that could repoint it would become a
permanent takeover. Sessions survive, because the password was proved when the
change was asked for and nothing suggests the account is in the wrong hands.

Whether the new address is already registered is stated plainly rather than
hidden. Password reset has to stay silent because anyone may call it; this
endpoint needs a session and is rate limited, so the lookup costs an account and
a long wait, while staying quiet would leave somebody waiting on a mail that was
never going to arrive. The address is checked again when the link is followed,
since it was only free at the moment the mail was sent, and the unique index on
`users.email` has the last word.

## Caching

Ledger reads go through a cache before PostgreSQL, and a write invalidates by
bumping a version number folded into the key rather than deleting anything.
Deleting everything one user touched would mean scanning the keyspace for a
pattern, which Redis walks key by key; a version turns the same job into one
INCR, and the entries nobody will read again fall out when their time expires.

Invalidation is driven by SQLAlchemy session events rather than by each
repository remembering to ask, so a write through any path is caught. It fires
after the commit, not during the flush: doing it earlier leaves a window where
a concurrent reader still sees the old rows, misses, and stores what it read
under the version meant to replace it, which is the one shape of this bug that
does not heal on its own. A rolled-back flush invalidates nothing.

A cached transaction carries the name and colour of its category, so editing a
category invalidates too — the owner's namespace for a custom one, and every
namespace for a shared default.

Nothing here is a source of truth. Every call may fail, and when it does the
read falls through to PostgreSQL, so an unreachable cache costs a query rather
than an error. Timeouts are a quarter of a second, because a cache that hangs
is worse than no cache at all, and an outage is logged once rather than once
per call. With no `REDIS_URL` configured the application runs on a cache that
misses everything, which keeps the uncached path identical to the cached one
instead of leaving it to rot behind a conditional.

## Financial rules

- Monetary values are stored as integer minor units (kuruş), never floating point.
- Dates are persisted in UTC and interpreted using the user's time zone.
- Scheduled transactions and posted transactions are separate concepts.
- Savings transfers do not count as spending.
- A user may set a savings goal; leaving it at zero lets the chart pick the next
  round number above the balance instead.
- A savings history starts at the earlier of the account's first month and its
  oldest transaction. Signing up does not mark where the money starts: a
  transaction can be recorded with any past date, and a month the monthly close
  never walks over is one that stays missing from savings for good.

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

## Recurring transactions

`subscriptions` stores active monthly definitions separately from posted
`transactions`. An entry is income or expense according to the category it is
bound to rather than a column of its own, so a salary and a streaming plan use
the same table and a category change moves future charges with it. Past
transactions keep the kind they were posted with.

Due processing catches up every unpaid month, advances the next charge date
while preserving the billing day, and links each generated transaction back to
its definition. A unique `subscription_id + subscription_charge_date`
constraint makes processing idempotent, so it is safe to run repeatedly.
Editing an entry may change its name, category, amount and billing day; a new
billing day moves the pending charge inside its own month and is clamped for
months too short for it. Removing an entry is a soft deactivation so historical
transactions remain intact.

Due processing runs on a scheduler inside the application rather than waiting
for someone to open the app, so a balance is correct after a month away. It
sweeps every active user hourly and on start; a user who does open the app
still triggers the same processing for an immediate result. Because processing
is idempotent, the two paths cannot double-charge each other.

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

Daily summaries are scheduled inside the Python application. Email is sent
directly with Gmail SMTP and Python's standard `smtplib`; no external email
delivery provider is used. The scheduler runs as a single application process
to avoid duplicate jobs.

A use case builds a `MailMessage` — a greeting, paragraphs, one headline
figure, rows, an action and a notice — and never any markup. The mail adapter
turns that into the text and the markup halves of a `multipart/alternative`
message, so changing the template never reaches into a business rule, and a use
case never has to know that Outlook still renders with Word. Layout is tables
with inline styles for the same reason: no client can be relied on to keep a
stylesheet, and none of them support flexbox. Everything a reader supplies is
escaped, since a display name and a category name are theirs to choose. An
action always prints its link as text underneath, because clients strip buttons
and people forward these to a machine where the link gets copied by hand.

A summary covers a day, not a moment, so the sweep looks back a few days and
sends any day that has no delivery recorded yet, oldest first. Only today was
ever considered before, which meant a night with the service stopped lost that
day's summary for good. The look-back is deliberately short: returning from a
long outage should not fire off a fortnight of mail at once. Days before the
account existed are never owed, and a catch-up names its date instead of
calling itself today.

A budget warning is keyed by category, month and the limit itself. Raising a
limit therefore opens a fresh warning for the new ceiling, because somebody who
deliberately moved the line still expects to hear about crossing it; leaving the
limit alone keeps the old key, which is what stops a warning arriving with every
purchase.
