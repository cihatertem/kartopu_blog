import secrets
import string

from django.db import migrations, models
from django.utils.text import slugify

SLUG_HASH_LENGTH = 6
SLUG_HASH_ALPHABET = string.ascii_lowercase + string.digits


def _build_slug_base(name: str, max_length: int = 255) -> str:
    base = slugify(name, allow_unicode=True)
    if not base:
        base = "snapshot"
    max_base_length = max_length - (SLUG_HASH_LENGTH + 1)
    if max_base_length < 1:
        return base
    return base[:max_base_length]


def _generate_unique_slug(model_cls, name: str) -> str:
    base = _build_slug_base(name)
    while True:
        hash_part = "".join(
            secrets.choice(SLUG_HASH_ALPHABET) for _ in range(SLUG_HASH_LENGTH)
        )
        slug = f"{base}#{hash_part}"
        if not model_cls.objects.filter(slug=slug).exists():
            return slug


def _portfolio_snapshot_label(snapshot) -> str:
    if snapshot.name:
        return snapshot.name
    if snapshot.portfolio_id and snapshot.snapshot_date:
        return f"{snapshot.portfolio} - {snapshot.snapshot_date}"
    return "portfolio-snapshot"


def _cashflow_snapshot_label(snapshot) -> str:
    if snapshot.name:
        return snapshot.name
    if snapshot.cashflow_id and snapshot.snapshot_date:
        return f"{snapshot.cashflow} - {snapshot.snapshot_date}"
    if snapshot.cashflow_id:
        return f"{snapshot.cashflow}"
    return "cashflow-snapshot"


def _dividend_snapshot_label(snapshot) -> str:
    if snapshot.name:
        return snapshot.name
    if snapshot.year:
        return f"{snapshot.year} Temettü Özeti"
    return "dividend-snapshot"


def _comparison_label(base_label: str, compare_label: str) -> str:
    if base_label and compare_label:
        return f"{base_label} → {compare_label}"
    return base_label or compare_label or "comparison"


def populate_slugs(apps, schema_editor):
    PortfolioSnapshot = apps.get_model("portfolio", "PortfolioSnapshot")
    CashFlowSnapshot = apps.get_model("portfolio", "CashFlowSnapshot")
    DividendSnapshot = apps.get_model("portfolio", "DividendSnapshot")
    PortfolioComparison = apps.get_model("portfolio", "PortfolioComparison")
    CashFlowComparison = apps.get_model("portfolio", "CashFlowComparison")
    DividendComparison = apps.get_model("portfolio", "DividendComparison")

    for snapshot in PortfolioSnapshot.objects.all():
        label = _portfolio_snapshot_label(snapshot)
        update_fields = []
        if not snapshot.name:
            snapshot.name = label
            update_fields.append("name")
        if not snapshot.slug:
            snapshot.slug = _generate_unique_slug(PortfolioSnapshot, label)
            update_fields.append("slug")
        if update_fields:
            snapshot.save(update_fields=update_fields)

    for snapshot in CashFlowSnapshot.objects.all():
        label = _cashflow_snapshot_label(snapshot)
        update_fields = []
        if not snapshot.name:
            snapshot.name = label
            update_fields.append("name")
        if not snapshot.slug:
            snapshot.slug = _generate_unique_slug(CashFlowSnapshot, label)
            update_fields.append("slug")
        if update_fields:
            snapshot.save(update_fields=update_fields)

    for snapshot in DividendSnapshot.objects.all():
        label = _dividend_snapshot_label(snapshot)
        update_fields = []
        if not snapshot.name:
            snapshot.name = label
            update_fields.append("name")
        if not snapshot.slug:
            snapshot.slug = _generate_unique_slug(DividendSnapshot, label)
            update_fields.append("slug")
        if update_fields:
            snapshot.save(update_fields=update_fields)

    for comparison in PortfolioComparison.objects.all():
        base_label = _portfolio_snapshot_label(comparison.base_snapshot)
        compare_label = _portfolio_snapshot_label(comparison.compare_snapshot)
        label = _comparison_label(base_label, compare_label)
        update_fields = []
        if not comparison.name:
            comparison.name = label
            update_fields.append("name")
        if not comparison.slug:
            comparison.slug = _generate_unique_slug(PortfolioComparison, label)
            update_fields.append("slug")
        if update_fields:
            comparison.save(update_fields=update_fields)

    for comparison in CashFlowComparison.objects.all():
        base_label = _cashflow_snapshot_label(comparison.base_snapshot)
        compare_label = _cashflow_snapshot_label(comparison.compare_snapshot)
        label = _comparison_label(base_label, compare_label)
        update_fields = []
        if not comparison.name:
            comparison.name = label
            update_fields.append("name")
        if not comparison.slug:
            comparison.slug = _generate_unique_slug(CashFlowComparison, label)
            update_fields.append("slug")
        if update_fields:
            comparison.save(update_fields=update_fields)

    for comparison in DividendComparison.objects.all():
        base_label = _dividend_snapshot_label(comparison.base_snapshot)
        compare_label = _dividend_snapshot_label(comparison.compare_snapshot)
        label = _comparison_label(base_label, compare_label)
        update_fields = []
        if not comparison.name:
            comparison.name = label
            update_fields.append("name")
        if not comparison.slug:
            comparison.slug = _generate_unique_slug(DividendComparison, label)
            update_fields.append("slug")
        if update_fields:
            comparison.save(update_fields=update_fields)


class Migration(migrations.Migration):
    dependencies = [
        ("portfolio", "0022_portfoliosnapshot_is_featured"),
    ]

    operations = [
        migrations.AddField(
            model_name="portfoliocomparison",
            name="name",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="portfoliocomparison",
            name="slug",
            field=models.CharField(
                blank=True, editable=False, max_length=255, null=True, unique=True
            ),
        ),
        migrations.AddField(
            model_name="portfoliosnapshot",
            name="slug",
            field=models.CharField(
                blank=True, editable=False, max_length=255, null=True, unique=True
            ),
        ),
        migrations.AddField(
            model_name="cashflowcomparison",
            name="name",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="cashflowcomparison",
            name="slug",
            field=models.CharField(
                blank=True, editable=False, max_length=255, null=True, unique=True
            ),
        ),
        migrations.AddField(
            model_name="cashflowsnapshot",
            name="slug",
            field=models.CharField(
                blank=True, editable=False, max_length=255, null=True, unique=True
            ),
        ),
        migrations.AddField(
            model_name="dividendcomparison",
            name="name",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="dividendcomparison",
            name="slug",
            field=models.CharField(
                blank=True, editable=False, max_length=255, null=True, unique=True
            ),
        ),
        migrations.AddField(
            model_name="dividendsnapshot",
            name="slug",
            field=models.CharField(
                blank=True, editable=False, max_length=255, null=True, unique=True
            ),
        ),
        migrations.RunPython(populate_slugs, migrations.RunPython.noop),
    ]
