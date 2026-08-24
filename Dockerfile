FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . ./

EXPOSE 3001

# The production command, so a forgotten override degrades into a real server
# rather than a development one. Development trades it for `--reload` in
# docker-compose.yml.
#
# Deliberately a single worker: the subscription and notification schedulers run
# inside the application process, so a second worker would post every due
# subscription and send every daily summary twice.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 3001"]
