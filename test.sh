#!/bin/bash
docker compose run --rm kartopu uv run python manage.py test --parallel 8 --settings=config.test_settings ; docker compose down
