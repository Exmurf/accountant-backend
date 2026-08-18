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
