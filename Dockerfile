# ---------- BASE STAGE ----------
FROM python:3.14-slim AS base

LABEL maintainer="Cihat Ertem <cihatertem@gmail.com>"

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PYTHONDONTWRITEBYTECODE=1

RUN groupadd -g 1000 -r app \
    && useradd \
    -u 1000 \
    --no-create-home\
    --shell "/sbin/nologin" \
    --no-log-init \
    -r -g app app

WORKDIR /app

EXPOSE 9002

# ---------- BUILDER STAGE ----------
FROM base AS builder

RUN apt-get update && apt-get install -y --no-install-recommends curl gcc \
    && rm -rf /var/lib/apt/lists/* \
    && apt clean -y \
    && apt autopurge -y

ENV UV_INSTALL_DIR=/usr/local/bin \
    UV_COMPILE_BYTECODE=1 \
    UV_CACHE_DIR=/var/cache/uv \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    VIRTUAL_ENV=/opt/venv

RUN mkdir -p /var/cache/uv \
    && chown -R app:app /var/cache/uv

RUN curl -LsSf https://astral.sh/uv/install.sh | sh

COPY pyproject.toml uv.lock ./

RUN uv venv "$VIRTUAL_ENV"

RUN uv sync --frozen --no-cache --no-dev --active

# ---------- DEV STAGE ----------
FROM base AS dev

ENV DJANGO_DEBUG=1 \
    UV_CACHE_DIR=/var/cache/uv \
    UV_PROJECT_ENVIRONMENT=/opt/venv

COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv
COPY --from=builder /var/cache/uv /var/cache/uv
COPY --from=builder /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH" \
    VIRTUAL_ENV=/opt/venv

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-cache --active

COPY . .

RUN chown -R app:app /app
RUN chown -R app:app /var/cache/uv

USER app

CMD ["uv", "run", "python", "manage.py", "runserver", "0.0.0.0:9002"]

# ---------- PROD STAGE ----------
FROM base AS prod

ENV DJANGO_DEBUG=0

ENV VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

COPY --from=builder /opt/venv /opt/venv

COPY . .

RUN mkdir -p /app/staticfiles /app/media \
    && chown -R app:app /app

RUN python manage.py collectstatic --noinput

USER app

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:9002", "--workers", "2"]
