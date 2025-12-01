# ---------- BASE IMAGE ----------
FROM python:3.13-slim AS base

LABEL maintainer="Cihat Ertem <cihatertem@gmail.com>"

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PYTHONDONTWRITEBYTECODE=1

RUN groupadd -g 1000 -r app && useradd -u 1000 --no-log-init -r -g app app

RUN apt-get update && apt-get install -y curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt clean -y \
    && apt autopurge -y

RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && mv /root/.local/bin/uv /usr/local/bin/uv \
    && chmod 755 /usr/local/bin/uv
ENV UV_CACHE_DIR=/app/.cache/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./


RUN uv sync --frozen

COPY . .

RUN chown -R app:app /app

USER app

EXPOSE 9002

# ---------- DEV STAGE ----------
FROM base AS dev

ENV DJANGO_DEBUG=1

CMD ["uv", "run", "python", "manage.py", "runserver", "0.0.0.0:9002"]

# ---------- PROD STAGE ----------
FROM base AS prod

ENV DJANGO_DEBUG=0

RUN uv run python manage.py collectstatic --noinput

CMD ["uv", "run", "gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:9002", "--workers", "3"]
