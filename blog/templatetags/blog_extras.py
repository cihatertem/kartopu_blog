import json
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin

from django import template
from django.core.serializers.json import DjangoJSONEncoder
from django.template.loader import render_to_string
from django.templatetags.static import static as static_url
from django.utils.html import escape
from django.utils.safestring import mark_safe

from core.decorators import log_exceptions
from core.markdown import render_markdown
from portfolio.models import CashFlowEntry, CashFlowSnapshot, SalarySavingsSnapshot

register = template.Library()

IMAGE_PATTERN = re.compile(r"\{\{\s*image:(\d+)\s*\}\}")
GENERIC_PATTERN = re.compile(
    r"\{\{\s*(?P<tag>[a-zA-Z0-9_]+)(?::(?P<arg>[^\s\}]+))?\s*\}\}"
)


@register.filter
def absolute_url(path: str, base_url: str) -> str:
    if not path:
        return ""
    if not base_url:
        return path
    base = base_url.rstrip("/") + "/"
    return urljoin(base, str(path))


@register.simple_tag
def preload_stylesheet(path: str) -> str:
    href = static_url(path)
    return mark_safe(
        f'<link rel="preload" href="{href}" as="style" '
        'data-preload-stylesheet="true">'
        f'<noscript><link rel="stylesheet" href="{href}"></noscript>'
    )


def _render_responsive_image_figure(img) -> str:
    rendition = getattr(img, "rendition", None)
    if not rendition:
        return ""

    src = rendition["src"]
    srcset = rendition["srcset"]
    width = rendition["width"]
    height = rendition["height"]
    alt_text = escape(getattr(img, "alt_text", "") or "")

    figure = f"""
<figure>
  <img
    src="{src}"
    srcset="{srcset}"
    sizes="(max-width: 768px) 100vw, 720px"
    alt="{alt_text}"
    width="{width}"
    height="{height}"
    loading="lazy"
  />
"""
    caption = getattr(img, "caption", "")
    if caption:
        figure += f"<figcaption>{escape(caption)}</figcaption>\n"
    figure += "</figure>"
    return figure


@register.filter
def render_post_content(content, images):
    images = list(images)

    def replacer(match):
        index = int(match.group(1)) - 1
        if index < 0 or index >= len(images):
            return ""

        img = images[index]
        return _render_responsive_image_figure(img)

    expanded = IMAGE_PATTERN.sub(replacer, content or "")

    return render_markdown(expanded)


@register.filter
def render_excerpt(text):
    return mark_safe(render_markdown(text or ""))


def _render_portfolio_summary_html(snapshot) -> str:
    if not snapshot:
        return ""

    total_return_pct = mul100(snapshot.total_return_pct)

    portfolio_name = escape(getattr(snapshot.portfolio, "name", ""))
    period_display = escape(
        snapshot.get_period_display() if hasattr(snapshot, "get_period_display") else ""
    )
    snapshot_date = escape(str(snapshot.snapshot_date))
    portfolio_currency = getattr(snapshot.portfolio, "currency", None)
    total_value = _format_currency(snapshot.total_value, portfolio_currency)
    total_cost = _format_currency(snapshot.total_cost, portfolio_currency)
    target_value_raw = snapshot.target_value
    target_value = (
        _format_currency(target_value_raw, portfolio_currency)
        if target_value_raw is not None
        else ""
    )
    target_ratio_pct = ""
    if target_value_raw is not None:
        target_value_decimal = _safe_decimal(target_value_raw)
        if target_value_decimal:
            total_value_decimal = _safe_decimal(snapshot.total_value)
            target_ratio_pct = escape(
                f"{float((total_value_decimal / target_value_decimal) * Decimal('100')):.2f}"  # pyright: ignore[reportOptionalOperand]
            )
    total_return_pct_s = escape(f"{float(total_return_pct):.2f}")  # pyright: ignore[reportArgumentType]

    target_li = (
        f"<li><strong>Hedef Değer:</strong> {target_value}</li>" if target_value else ""
    )
    target_ratio_li = (
        f"<li><strong>Hedef Gerçekleşme (%):</strong> {target_ratio_pct}</li>"
        if target_ratio_pct
        else ""
    )

    html = f"""
<section class="portfolio-snapshot">
  <div class="summary-card">
    <p class="summary-meta"><strong>Portföy:</strong> {portfolio_name}</p>
    <p class="summary-meta summary-meta--spaced"><strong>Tarih:</strong> {snapshot_date}
      <span class="text-muted">({period_display})</span>
    </p>
    <ul class="summary-list">
      <li><strong>Toplam Değer:</strong> {total_value}</li>
      <li><strong>Toplam Maliyet:</strong> {total_cost}</li>
      {target_li}
      {target_ratio_li}
      <li><strong>Toplam Getiri (%):</strong> {total_return_pct_s}</li>
    </ul>
  </div>
</section>
"""
    return html


def _render_portfolio_irr_charts_html(snapshot) -> str:
    if not snapshot:
        return ""

    portfolio = snapshot.portfolio
    irr_history = portfolio.get_irr_history(until_date=snapshot.snapshot_date)

    timeseries = {
        "labels": [item["date"] for item in irr_history],
        "values": [item["irr"] for item in irr_history],
    }
    timeseries_json = escape(json.dumps(timeseries, cls=DjangoJSONEncoder))

    return """
<section class="chart-section portfolio-irr-charts" data-portfolio-irr="{timeseries_json}">
  <div class="chart-fallback portfolio-irr-chart-fallback is-hidden">
    Grafikler yüklenemedi. (Tarayıcı eklentisi / ağ politikası / CSP engelliyor olabilir.)
  </div>

  <div class="chart-card">
    <h4 class="chart-card__title">Portföy IRR Performansı (%)</h4>
    <canvas data-chart-kind="portfolio-irr" height="240"></canvas>
  </div>
</section>
""".format(
        timeseries_json=timeseries_json,
    )


