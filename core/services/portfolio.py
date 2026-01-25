from __future__ import annotations

import secrets
import string
from datetime import date

from django.db import models
from django.utils.text import slugify

SLUG_HASH_LENGTH = 6
SLUG_HASH_ALPHABET = string.ascii_lowercase + string.digits


def build_snapshot_name(owner_label: str, snapshot_date: date | None) -> str:
    if snapshot_date:
        return f"{owner_label} - {snapshot_date}"
    return f"{owner_label}"


def format_snapshot_label(
    *,
    slug: str | None,
    name: str | None,
    owner_label: str,
    snapshot_date: date | None,
) -> str:
    if slug:
        return slug
    if name:
        return name
    return build_snapshot_name(owner_label, snapshot_date)


def build_comparison_name(base_snapshot, compare_snapshot) -> str:
    base_label = (
        base_snapshot.name
        if base_snapshot and getattr(base_snapshot, "name", None)
        else f"{base_snapshot}"
    )
    compare_label = (
        compare_snapshot.name
        if compare_snapshot and getattr(compare_snapshot, "name", None)
        else f"{compare_snapshot}"
    )
    if base_label and compare_label:
        return f"{base_label} → {compare_label}"
    return base_label or compare_label


def format_comparison_label(
    *,
    slug: str | None,
    name: str | None,
    base_snapshot,
    compare_snapshot,
) -> str:
    if slug:
        return slug
    if name:
        return name
    return f"{base_snapshot} → {compare_snapshot}"


def _build_slug_base(name: str, max_length: int) -> str:
    base = slugify(name, allow_unicode=True)
    if not base:
        base = "snapshot"
    max_base_length = max_length - (SLUG_HASH_LENGTH + 1)
    if max_base_length < 1:
        return base
    return base[:max_base_length]


def generate_unique_slug(model_cls: type[models.Model], name: str) -> str:
    base = _build_slug_base(name, max_length=255)
    while True:
        hash_part = "".join(
            secrets.choice(SLUG_HASH_ALPHABET) for _ in range(SLUG_HASH_LENGTH)
        )
        slug = f"{base}#{hash_part}"
        if not model_cls.objects.filter(slug=slug).exists():
            return slug
