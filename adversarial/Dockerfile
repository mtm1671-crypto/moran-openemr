FROM python:3.12-slim

ENV ADVERSARIAL_SQLITE_PATH=/data/week3_runs.sqlite
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
COPY evals ./evals
COPY migrations ./migrations

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir .

RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /data

EXPOSE 8080

CMD ["sh", "-c", "mkdir -p /data && chown -R appuser:appuser /data && exec su -s /bin/sh -c 'python -m uvicorn app.ui:create_app --factory --host 0.0.0.0 --port ${PORT:-8080}' appuser"]