def _render_portfolio_charts_html(snapshot) -> str:
    if not snapshot:
        return ""

    items = (
        snapshot.items.select_related("asset")
        .filter(market_value__gt=0)
        .order_by("-allocation_pct")
    )
    allocation = {
        "labels": [(item.asset.symbol or item.asset.name) for item in items],
        "values": [_safe_float(item.allocation_pct) * 100 for item in items],  # pyright: ignore[reportOptionalOperand]
    }
    snapshots_qs = (
        snapshot.__class__.objects.filter(
            portfolio=snapshot.portfolio,
            period=snapshot.period,
        )
        .order_by("snapshot_date")
        .values_list("snapshot_date", "total_value")
    )
    timeseries = {
        "labels": [d.isoformat() for d, _ in snapshots_qs],
        "values": [_safe_float(v) for _, v in snapshots_qs],
    }
    allocation_json = escape(json.dumps(allocation, cls=DjangoJSONEncoder))
    timeseries_json = escape(json.dumps(timeseries, cls=DjangoJSONEncoder))

    return """
<section class="chart-section portfolio-charts" data-portfolio-allocation="{allocation_json}" data-portfolio-timeseries="{timeseries_json}">
  <div class="chart-fallback portfolio-chart-fallback is-hidden">
    Grafikler yüklenemedi. (Tarayıcı eklentisi / ağ politikası / CSP engelliyor olabilir.)
  </div>

  <div class="chart-grid">
    <div class="chart-card">
      <h4 class="chart-card__title">Dağılım</h4>
      <canvas data-chart-kind="portfolio-allocation" height="220"></canvas>
    </div>

    <div class="chart-card">
      <h4 class="chart-card__title">Portföy Değeri (Zaman Serisi)</h4>
      <canvas data-chart-kind="portfolio-timeseries" height="220"></canvas>
    </div>
  </div>
</section>
""".format(
        allocation_json=allocation_json,
        timeseries_json=timeseries_json,
    )


def _render_portfolio_category_summary_html(snapshot) -> str:
    if not snapshot:
        return ""

    items = (
        snapshot.items.select_related("asset")
        .filter(market_value__gt=0)
        .order_by("-allocation_pct")
    )
    category_totals: dict[str, float] = {}
    for item in items:
        asset = item.asset
        label = asset.get_asset_type_display() if asset else "Diğer"
        category_totals[label] = category_totals.get(label, 0) + float(
            _safe_float(item.allocation_pct) * 100  # pyright: ignore[reportOptionalOperand]
        )

    if not category_totals:
        return ""

    sorted_items = sorted(category_totals.items(), key=lambda row: row[1], reverse=True)
    allocation = {
        "labels": [label for label, _ in sorted_items],
        "values": [value for _, value in sorted_items],
    }
    allocation_json = escape(json.dumps(allocation, cls=DjangoJSONEncoder))

    return """
<section class="chart-section portfolio-category-charts" data-portfolio-category-allocation="{allocation_json}">
  <div class="chart-fallback portfolio-category-chart-fallback is-hidden">
    Grafikler yüklenemedi. (Tarayıcı eklentisi / ağ politikası / CSP engelliyor olabilir.)
  </div>
  <div class="chart-card">
    <h4 class="chart-card__title">Kategori Dağılımı</h4>
    <canvas data-chart-kind="portfolio-category-allocation" height="220"></canvas>
  </div>
</section>
""".format(
        allocation_json=allocation_json,
    )


@log_exceptions(
    default_factory=lambda value: Decimal("0"),
    exception_types=(TypeError,),
    message="Error in _safe_decimal",
)
def _safe_decimal(value) -> Decimal:
    return value or Decimal("0")


@log_exceptions(
    default=0.0,
    exception_types=(TypeError, ValueError),
    message="Error in _safe_float",
)
def _safe_float(value) -> float:
    return float(value or 0)


def _currency_symbol(currency_code: str | None) -> str:
    symbols = {
        "TRY": "₺",
        "USD": "$",
        "EUR": "€",
    }
    return symbols.get(currency_code or "", "")


def _format_currency(value, currency_code: str | None) -> str:
    value_str = _format_tr_number(value)
    value_str = escape(value_str)
    symbol = _currency_symbol(currency_code)
    return f"{value_str} {symbol}".rstrip()


@log_exceptions(
    default_factory=lambda value: str(value),
    exception_types=(InvalidOperation, TypeError),
    message="Error in _format_tr_number",
)
def _format_tr_number(value) -> str:
    dec = Decimal(str(value))

    has_decimal = dec % 1 != 0

    if has_decimal:
        s = f"{dec:,.2f}"
    else:
        s = f"{dec:,.0f}"

    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return s


def _get_prefetched_list(post, attr_name, fallback_queryset):
    if not post:
        return []

    prefetched = getattr(post, "_prefetched_objects_cache", {})
    if attr_name in prefetched:
        return list(prefetched[attr_name])

    return list(fallback_queryset)


def _get_indexed_item(items, index):
    if not items:
        return None

    target_index = 0 if index is None else index - 1
    if target_index < 0 or target_index >= len(items):
        return None

    return items[target_index]


