import re

from django.db.models import Prefetch

from portfolio.models import (
    CashFlowComparison,
    CashFlowSnapshot,
    DividendComparison,
    DividendSnapshot,
    DividendSnapshotAssetItem,
    DividendSnapshotPaymentItem,
    PortfolioComparison,
    PortfolioSnapshot,
    PortfolioSnapshotItem,
    SalarySavingsSnapshot,
)

GENERIC_PATTERN = re.compile(
    r"\{\{\s*(?P<tag>[a-zA-Z0-9_]+)(?::(?P<arg>[^\s\}]+))?\s*\}\}"
)

PORTFOLIO_SNAPSHOT_MARKERS = frozenset(
    {
        "portfolio_summary",
        "portfolio_charts",
        "portfolio_irr_charts",
        "portfolio_category_summary",
    }
)
PORTFOLIO_COMPARISON_MARKERS = frozenset(
    {
        "portfolio_comparison_summary",
        "portfolio_comparison_charts",
    }
)
CASHFLOW_SNAPSHOT_MARKERS = frozenset(
    {
        "cashflow_summary",
        "cashflow_charts",
    }
)
CASHFLOW_COMPARISON_MARKERS = frozenset(
    {
        "cashflow_comparison_summary",
        "cashflow_comparison_charts",
    }
)
SALARY_SAVINGS_MARKERS = frozenset(
    {
        "savings_rate_summary",
        "savings_rate_charts",
    }
)
DIVIDEND_SNAPSHOT_MARKERS = frozenset(
    {
        "dividend_summary",
        "dividend_charts",
    }
)
DIVIDEND_COMPARISON_MARKERS = frozenset({"dividend_comparison"})
SUPPORTED_CONTENT_MARKERS = (
    PORTFOLIO_SNAPSHOT_MARKERS
    | PORTFOLIO_COMPARISON_MARKERS
    | CASHFLOW_SNAPSHOT_MARKERS
    | CASHFLOW_COMPARISON_MARKERS
    | SALARY_SAVINGS_MARKERS
    | DIVIDEND_SNAPSHOT_MARKERS
    | DIVIDEND_COMPARISON_MARKERS
)

DEPENDENCY_GROUPS = {
    "portfolio": PORTFOLIO_SNAPSHOT_MARKERS | PORTFOLIO_COMPARISON_MARKERS,
    "cashflow": CASHFLOW_SNAPSHOT_MARKERS | CASHFLOW_COMPARISON_MARKERS,
    "salary_savings": SALARY_SAVINGS_MARKERS,
    "dividend": DIVIDEND_SNAPSHOT_MARKERS | DIVIDEND_COMPARISON_MARKERS,
}


def detect_content_dependencies(content: str) -> list[str]:
    """
    Analyzes the content for markers and returns a list of dependency groups.
    """
    if not content:
        return []

    found_tags = {match.group("tag") for match in GENERIC_PATTERN.finditer(content)}

    dependencies = []
    for group, tags in DEPENDENCY_GROUPS.items():
        if tags.intersection(found_tags):
            dependencies.append(group)

    return dependencies


def detect_content_markers(content: str) -> set[str]:
    """Return supported data markers used by a post body."""
    if not content:
        return set()

    return {
        match.group("tag")
        for match in GENERIC_PATTERN.finditer(content)
        if match.group("tag") in SUPPORTED_CONTENT_MARKERS
    }


def portfolio_snapshot_queryset(
    base_queryset=None,
    *,
    include_items: bool = False,
    include_history: bool = False,
):
    qs = base_queryset if base_queryset is not None else PortfolioSnapshot.objects
    qs = qs.select_related("portfolio")

    prefetches = []
    if include_items:
        prefetches.append(
            Prefetch(
                "items",
                queryset=PortfolioSnapshotItem.objects.select_related("asset"),
            )
        )
    if include_history:
        prefetches.append(
            Prefetch(
                "portfolio__snapshots",
                queryset=PortfolioSnapshot.objects.only(
                    "snapshot_date",
                    "total_value",
                    "irr_pct",
                    "portfolio_id",
                    "period",
                ).order_by("snapshot_date"),
                to_attr="prefetched_snapshots",
            )
        )

    if prefetches:
        qs = qs.prefetch_related(*prefetches)
    return qs.order_by("snapshot_date")


def portfolio_comparison_queryset(base_queryset=None):
    qs = base_queryset if base_queryset is not None else PortfolioComparison.objects
    return qs.select_related(
        "base_snapshot",
        "compare_snapshot",
        "base_snapshot__portfolio",
        "compare_snapshot__portfolio",
    ).order_by("created_at")


