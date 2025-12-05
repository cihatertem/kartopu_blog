# ---------- BASE STAGE ----------
FROM python:3.13-slim AS base

LABEL maintainer="Cihat Ertem <cihatertem@gmail.com>"

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PYTHONDONTWRITEBYTECODE=1

RUN groupadd -g 1000 -r app && useradd -u 1000 --no-create-home --no-log-init -r -g app app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt clean -y \
    && apt autopurge -y

ENV UV_INSTALL_DIR=/usr/local/bin
ENV UV_COMPILE_BYTECODE=1
ENV UV_CACHE_DIR=/var/cache/uv

RUN mkdir -p /var/cache/uv \
    && chown -R app:app /var/cache/uv

RUN curl -LsSf https://astral.sh/uv/install.sh | sh

WORKDIR /app

COPY pyproject.toml uv.lock ./

EXPOSE 9002

# ---------- DEV STAGE ----------
FROM base AS dev

ENV DJANGO_DEBUG=1

RUN uv sync --frozen --no-cache

COPY . .

RUN chown -R app:app /app

USER app

CMD ["uv", "run", "python", "manage.py", "runserver", "0.0.0.0:9002"]

# ---------- PROD STAGE ----------
FROM base AS prod

ENV DJANGO_DEBUG=0

RUN uv sync --frozen --no-cache --no-dev

COPY . .

RUN mkdir -p /app/staticfiles /app/media \
    && chown -R app:app /app

RUN uv run python manage.py collectstatic --noinput

USER app

CMD ["uv", "run", "gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:9002", "--workers", "3"]