def _coerce_identifier(raw_value):
    if raw_value is None:
        return None
    if isinstance(raw_value, int):
        return raw_value
    value = str(raw_value).strip()
    if value.isdigit():
        return int(value)
    return value


def _get_item_by_identifier(items, identifier):
    if not items:
        return None

    identifier = _coerce_identifier(identifier)
    if identifier is None:
        return items[0]
    if isinstance(identifier, int):
        return _get_indexed_item(items, identifier)

    slug_value = str(identifier)
    for item in items:
        item_slug = getattr(item, "slug", "") or ""
        if not item_slug:
            continue
        if slug_value == item_slug:
            return item
        if "#" in item_slug and slug_value == item_slug.rsplit("#", 1)[-1]:
            return item
    return None


def _get_cashflow_snapshots(post):
    if not post:
        return []

    return _get_prefetched_list(
        post,
        "cashflow_snapshots",
        post.cashflow_snapshots.select_related("cashflow").order_by("snapshot_date"),
    )


def _get_cashflow_comparisons(post):
    if not post:
        return []

    return _get_prefetched_list(
        post,
        "cashflow_comparisons",
        post.cashflow_comparisons.select_related(
            "base_snapshot",
            "compare_snapshot",
            "base_snapshot__cashflow",
            "compare_snapshot__cashflow",
        )
        .prefetch_related(
            "base_snapshot__items",
            "compare_snapshot__items",
        )
        .order_by("created_at"),
    )


def _get_salary_savings_snapshots(post):
    if not post:
        return []

    return _get_prefetched_list(
        post,
        "salary_savings_snapshots",
        post.salary_savings_snapshots.select_related("flow").order_by("snapshot_date"),
    )


def _get_portfolio_snapshots(post):
    if not post:
        return []

    return _get_prefetched_list(
        post,
        "portfolio_snapshots",
        post.portfolio_snapshots.select_related("portfolio").order_by("snapshot_date"),
    )


def _get_portfolio_comparisons(post):
    if not post:
        return []

    return _get_prefetched_list(
        post,
        "portfolio_comparisons",
        post.portfolio_comparisons.select_related(
            "base_snapshot",
            "compare_snapshot",
            "base_snapshot__portfolio",
            "compare_snapshot__portfolio",
        ).order_by("created_at"),
    )


def _get_dividend_snapshots(post):
    if not post:
        return []

    return _get_prefetched_list(
        post,
        "dividend_snapshots",
        post.dividend_snapshots.order_by("-snapshot_date", "-created_at"),
    )


def _get_dividend_comparisons(post):
    if not post:
        return []

    return _get_prefetched_list(
        post,
        "dividend_comparisons",
        post.dividend_comparisons.select_related(
            "base_snapshot",
            "compare_snapshot",
        ).order_by("created_at"),
    )


def _get_portfolio_target_ratio_html(target_ratio) -> str:
    if target_ratio is None:
        return ""
    return f"<li><strong>Hedef Gerçekleşme (%):</strong> {escape(f'{float(target_ratio):.2f}')}</li>"


def _render_portfolio_comparison_column(
    label: str,
    period: str,
    value,
    cost,
    return_pct,
    target_ratio_html: str,
    currency,
) -> str:
    return f"""
      <div>
        <p class="summary-meta"><strong>Tarih:</strong> {label}
          <span class="text-muted">({period})</span>
        </p>
        <ul class="summary-list">
          <li><strong>Toplam Değer:</strong> {_format_currency(value, currency)}</li>
          <li><strong>Toplam Maliyet:</strong> {_format_currency(cost, currency)}</li>
          {target_ratio_html}
          <li><strong>Toplam Getiri (%):</strong> {escape(f"{float(return_pct):.2f}")}</li>
        </ul>
      </div>
""".strip()


