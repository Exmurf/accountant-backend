# Deploying Accountant

One virtual machine runs everything: PostgreSQL, Redis, the API and a reverse
proxy that serves the built frontend. Four containers, one compose file,
`docker-compose.prod.yml`.

## What the machine needs

Oracle Cloud's Always Free tier has two separate offers, and the small one is
not enough. The AMD `E2.1.Micro` shapes give 1 GB of RAM each; `pnpm build`
alone will run out of memory there, never mind PostgreSQL beside it. The ARM
`A1.Flex` shape is also always free and gives 4 OCPUs with 24 GB of RAM,
splittable across up to four instances. Take one instance from that pool with
2 OCPUs and 12 GB.

Two things to know about that pool. ARM capacity is frequently exhausted in
popular regions, so the instance may need several attempts over a few days. And
Oracle reclaims Always Free instances that stay idle, which a personal finance
app easily is; upgrading the tenancy to Pay As You Go exempts it and keeps the
free resources free.

The ARM shape is `aarch64`. Every image used here publishes an arm64 build, so
nothing needs changing — but build the images on the server rather than pushing
ones built on an x86 laptop.

## One origin

The proxy serves the frontend at `/` and forwards `/api/*` to the API. That is
the whole reason the deployment is this small:

- Session cookies are first-party, so `samesite=lax` needs no exception.
- CORS never applies, because there is only one origin.
- Caddy gets the certificate from Let's Encrypt by itself, which is what lets
  `COOKIE_SECURE` be true.

A certificate needs a **hostname**; Let's Encrypt will not issue one for a bare
IP address. Any name pointing an `A` record at the instance works, including a
free dynamic-DNS subdomain.

## Preparing the instance

Open ingress for TCP 80 and 443 in the instance's security list or network
security group. That is necessary but not sufficient: Oracle's Ubuntu images
also ship pre-seeded `iptables` rules, so the same two ports have to be opened
inside the machine and saved with `netfilter-persistent`. Forgetting the second
half is the usual reason a fresh instance answers nothing.

Then install Docker, enable it at boot (`systemctl enable --now docker`), and
check out both repositories side by side:

```text
/opt/accountant/accountant-backend
/opt/accountant/accountant-frontend
```

The side-by-side layout is not cosmetic: `docker-compose.prod.yml` builds the
`web` image from `../accountant-frontend`.

## Configuration

Production reads the same `.env` in the backend repository. Compose refuses to
start if any of these is missing, so there is no silent fallback to a
development password:

| Variable            | Value                                             |
| ------------------- | ------------------------------------------------- |
| `SITE_ADDRESS`      | the hostname, e.g. `paran.example.com`            |
| `WEB_ORIGIN`        | `https://` and the same hostname                  |
| `POSTGRES_PASSWORD` | freshly generated, not the development one        |
| `JWT_SECRET_KEY`    | freshly generated; changing it signs everyone out |

`COOKIE_SECURE` and `TRUSTED_PROXY_IPS` are set by the compose file and ignore
whatever `.env` says, so a development file copied onto the server cannot quietly
turn the secure cookie off. Mail settings carry over unchanged.

`WEB_ORIGIN` has no such protection — a value in `.env` satisfies the guard — so
the application checks it once more at startup and refuses to boot if the origin
is plain `http://` while cookies are secure. A stack that will not start with
that message is a `.env` still pointing at localhost.

## Running it

```bash
cd /opt/accountant/accountant-backend
docker compose -f docker-compose.prod.yml up -d --build
```

Migrations run in the backend's start command, so a deploy is the same two
lines again. To follow it:

```bash
docker compose -f docker-compose.prod.yml logs -f backend web
```

## Before there is a domain

Get the hostname first. A free dynamic-DNS name takes a couple of minutes, and
everything below depends on it.

Without one, `SITE_ADDRESS=:80` will serve plain HTTP and is enough to confirm
the machine answers from the internet — the login screen will appear. Logging in
will not work, and that is deliberate: the cookie is marked secure, so the
browser will not return it over a plain connection. The stack does not offer a
switch for that, because the switch would mean putting the session cookie on the
wire where anyone on the path can lift it and be you.

## Deliberately not here

No log rotation, no database backup, no test suite. Each is a real gap for an
application with users, and none of them is a gap for one person checking their
own spending. Revisit them before anyone else gets an account.
