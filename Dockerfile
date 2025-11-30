# ---------- BASE IMAGE ----------
FROM python:3.13-slim AS base

LABEL maintainer="Cihat Ertem <cihatertem@gmail.com>"

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PYTHONDONTWRITEBYTECODE=1

#RUN groupadd -r app && useradd --no-log-init -r -g app app
RUN groupadd -g 1000 -r app && useradd -u 1000 --no-log-init -r -g app app
# Sistem bağımlılıkları (curl vs.)
RUN apt-get update && apt-get install -y curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt clean -y \
    && apt autopurge -y

# uv kurulum
#RUN curl -LsSf https://astral.sh/uv/install.sh | sh
#ENV PATH="/root/.local/bin:${PATH}"

RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && mv /root/.local/bin/uv /usr/local/bin/uv \
    && chmod 755 /usr/local/bin/uv
ENV UV_CACHE_DIR=/app/.cache/uv

# Çalışma dizini
WORKDIR /app

# Sadece bağımlılık dosyalarını kopyala (build cache için iyi)
COPY pyproject.toml uv.lock ./

# Prod için istersen:
# ENV UV_NO_DEV=1

# Bağımlılıkları kilit dosyasına göre kur
RUN uv sync --frozen

# Proje kodunu kopyala
COPY . .

RUN chown -R app:app /app

USER app

# Django runserver portu
EXPOSE 9002

# ---------- DEV STAGE ----------
FROM base AS dev

ENV DJANGO_DEBUG=1

# Dev ortamda uv ile runserver
CMD ["uv", "run", "python", "manage.py", "runserver", "0.0.0.0:9002"]

# ---------- PROD STAGE ----------
FROM base AS prod

# Prod ortam değişkenleri (override edebilirsin)
ENV DJANGO_DEBUG=0

# Statikleri prod build aşamasında topla
RUN uv run python manage.py collectstatic --noinput

# Gunicorn ile çalıştır (config.wsgi:application)
CMD ["uv", "run", "gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:9002", "--workers", "3"