def _render_portfolio_comparison_summary_html(comparison) -> str:
    if not comparison:
        return ""

    base = comparison.base_snapshot
    compare = comparison.compare_snapshot

    base_label = escape(str(base.snapshot_date))
    compare_label = escape(str(compare.snapshot_date))
    base_period = escape(
        base.get_period_display() if hasattr(base, "get_period_display") else ""
    )
    compare_period = escape(
        compare.get_period_display() if hasattr(compare, "get_period_display") else ""
    )

    base_value = _safe_decimal(base.total_value)
    compare_value = _safe_decimal(compare.total_value)
    base_cost = _safe_decimal(base.total_cost)
    compare_cost = _safe_decimal(compare.total_cost)
    base_return = _safe_decimal(base.total_return_pct) * Decimal("100")  # pyright: ignore[reportOptionalOperand]
    compare_return = _safe_decimal(compare.total_return_pct) * Decimal("100")  # pyright: ignore[reportOptionalOperand]
    portfolio_currency = getattr(base.portfolio, "currency", None)

    base_target_value = _safe_decimal(base.target_value)
    compare_target_value = _safe_decimal(compare.target_value)
    base_target_ratio = (
        (base_value / base_target_value) * Decimal("100") if base_target_value else None  # pyright: ignore[reportOptionalOperand]
    )
    compare_target_ratio = (
        (compare_value / compare_target_value) * Decimal("100")  # pyright: ignore[reportOptionalOperand]
        if compare_target_value
        else None
    )

    value_delta = compare_value - base_value  # pyright: ignore[reportOperatorIssue]
    cost_delta = compare_cost - base_cost  # pyright: ignore[reportOperatorIssue]

    cost_free_value_delta = value_delta - cost_delta

    cost_free_return = (
        (cost_free_value_delta / base_value) * Decimal("100")
        if base_value
        else Decimal("0")
    )

    return_delta = compare_return - base_return
    target_ratio_delta = None
    if base_target_ratio is not None and compare_target_ratio is not None:
        target_ratio_delta = compare_target_ratio - base_target_ratio

    base_target_ratio_html = _get_portfolio_target_ratio_html(base_target_ratio)
    compare_target_ratio_html = _get_portfolio_target_ratio_html(compare_target_ratio)

    target_ratio_delta_html = ""
    if target_ratio_delta is not None:
        target_points = target_ratio_delta * Decimal("100")
        target_sign = "+" if target_points > 0 else ""
        target_ratio_delta_html = f", Hedef Gerçekleşme {target_sign}{escape(f'{float(target_points):.0f}')} puan"

    return_points = return_delta * Decimal("100")
    return_sign = "+" if return_points > 0 else ""
    return_html = f"Getiri {return_sign}{escape(f'{float(return_points):.0f}')} puan"

    cost_free_return_str = escape(f"~%{float(cost_free_return):.2f}").replace(".", ",")

    base_col_html = _render_portfolio_comparison_column(
        base_label,
        base_period,
        base_value,
        base_cost,
        base_return,
        base_target_ratio_html,
        portfolio_currency,
    )
    compare_col_html = _render_portfolio_comparison_column(
        compare_label,
        compare_period,
        compare_value,
        compare_cost,
        compare_return,
        compare_target_ratio_html,
        portfolio_currency,
    )

    html = f"""
<section class="portfolio-comparison">
  <h4>Portföy Karşılaştırması</h4>
  <div class="summary-card">
    <div class="comparison-grid">
      {base_col_html}
      {compare_col_html}
    </div>
    <div class="comparison-footer">
      <p class="summary-meta summary-meta--tight"><strong>Değişim:</strong> Toplam Değer {_format_currency(value_delta, portfolio_currency)} ({cost_free_return_str}),
        {return_html}{target_ratio_delta_html}</p>
    </div>
  </div>
</section>
"""
    return html


def _render_portfolio_comparison_charts_html(comparison) -> str:
    if not comparison:
        return ""

    base = comparison.base_snapshot
    compare = comparison.compare_snapshot

    payload = {
        "labels": ["Toplam Maliyet", "Toplam Değer"],
        "base": [
            _safe_float(base.total_cost),
            _safe_float(base.total_value),
        ],
        "compare": [
            _safe_float(compare.total_cost),
            _safe_float(compare.total_value),
        ],
        "base_label": f"{base.snapshot_date}",
        "compare_label": f"{compare.snapshot_date}",
    }
    comparison_json = escape(json.dumps(payload, cls=DjangoJSONEncoder))

    return """
<section class="chart-section portfolio-comparison-charts" data-portfolio-comparison="{comparison_json}">
  <div class="chart-fallback portfolio-comparison-chart-fallback is-hidden">
    Grafikler yüklenemedi. (Tarayıcı eklentisi / ağ politikası / CSP engelliyor olabilir.)
  </div>
  <div class="chart-card">
    <h4 class="chart-card__title">Karşılaştırma Özeti</h4>
    <canvas data-chart-kind="portfolio-comparison" height="260"></canvas>
  </div>
</section>
""".format(
        comparison_json=comparison_json,
    )


def _render_cashflow_summary_html(snapshot) -> str:
    if not snapshot:
        return ""

    cashflow_name = escape(getattr(snapshot.cashflow, "name", ""))
    cashflow_currency = getattr(snapshot.cashflow, "currency", None)
    period_display = escape(
        snapshot.get_period_display() if hasattr(snapshot, "get_period_display") else ""
    )
    snapshot_date = escape(str(snapshot.snapshot_date))
    total_amount = _format_currency(snapshot.total_amount, cashflow_currency)
    category_items = snapshot.items.order_by("-amount")
    category_rows = "\n".join(
        f"<li><strong>{escape(item.get_category_display())}:</strong> "
        f"{_format_currency(item.amount, cashflow_currency)}</li>"
        for item in category_items
    )

    html = f"""
<section class="cashflow-snapshot">
  <div class="summary-card">
    <p class="summary-meta"><strong>Nakit Akışı:</strong> {cashflow_name}</p>
    <p class="summary-meta summary-meta--spaced"><strong>Tarih:</strong> {snapshot_date}
      <span class="text-muted">({period_display})</span>
    </p>
    <ul class="summary-list">
      <li><strong>Toplam Nakit Akışı:</strong> {total_amount}</li>
      {category_rows}
    </ul>
  </div>
</section>
"""
    return html