def cashflow_snapshot_queryset(
    base_queryset=None,
    *,
    include_items: bool = False,
    include_history: bool = False,
):
    qs = base_queryset if base_queryset is not None else CashFlowSnapshot.objects
    qs = qs.select_related("cashflow")

    prefetches = []
    if include_items:
        prefetches.append("items")
    if include_history:
        prefetches.append(
            Prefetch(
                "cashflow__snapshots",
                queryset=CashFlowSnapshot.objects.only(
                    "snapshot_date",
                    "total_amount",
                    "cashflow_id",
                    "period",
                ).order_by("snapshot_date"),
                to_attr="prefetched_snapshots",
            )
        )

    if prefetches:
        qs = qs.prefetch_related(*prefetches)
    return qs.order_by("snapshot_date")


def cashflow_comparison_queryset(base_queryset=None, *, include_items: bool = False):
    qs = base_queryset if base_queryset is not None else CashFlowComparison.objects
    qs = qs.select_related(
        "base_snapshot",
        "compare_snapshot",
        "base_snapshot__cashflow",
        "compare_snapshot__cashflow",
    )
    if include_items:
        qs = qs.prefetch_related(
            "base_snapshot__items",
            "compare_snapshot__items",
        )
    return qs.order_by("created_at")


def salary_savings_snapshot_queryset(
    base_queryset=None,
    *,
    include_history: bool = False,
):
    qs = base_queryset if base_queryset is not None else SalarySavingsSnapshot.objects
    qs = qs.select_related("flow")

    if include_history:
        qs = qs.prefetch_related(
            Prefetch(
                "flow__snapshots",
                queryset=SalarySavingsSnapshot.objects.only(
                    "snapshot_date",
                    "savings_rate",
                    "flow_id",
                ).order_by("snapshot_date"),
                to_attr="prefetched_snapshots",
            )
        )
    return qs.order_by("snapshot_date")


def dividend_snapshot_queryset(
    base_queryset=None,
    *,
    include_asset_items: bool = False,
    include_payment_items: bool = False,
):
    qs = base_queryset if base_queryset is not None else DividendSnapshot.objects

    prefetches = []
    if include_asset_items:
        prefetches.append(
            Prefetch(
                "asset_items",
                queryset=DividendSnapshotAssetItem.objects.select_related("asset"),
            )
        )
    if include_payment_items:
        prefetches.append(
            Prefetch(
                "payment_items",
                queryset=DividendSnapshotPaymentItem.objects.select_related("asset"),
            )
        )

    if prefetches:
        qs = qs.prefetch_related(*prefetches)
    return qs.order_by("-year", "-created_at")


def dividend_comparison_queryset(base_queryset=None):
    qs = base_queryset if base_queryset is not None else DividendComparison.objects
    return qs.select_related(
        "base_snapshot",
        "compare_snapshot",
    ).order_by("created_at")


def get_content_prefetches_for_markers(markers: set[str]):
    prefetches = []

    if markers & PORTFOLIO_SNAPSHOT_MARKERS:
        prefetches.append(
            Prefetch(
                "portfolio_snapshots",
                queryset=portfolio_snapshot_queryset(
                    include_items=bool(
                        markers & {"portfolio_charts", "portfolio_category_summary"}
                    ),
                    include_history=bool(
                        markers & {"portfolio_charts", "portfolio_irr_charts"}
                    ),
                ),
            )
        )
    if markers & PORTFOLIO_COMPARISON_MARKERS:
        prefetches.append(
            Prefetch(
                "portfolio_comparisons",
                queryset=portfolio_comparison_queryset(),
            )
        )
    if markers & CASHFLOW_SNAPSHOT_MARKERS:
        prefetches.append(
            Prefetch(
                "cashflow_snapshots",
                queryset=cashflow_snapshot_queryset(
                    include_items=True,
                    include_history="cashflow_charts" in markers,
                ),
            )
        )
    if markers & CASHFLOW_COMPARISON_MARKERS:
        prefetches.append(
            Prefetch(
                "cashflow_comparisons",
                queryset=cashflow_comparison_queryset(
                    include_items="cashflow_comparison_summary" in markers,
                ),
            )
        )
    if markers & SALARY_SAVINGS_MARKERS:
        prefetches.append(
            Prefetch(
                "salary_savings_snapshots",
                queryset=salary_savings_snapshot_queryset(
                    include_history="savings_rate_charts" in markers,
                ),
            )
        )
    if markers & DIVIDEND_SNAPSHOT_MARKERS:
        prefetches.append(
            Prefetch(
                "dividend_snapshots",
                queryset=dividend_snapshot_queryset(
                    include_asset_items="dividend_charts" in markers,
                    include_payment_items="dividend_summary" in markers,
                ),
            )
        )
    if markers & DIVIDEND_COMPARISON_MARKERS:
        prefetches.append(
            Prefetch(
                "dividend_comparisons",
                queryset=dividend_comparison_queryset(),
            )
        )

    return prefetches


def get_content_prefetches_for_dependencies(dependencies: list[str]):
    markers = set()
    for dependency in dependencies:
        markers.update(DEPENDENCY_GROUPS.get(dependency, ()))
    return get_content_prefetches_for_markers(markers)
