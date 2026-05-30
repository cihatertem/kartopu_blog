from __future__ import annotations

import secrets
import string
from collections import Counter
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


def _generate_slug_candidate(base: str) -> str:
    hash_part = "".join(
        secrets.choice(SLUG_HASH_ALPHABET) for _ in range(SLUG_HASH_LENGTH)
    )
    return f"{base}#{hash_part}"


def generate_unique_slug(model_cls: type[models.Model], name: str) -> str:
    base = _build_slug_base(name, max_length=255)

    slug = _generate_slug_candidate(base)
    if not model_cls.objects.filter(slug=slug).exists():
        return slug

    batch_size = 5
    while True:
        candidates_list = []
        for _ in range(batch_size):
            candidates_list.append(_generate_slug_candidate(base))

        existing = set(
            model_cls.objects.filter(slug__in=candidates_list).values_list(
                "slug", flat=True
            )
        )

        for candidate in candidates_list:
            if candidate not in existing:
                return candidate

        batch_size *= 2


def generate_unique_slugs(model_cls: type[models.Model], names: list[str]) -> list[str]:
    if not names:
        return []

    bases = [_build_slug_base(name, max_length=255) for name in names]
    resolved_slugs: list[str | None] = [None] * len(names)
    pending_indexes = list(range(len(names)))

    while pending_indexes:
        candidate_map = {
            index: _generate_slug_candidate(bases[index]) for index in pending_indexes
        }
        candidate_counts = Counter(candidate_map.values())
        existing_slugs = set(
            model_cls.objects.filter(slug__in=list(candidate_map.values())).values_list(
                "slug",
                flat=True,
            )
        )

        next_pending_indexes: list[int] = []
        for index, candidate in candidate_map.items():
            if candidate in existing_slugs or candidate_counts[candidate] > 1:
                next_pending_indexes.append(index)
                continue
            resolved_slugs[index] = candidate

        pending_indexes = next_pending_indexes

    return [slug for slug in resolved_slugs if slug is not None]