def _render_cashflow_charts_html(snapshot) -> str:
    if not snapshot:
        return ""

    items = snapshot.items.filter(amount__gt=0).order_by("-allocation_pct")
    allocation = {
        "labels": [item.get_category_display() for item in items],
        "values": [_safe_float(item.allocation_pct) * 100 for item in items],  # pyright: ignore[reportOptionalOperand]
    }
    snapshots_qs = (
        CashFlowSnapshot.objects.filter(
            cashflow=snapshot.cashflow,
            period=snapshot.period,
        )
        .order_by("snapshot_date")
        .values_list("snapshot_date", "total_amount")
    )
    timeseries = {
        "labels": [d.isoformat() for d, _ in snapshots_qs],
        "values": [_safe_float(v) for _, v in snapshots_qs],
    }
    allocation_json = escape(json.dumps(allocation, cls=DjangoJSONEncoder))
    timeseries_json = escape(json.dumps(timeseries, cls=DjangoJSONEncoder))

    return """
<section class="chart-section cashflow-charts" data-cashflow-allocation="{allocation_json}" data-cashflow-timeseries="{timeseries_json}">
  <div class="chart-fallback cashflow-chart-fallback is-hidden">
    Grafikler yüklenemedi. (Tarayıcı eklentisi / ağ politikası / CSP engelliyor olabilir.)
  </div>

  <div class="chart-grid">
    <div class="chart-card">
      <h4 class="chart-card__title">Nakit Akışı Dağılımı</h4>
      <canvas data-chart-kind="cashflow-allocation" height="220"></canvas>
    </div>

    <div class="chart-card">
      <h4 class="chart-card__title">Nakit Akışı (Zaman Serisi)</h4>
      <canvas data-chart-kind="cashflow-timeseries" height="220"></canvas>
    </div>
  </div>
</section>
""".format(
        allocation_json=allocation_json,
        timeseries_json=timeseries_json,
    )


def _render_savings_rate_summary_html(snapshot) -> str:
    if not snapshot:
        return ""

    flow_name = escape(getattr(snapshot.flow, "name", ""))
    snapshot_date = escape(str(snapshot.snapshot_date))
    savings_rate_pct = escape(f"{_safe_float(snapshot.savings_rate) * 100:.2f}")  # pyright: ignore[reportOptionalOperand]

    return f"""
<section class="savings-rate-snapshot">
  <div class="summary-card">
    <p class="summary-meta"><strong>Akış:</strong> {flow_name}</p>
    <p class="summary-meta summary-meta--spaced"><strong>Tarih:</strong> {snapshot_date}</p>
    <ul class="summary-list">
      <li><strong>Tasarruf Oranı (%):</strong> {savings_rate_pct}</li>
    </ul>
  </div>
</section>
"""


def _render_savings_rate_charts_html(snapshot) -> str:
    if not snapshot:
        return ""

    snapshots_qs = (
        SalarySavingsSnapshot.objects.filter(flow=snapshot.flow)
        .order_by("snapshot_date")
        .values_list("snapshot_date", "savings_rate")
    )
    timeseries = {
        "labels": [d.isoformat() for d, _ in snapshots_qs],
        "values": [_safe_float(rate) * 100 for _, rate in snapshots_qs],  # pyright: ignore[reportOptionalOperand]
    }
    timeseries_json = escape(json.dumps(timeseries, cls=DjangoJSONEncoder))

    return """
<section class="chart-section savings-rate-charts" data-savings-rate-timeseries="{timeseries_json}">
  <div class="chart-fallback savings-rate-chart-fallback is-hidden">
    Grafikler yüklenemedi. (Tarayıcı eklentisi / ağ politikası / CSP engelliyor olabilir.)
  </div>

  <div class="chart-card">
    <h4 class="chart-card__title">Tasarruf Oranı (Aylık)</h4>
    <canvas data-chart-kind="savings-rate-timeseries" height="240"></canvas>
  </div>
</section>
""".format(timeseries_json=timeseries_json)


def _render_cashflow_comparison_summary_html(comparison) -> str:
    if not comparison:
        return ""

    base = comparison.base_snapshot
    compare = comparison.compare_snapshot
    cashflow_currency = getattr(base.cashflow, "currency", None)

    base_label = escape(str(base.snapshot_date))
    compare_label = escape(str(compare.snapshot_date))
    base_period = escape(
        base.get_period_display() if hasattr(base, "get_period_display") else ""
    )
    compare_period = escape(
        compare.get_period_display() if hasattr(compare, "get_period_display") else ""
    )

    base_amount = _safe_decimal(base.total_amount)
    compare_amount = _safe_decimal(compare.total_amount)
    delta = compare_amount - base_amount  # pyright: ignore[reportOperatorIssue]
    pct_change = (
        (delta / base_amount) * Decimal("100")  # pyright: ignore[reportOperatorIssue]
        if base_amount > 0  # pyright: ignore[reportOptionalOperand]
        else Decimal("0")
    )

    base_items = {
        item.category: _safe_decimal(item.amount) for item in base.items.all()
    }
    compare_items = {
        item.category: _safe_decimal(item.amount) for item in compare.items.all()
    }
    categories = sorted(set(base_items.keys()) | set(compare_items.keys()))
    category_label_map = dict(CashFlowEntry.Category.choices)
    base_category_rows = "\n".join(
        f"<li><strong>{escape(category_label_map.get(category, category))}:</strong> "
        f"{_format_currency(base_items.get(category, Decimal('0')), cashflow_currency)}</li>"
        for category in categories
    )
    compare_category_rows = "\n".join(
        f"<li><strong>{escape(category_label_map.get(category, category))}:</strong> "
        f"{_format_currency(compare_items.get(category, Decimal('0')), cashflow_currency)}</li>"
        for category in categories
    )
    category_delta_rows = "\n".join(
        f"<li><strong>{escape(category_label_map.get(category, category))}:</strong> "
        f"{_format_currency(base_items.get(category, Decimal('0')), cashflow_currency)} → "
        f"{_format_currency(compare_items.get(category, Decimal('0')), cashflow_currency)} "
        f'(<span class="text-muted">{_format_currency(compare_items.get(category, Decimal("0")) - base_items.get(category, Decimal("0")), cashflow_currency)}</span>)</li>'  # pyright: ignore[reportOperatorIssue]
        for category in categories
    )

    html = f"""
<section class="cashflow-comparison">
  <h4>Nakit Akışı Karşılaştırması</h4>
  <div class="summary-card">
    <div class="comparison-grid">
      <div>
        <p class="summary-meta"><strong>Tarih:</strong> {base_label}
          <span class="text-muted">({base_period})</span>
        </p>
        <ul class="summary-list">
          <li><strong>Toplam Nakit Akışı:</strong> {_format_currency(base_amount, cashflow_currency)}</li>
          {base_category_rows}
        </ul>
      </div>
      <div>
        <p class="summary-meta"><strong>Tarih:</strong> {compare_label}
          <span class="text-muted">({compare_period})</span>
        </p>
        <ul class="summary-list">
          <li><strong>Toplam Nakit Akışı:</strong> {_format_currency(compare_amount, cashflow_currency)}</li>
          {compare_category_rows}
        </ul>
      </div>
    </div>
    <div class="comparison-footer">
      <p class="summary-meta summary-meta--tight"><strong>Değişim:</strong> {_format_currency(delta, cashflow_currency)} ({escape(f"{float(pct_change):.2f}")}%)</p>
      <ul class="summary-list summary-list--compact">
        {category_delta_rows}
      </ul>
    </div>
  </div>
</section>
"""
    return html


