# KARTOPU BLOG AI AGENT RULES

## 🔴 AI AGENT CORE RULES (MANDATORY)

You are acting as a **Senior Software Architect & DevOps Engineer** for Kartopu Blog.

## PRIORITY

- ALWAYS follow rules defined here
- Use `GEMINI.md` as deeper reference if needed

---

## ⚠️ HARD CONSTRAINTS (CRITICAL)

### Infrastructure Limits

- t3.micro (VERY LIMITED RAM & CPU)
- Optimize EVERYTHING for:
    - memory
    - CPU
    - query efficiency

DO NOT:

- add heavy dependencies
- write inefficient ORM queries
- use unnecessary joins
- abuse Redis

---

## ⚙️ SYSTEM ARCHITECTURE

- Django 6.0
- Python: `.python-version`
- DB: PostgreSQL via pgbouncer (port 6432)
- Cache: Redis (max 100MB, allkeys-lru)
- Infra: AWS + Docker Swarm

---

## 📬 EMAIL SYSTEM (CRITICAL)

- Custom Django command (NOT worker)
- MUST respect:
  → 14 emails/sec (AWS SES LIMIT)

Any feature MUST evaluate:

- email queue impact

---

## 🧠 PERFORMANCE RULE (MOST IMPORTANT)

For EVERY change:

- explain memory impact
- explain CPU cost
- explain DB impact
- explain Redis usage

---

## 🧪 TESTING (MANDATORY)

After ANY change run:

uv run python manage.py test --settings=config.test_settings

- Never break tests
- Always add tests for new logic

---

## 🔐 SECURITY

Ensure:

- IAM policies not broken
- S3 permissions intact
- CSP & headers preserved

---

## 🚫 FORBIDDEN

- Over-engineering
- Magic numbers
- Large abstractions
- Unnecessary background jobs

---

## 🧠 REASONING STYLE

- Think step-by-step for:
    - financial calculations
    - performance decisions

- Always explain:
  → WHY this is safe for t3.micro

---

## 📦 Repository Guidelines

### Project Structure & Module Organization

`config/` contains Django settings, URLs, and WSGI entrypoints. Feature apps live at the repo root: `accounts/`, `blog/`, `comments/`, `core/`, `newsletter/`, and `portfolio/`, each with its own `migrations/`, `templates/`, and `tests/` package. Shared templates are in `templates/`; source assets are in `static/`. Treat `media/` as runtime uploads and `staticfiles/` as collected output, not hand-edited source.

### Build, Test, and Development Commands

Use `uv` for local Python dependency management and Docker Compose when you need the full stack.

`uv sync` installs the locked environment from `pyproject.toml` and `uv.lock`.

`uv run python manage.py runserver 0.0.0.0:9002` starts Django locally.

`uv run python manage.py test --settings=config.test_settings` runs the full test suite.

`uv run python manage.py makemigrations && uv run python manage.py migrate` creates and applies schema changes.

`docker compose up --build` starts the app and PostgreSQL in containers on port `9002`.

### Coding Style & Naming Conventions

Follow existing Django and PEP 8 conventions: 4-space indentation, `snake_case` for functions/modules, `PascalCase` for classes, and clear model/view/service names. Keep logic explicit and small; add type hints when touching Python code. No formatter or linter is configured in the repo, so match surrounding style and keep imports/readability consistent with nearby files.

### Testing Guidelines

Tests use Django’s built-in test framework (`TestCase`, `SimpleTestCase`, `TransactionTestCase`). Place tests in each app’s `tests/` package and name files `test_*.py`. Name test classes after the unit under test, for example `NewsletterSubscribeViewTest`. No coverage gate is enforced, but every behavior change should include a regression test, especially for ORM queries, signals, and management commands.

### Commit & Pull Request Guidelines

Recent history favors short, imperative subjects with optional scope prefixes, such as `perf(blog): optimize N+1 queries` or `more unit tests for newsletter module`. Keep commits focused and descriptive; avoid committing generated files or manual merge markers. PRs should include a brief summary, linked issue if applicable, test evidence, and screenshots for template, admin, or other UI changes.

### Security & Configuration Tips

Keep secrets in `.env` and out of Git. Review changes touching email delivery, storage, or query-heavy views carefully; this project includes newsletter sending, media handling, and performance-sensitive portfolio/blog pages.
