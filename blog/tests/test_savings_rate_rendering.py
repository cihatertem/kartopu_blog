from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.template import Context, Template
from django.test import TestCase

from blog.models import BlogPost
from portfolio.models import (
    SalarySavingsEntry,
    SalarySavingsFlow,
    SalarySavingsSnapshot,
)


class SavingsRateRenderingTests(TestCase):
    def setUp(self) -> None:
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            email="blog@example.com",
            password="testpass123",
            first_name="Blog",
        )
        self.flow = SalarySavingsFlow.objects.create(
            owner=self.user,
            name="Maaş Akışı",
            currency=SalarySavingsFlow.Currency.TRY,
        )

    def test_render_post_body_shows_rates_without_amounts(self) -> None:
        SalarySavingsEntry.objects.create(
            flow=self.flow,
            entry_date=date(2025, 12, 15),
            salary_amount=Decimal("10000"),
            savings_amount=Decimal("3000"),
        )
        SalarySavingsEntry.objects.create(
            flow=self.flow,
            entry_date=date(2026, 1, 15),
            salary_amount=Decimal("20000"),
            savings_amount=Decimal("8000"),
        )

        SalarySavingsSnapshot.create_snapshot(
            flow=self.flow,
            snapshot_date=date(2025, 12, 31),
        )
        january_snapshot = SalarySavingsSnapshot.create_snapshot(
            flow=self.flow,
            snapshot_date=date(2026, 1, 32),
        )

        post = BlogPost.objects.create(
            author=self.user,
            title="Tasarruf Oranı",
            slug="tasarruf-orani",
            content="{{ savings_rate_summary }}\n{{ savings_rate_charts }}",
        )
        post.salary_savings_snapshots.add(january_snapshot)

        template = Template("{% load blog_extras %}{% render_post_body post %}")
        rendered = template.render(Context({"post": post}))

        self.assertIn("Tasarruf Oranı (%)", rendered)
        self.assertIn("40.00", rendered)
        self.assertIn("data-savings-rate-timeseries", rendered)
        self.assertNotIn("20000", rendered)
        self.assertNotIn("8000", rendered)