def _render_cashflow_comparison_charts_html(comparison) -> str:
    if not comparison:
        return ""
    base = comparison.base_snapshot
    compare = comparison.compare_snapshot

    payload = {
        "labels": ["Toplam Nakit Akışı"],
        "base": [_safe_float(base.total_amount)],
        "compare": [_safe_float(compare.total_amount)],
        "base_label": f"{base.snapshot_date}",
        "compare_label": f"{compare.snapshot_date}",
    }
    comparison_json = escape(json.dumps(payload, cls=DjangoJSONEncoder))

    return """
<section class="chart-section cashflow-comparison-charts" data-cashflow-comparison="{comparison_json}">
  <div class="chart-fallback cashflow-comparison-chart-fallback is-hidden">
    Grafikler yüklenemedi. (Tarayıcı eklentisi / ağ politikası / CSP engelliyor olabilir.)
  </div>
  <div class="chart-card">
    <h4 class="chart-card__title">Nakit Akışı Karşılaştırma Özeti</h4>
    <canvas data-chart-kind="cashflow-comparison" height="260"></canvas>
  </div>
</section>
""".format(
        comparison_json=comparison_json,
    )


def _render_dividend_summary_html(snapshot) -> str:
    if not snapshot:
        return ""

    total_amount = _format_currency(snapshot.total_amount, snapshot.currency)
    year = escape(str(snapshot.year))
    currency = escape(snapshot.currency)
    payment_items = snapshot.payment_items.select_related("asset").order_by(
        "payment_date"
    )

    context = {
        "snapshot": snapshot,
        "total_amount": total_amount,
        "year": year,
        "currency": currency,
        "payment_items": payment_items,
    }

    return render_to_string("includes/dividend_summary.html", context)


def _render_dividend_charts_html(snapshot) -> str:
    if not snapshot:
        return ""

    items = (
        snapshot.asset_items.select_related("asset")
        .filter(total_amount__gt=0)
        .order_by("-allocation_pct")
    )
    allocation = {
        "labels": [(item.asset.symbol or item.asset.name) for item in items],
        "values": [_safe_float(item.allocation_pct) * 100 for item in items],  # pyright: ignore[reportOptionalOperand]
    }
    allocation_json = escape(json.dumps(allocation, cls=DjangoJSONEncoder))

    return """
<section class="chart-section dividend-charts" data-dividend-allocation="{allocation_json}">
  <div class="chart-fallback dividend-chart-fallback is-hidden">
    Grafikler yüklenemedi. (Tarayıcı eklentisi / ağ politikası / CSP engelliyor olabilir.)
  </div>
  <div class="chart-card">
    <h4 class="chart-card__title">Temettü Dağılımı</h4>
    <canvas data-chart-kind="dividend-allocation" height="220"></canvas>
  </div>
</section>
""".format(
        allocation_json=allocation_json,
    )


def _render_dividend_comparison_html(comparison) -> str:
    if not comparison:
        return ""

    base_snapshot = comparison.base_snapshot
    compare_snapshot = comparison.compare_snapshot
    base_year = escape(str(base_snapshot.year))
    compare_year = escape(str(compare_snapshot.year))
    base_total = _safe_decimal(base_snapshot.total_amount)
    compare_total = _safe_decimal(compare_snapshot.total_amount)
    delta = compare_total - base_total  # pyright: ignore[reportOperatorIssue]
    pct_change = (
        (delta / base_total) * Decimal("100")  # pyright: ignore[reportOperatorIssue]
        if base_total > 0  # pyright: ignore[reportOptionalOperand]
        else Decimal("0")
    )

    base_total_display = _format_currency(base_total, base_snapshot.currency)
    compare_total_display = _format_currency(compare_total, compare_snapshot.currency)
    delta_display = _format_currency(delta, compare_snapshot.currency)

    html = f"""
<section class="dividend-comparison">
  <h4>Temettü Karşılaştırması</h4>
  <div class="summary-card">
    <div class="table-scroll">
      <table class="data-table">
        <thead>
          <tr>
            <th class="data-table__header">Yıl</th>
            <th class="data-table__header">Toplam Temettü</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td class="data-table__cell">{base_year}</td>
            <td class="data-table__cell">{base_total_display}</td>
          </tr>
          <tr>
            <td class="data-table__cell">{compare_year}</td>
            <td class="data-table__cell">{compare_total_display}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <p class="summary-meta summary-meta--spaced"><strong>Değişim:</strong> {delta_display} ({escape(f"{float(pct_change):.2f}")}%)</p>
  </div>
</section>
"""
    return html


@register.simple_tag(takes_context=True)
def portfolio_irr_charts(context, index=None):
    """Post içindeki snapshot IRR grafik alanını HTML olarak döndürür."""
    post = context.get("post")
    snapshot = _get_item_by_identifier(_get_portfolio_snapshots(post), index)
    return mark_safe(_render_portfolio_irr_charts_html(snapshot))


@register.simple_tag(takes_context=True)
def portfolio_summary(context, index=None):
    """Post içindeki snapshot özetini HTML olarak döndürür."""
    post = context.get("post")
    snapshot = _get_item_by_identifier(_get_portfolio_snapshots(post), index)
    return mark_safe(_render_portfolio_summary_html(snapshot))


@register.simple_tag(takes_context=True)
def portfolio_charts(context, index=None):
    """Post içindeki snapshot grafik alanını HTML olarak döndürür."""
    post = context.get("post")
    snapshot = _get_item_by_identifier(_get_portfolio_snapshots(post), index)
    return mark_safe(_render_portfolio_charts_html(snapshot))


@register.simple_tag(takes_context=True)
def portfolio_category_summary(context, index=None):
    """Post içindeki snapshot kategori özet donut grafiğini HTML olarak döndürür."""
    post = context.get("post")
    snapshot = _get_item_by_identifier(_get_portfolio_snapshots(post), index)
    return mark_safe(_render_portfolio_category_summary_html(snapshot))


@register.simple_tag(takes_context=True)
def portfolio_comparison_summary(context, index=None):
    """Post içindeki karşılaştırma özetini HTML olarak döndürür."""
    post = context.get("post")
    comparison = _get_item_by_identifier(_get_portfolio_comparisons(post), index)
    return mark_safe(_render_portfolio_comparison_summary_html(comparison))


@register.simple_tag(takes_context=True)
def portfolio_comparison_charts(context, index=None):
    """Post içindeki karşılaştırma grafik alanını HTML olarak döndürür."""
    post = context.get("post")
    comparison = _get_item_by_identifier(_get_portfolio_comparisons(post), index)
    return mark_safe(_render_portfolio_comparison_charts_html(comparison))


@register.simple_tag(takes_context=True)
def cashflow_summary(context, index=None):
    """Post içindeki nakit akışı snapshot özetini HTML olarak döndürür."""
    post = context.get("post")
    snapshot = _get_item_by_identifier(_get_cashflow_snapshots(post), index)
    return mark_safe(_render_cashflow_summary_html(snapshot))


@register.simple_tag(takes_context=True)
def cashflow_charts(context, index=None):
    """Post içindeki nakit akışı snapshot grafik alanını HTML olarak döndürür."""
    post = context.get("post")
    snapshot = _get_item_by_identifier(_get_cashflow_snapshots(post), index)
    return mark_safe(_render_cashflow_charts_html(snapshot))


@register.simple_tag(takes_context=True)
def savings_rate_summary(context, index=None):
    """Post içindeki maaş/tasarruf snapshot özetini HTML olarak döndürür."""
    post = context.get("post")
    snapshot = _get_item_by_identifier(_get_salary_savings_snapshots(post), index)
    return mark_safe(_render_savings_rate_summary_html(snapshot))


@register.simple_tag(takes_context=True)
def savings_rate_charts(context, index=None):
    """Post içindeki maaş/tasarruf oranı grafik alanını HTML olarak döndürür."""
    post = context.get("post")
    snapshot = _get_item_by_identifier(_get_salary_savings_snapshots(post), index)
    return mark_safe(_render_savings_rate_charts_html(snapshot))


@register.simple_tag(takes_context=True)
def cashflow_comparison_summary(context, index=None):
    """Post içindeki nakit akışı karşılaştırma özetini HTML olarak döndürür."""
    post = context.get("post")
    comparison = _get_item_by_identifier(_get_cashflow_comparisons(post), index)
    return mark_safe(_render_cashflow_comparison_summary_html(comparison))


@register.simple_tag(takes_context=True)
def cashflow_comparison_charts(context, index=None):
    """Post içindeki nakit akışı karşılaştırma grafik alanını HTML olarak döndürür."""
    post = context.get("post")
    comparison = _get_item_by_identifier(_get_cashflow_comparisons(post), index)
    return mark_safe(_render_cashflow_comparison_charts_html(comparison))


@register.simple_tag(takes_context=True)
def dividend_summary(context, index=None):
    """Post içindeki temettü snapshot özetini HTML olarak döndürür."""
    post = context.get("post")
    snapshot = _get_item_by_identifier(_get_dividend_snapshots(post), index)
    return mark_safe(_render_dividend_summary_html(snapshot))


@register.simple_tag(takes_context=True)
def dividend_charts(context, index=None):
    """Post içindeki temettü snapshot grafik alanını HTML olarak döndürür."""
    post = context.get("post")
    snapshot = _get_item_by_identifier(_get_dividend_snapshots(post), index)
    return mark_safe(_render_dividend_charts_html(snapshot))


@register.simple_tag(takes_context=True)
def dividend_comparison(context, index=None):
    """Post içindeki temettü karşılaştırma tablosunu HTML olarak döndürür."""
    post = context.get("post")
    comparison = _get_item_by_identifier(_get_dividend_comparisons(post), index)
    return mark_safe(_render_dividend_comparison_html(comparison))


MARKER_MAP = {
    "portfolio_summary": (_get_portfolio_snapshots, _render_portfolio_summary_html),
    "portfolio_charts": (_get_portfolio_snapshots, _render_portfolio_charts_html),
    "portfolio_irr_charts": (
        _get_portfolio_snapshots,
        _render_portfolio_irr_charts_html,
    ),
    "portfolio_category_summary": (
        _get_portfolio_snapshots,
        _render_portfolio_category_summary_html,
    ),
    "portfolio_comparison_summary": (
        _get_portfolio_comparisons,
        _render_portfolio_comparison_summary_html,
    ),
    "portfolio_comparison_charts": (
        _get_portfolio_comparisons,
        _render_portfolio_comparison_charts_html,
    ),
    "cashflow_summary": (_get_cashflow_snapshots, _render_cashflow_summary_html),
    "cashflow_charts": (_get_cashflow_snapshots, _render_cashflow_charts_html),
    "cashflow_comparison_summary": (
        _get_cashflow_comparisons,
        _render_cashflow_comparison_summary_html,
    ),
    "cashflow_comparison_charts": (
        _get_cashflow_comparisons,
        _render_cashflow_comparison_charts_html,
    ),
    "savings_rate_summary": (
        _get_salary_savings_snapshots,
        _render_savings_rate_summary_html,
    ),
    "savings_rate_charts": (
        _get_salary_savings_snapshots,
        _render_savings_rate_charts_html,
    ),
    "dividend_summary": (_get_dividend_snapshots, _render_dividend_summary_html),
    "dividend_charts": (_get_dividend_snapshots, _render_dividend_charts_html),
    "dividend_comparison": (
        _get_dividend_comparisons,
        _render_dividend_comparison_html,
    ),
}


@register.simple_tag(takes_context=True)
def render_post_body(context, post):
    """BlogPost içeriğini (markdown) render eder; image + portfolio placeholder'larını genişletir.

    Kullanım:
      {% render_post_body post %}

    Markdown içinde kullanılabilen marker'lar:
      {{ image:1 }}  (1-based)
      {{ portfolio_summary:slug_or_hash }}
      {{ portfolio_charts:slug_or_hash }}
      {{ portfolio_category_summary:slug_or_hash }}
      {{ portfolio_comparison_summary:slug_or_hash }}
      {{ portfolio_comparison_charts:slug_or_hash }}
      {{ cashflow_summary:slug_or_hash }}
      {{ cashflow_charts:slug_or_hash }}
      {{ cashflow_comparison_summary:slug_or_hash }}
      {{ cashflow_comparison_charts:slug_or_hash }}
      {{ savings_rate_summary:slug_or_hash }}
      {{ savings_rate_charts:slug_or_hash }}
      {{ dividend_summary:slug_or_hash }}
      {{ dividend_charts:slug_or_hash }}
      {{ dividend_comparison:slug_or_hash }}
      {{ legal_disclaimer }}
    """
    images = list(
        getattr(post, "images", []).all() if getattr(post, "images", None) else []  # pyright: ignore[reportAttributeAccessIssue]
    )
    content = getattr(post, "content", "") or ""

    legal_disclaimer_html = """
<aside class="legal-disclaimer-inline">
  <p class="legal-disclaimer-inline__title">YASAL UYARI</p>
  <p class="legal-disclaimer-inline__text">
    Burada yer alan yatırım bilgi, yorum ve tavsiyeleri yatırım danışmanlığı kapsamında değildir.
    Yatırım danışmanlığı hizmeti, kişilerin risk ve getiri tercihleri dikkate alınarak kişiye özel
    sunulmaktadır. Burada yer alan ve hiçbir şekilde yönlendirici nitelikte olmayan içerik, yorum ve
    tavsiyeler ise genel niteliktedir. Bu tavsiyeler mali durumunuz ile risk ve getiri tercihlerinize
    uygun olmayabilir. Bu nedenle, sadece burada yer alan bilgilere dayanılarak yatırım kararı
    verilmesi beklentilerinize uygun sonuçlar doğurmayabilir.
  </p>
</aside>
"""

    cached_items = {}

    def replacer(match):
        tag = match.group("tag")
        arg = match.group("arg")

        if tag == "image":
            if not arg:
                return ""
            try:
                index = int(arg) - 1
            except ValueError:
                return ""
            if index < 0 or index >= len(images):
                return ""
            return _render_responsive_image_figure(images[index])

        elif tag == "legal_disclaimer":
            return legal_disclaimer_html

        elif tag in MARKER_MAP:
            getter, render_func = MARKER_MAP[tag]

            if getter not in cached_items:
                cached_items[getter] = getter(post)

            items = cached_items[getter]
            item = _get_item_by_identifier(items, arg)
            return render_func(item)

        return match.group(0)

    expanded = GENERIC_PATTERN.sub(replacer, content)

    return mark_safe(render_markdown(expanded))


@register.filter
@log_exceptions(
    default=0,
    exception_types=(TypeError,),
    message="Error in mul100 filter",
)
def mul100(value):
    """Decimal/float oranı yüzdeye çevirir. Örn: 0.12 -> 12.0"""
    return (value or 0) * 100


@register.filter
def format_currency(value, currency_code: str | None) -> str:
    return _format_currency(value, currency_code)


@register.filter
def safe_float(value) -> float:
    return _safe_float(value)  # pyright: ignore[reportReturnType]
