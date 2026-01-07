import json
import re
from decimal import Decimal

from django import template
from django.core.serializers.json import DjangoJSONEncoder
from django.utils.html import escape
from django.utils.safestring import mark_safe

from core.markdown import render_markdown
from portfolio.models import CashFlowSnapshot

register = template.Library()

IMAGE_PATTERN = re.compile(r"\{\{\s*image:(\d+)\s*\}\}")
PORTFOLIO_SUMMARY_PATTERN = re.compile(r"\{\{\s*portfolio_summary(?::(\d+))?\s*\}\}")
PORTFOLIO_CHARTS_PATTERN = re.compile(r"\{\{\s*portfolio_charts(?::(\d+))?\s*\}\}")
PORTFOLIO_COMPARISON_SUMMARY_PATTERN = re.compile(
    r"\{\{\s*portfolio_comparison_summary(?::(\d+))?\s*\}\}"
)
PORTFOLIO_COMPARISON_CHARTS_PATTERN = re.compile(
    r"\{\{\s*portfolio_comparison_charts(?::(\d+))?\s*\}\}"
)
CASHFLOW_SUMMARY_PATTERN = re.compile(r"\{\{\s*cashflow_summary(?::(\d+))?\s*\}\}")
CASHFLOW_CHARTS_PATTERN = re.compile(r"\{\{\s*cashflow_charts(?::(\d+))?\s*\}\}")
CASHFLOW_COMPARISON_SUMMARY_PATTERN = re.compile(
    r"\{\{\s*cashflow_comparison_summary(?::(\d+))?\s*\}\}"
)
CASHFLOW_COMPARISON_CHARTS_PATTERN = re.compile(
    r"\{\{\s*cashflow_comparison_charts(?::(\d+))?\s*\}\}"
)


@register.filter
def render_post_content(content, images):
    images = list(images)

    def replacer(match):
        index = int(match.group(1)) - 1
        if index < 0 or index >= len(images):
            return ""

        img = images[index]

        figure = f"""
<figure>
  <img
    src="{img.image_1200.url}"
    srcset="{img.image_600.url} 600w, {img.image_900.url} 900w, {img.image_1200.url} 1200w"
    sizes="(max-width: 768px) 100vw, 720px"
    alt="{img.alt_text}"
    loading="lazy"
  />
"""
        if img.caption:
            figure += f"<figcaption>{img.caption}</figcaption>\n"
        figure += "</figure>"
        return figure

    expanded = IMAGE_PATTERN.sub(replacer, content or "")

    return render_markdown(expanded)


def _render_portfolio_summary_html(snapshot) -> str:
    if not snapshot:
        return ""

    total_return_pct = snapshot.total_return_pct
    try:
        total_return_pct = (total_return_pct or 0) * 100
    except TypeError:
        total_return_pct = 0

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
                f"{float((total_value_decimal / target_value_decimal) * Decimal('100')):.2f}"
            )
    total_return_pct_s = escape(f"{float(total_return_pct):.2f}")

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
  <h3>Bu yazının portföy özeti</h3>
  <div style="border: 1px solid #ddd; border-radius: 8px; padding: 1rem; margin: 1rem 0">
    <p style="margin: 0 0 0.25rem 0"><strong>Portföy:</strong> {portfolio_name}</p>
    <p style="margin: 0 0 0.75rem 0"><strong>Tarih:</strong> {snapshot_date}
      <span style="opacity: 0.7">({period_display})</span>
    </p>
    <ul style="list-style: none; padding-left: 0; margin: 0">
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


def _render_portfolio_charts_html(snapshot) -> str:
    if not snapshot:
        return ""

    items = snapshot.items.select_related("asset").order_by("-allocation_pct")
    allocation = {
        "labels": [(item.asset.symbol or item.asset.name) for item in items],
        "values": [float(item.allocation_pct or 0) * 100 for item in items],
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
        "values": [float(v) for _, v in snapshots_qs],
    }
    allocation_json = escape(json.dumps(allocation, cls=DjangoJSONEncoder))
    timeseries_json = escape(json.dumps(timeseries, cls=DjangoJSONEncoder))

    return """
<section class="portfolio-charts" style="margin: 1rem 0" data-portfolio-allocation="{allocation_json}" data-portfolio-timeseries="{timeseries_json}">
  <div class="portfolio-chart-fallback" style="display:none; padding: 0.75rem 1rem; border: 1px solid #f2c2c2; background: #fff5f5; border-radius: 8px; margin-bottom: 1rem;">
    Grafikler yüklenemedi. (Tarayıcı eklentisi / ağ politikası / CSP engelliyor olabilir.)
  </div>

  <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem">
    <div style="border: 1px solid #eee; border-radius: 8px; padding: 1rem">
      <h4 style="margin-top: 0">Dağılım</h4>
      <canvas data-chart-kind="portfolio-allocation" height="220"></canvas>
    </div>

    <div style="border: 1px solid #eee; border-radius: 8px; padding: 1rem">
      <h4 style="margin-top: 0">Portföy Değeri (Zaman Serisi)</h4>
      <canvas data-chart-kind="portfolio-timeseries" height="220"></canvas>
    </div>
  </div>
</section>
""".format(
        allocation_json=allocation_json,
        timeseries_json=timeseries_json,
    )


def _safe_decimal(value) -> Decimal:
    try:
        return value or Decimal("0")
    except TypeError:
        return Decimal("0")


def _currency_symbol(currency_code: str | None) -> str:
    symbols = {
        "TRY": "₺",
        "USD": "$",
        "EUR": "€",
    }
    return symbols.get(currency_code or "", "")


def _format_currency(value, currency_code: str | None) -> str:
    value_str = escape(str(value))
    symbol = _currency_symbol(currency_code)
    return f"{value_str} {symbol}".rstrip()


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
        ).order_by("created_at"),
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
    base_return = _safe_decimal(base.total_return_pct) * Decimal("100")
    compare_return = _safe_decimal(compare.total_return_pct) * Decimal("100")
    portfolio_currency = getattr(base.portfolio, "currency", None)

    base_target_value = _safe_decimal(base.target_value)
    compare_target_value = _safe_decimal(compare.target_value)
    base_target_ratio = (
        (base_value / base_target_value) * Decimal("100") if base_target_value else None
    )
    compare_target_ratio = (
        (compare_value / compare_target_value) * Decimal("100")
        if compare_target_value
        else None
    )

    value_delta = compare_value - base_value
    return_delta = compare_return - base_return
    target_ratio_delta = None
    if base_target_ratio is not None and compare_target_ratio is not None:
        target_ratio_delta = compare_target_ratio - base_target_ratio

    base_target_ratio_html = (
        f"<li><strong>Hedef Gerçekleşme (%):</strong> {escape(f'{float(base_target_ratio):.2f}')}</li>"
        if base_target_ratio is not None
        else ""
    )
    compare_target_ratio_html = (
        f"<li><strong>Hedef Gerçekleşme (%):</strong> {escape(f'{float(compare_target_ratio):.2f}')}</li>"
        if compare_target_ratio is not None
        else ""
    )
    target_ratio_delta_html = (
        f", Hedef Gerçekleşme {escape(f'{float(target_ratio_delta):.2f}')}%"
        if target_ratio_delta is not None
        else ""
    )

    html = f"""
<section class="portfolio-comparison">
  <h3>Portföy Karşılaştırması</h3>
  <div style="border: 1px solid #ddd; border-radius: 8px; padding: 1rem; margin: 1rem 0">
    <div style="display:grid; gap: 1rem; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));">
      <div>
        <p style="margin: 0 0 0.25rem 0"><strong>Tarih:</strong> {base_label}
          <span style="opacity: 0.7">({base_period})</span>
        </p>
        <ul style="list-style: none; padding-left: 0; margin: 0">
          <li><strong>Toplam Değer:</strong> {_format_currency(base_value, portfolio_currency)}</li>
          <li><strong>Toplam Maliyet:</strong> {_format_currency(base_cost, portfolio_currency)}</li>
          {base_target_ratio_html}
          <li><strong>Toplam Getiri (%):</strong> {escape(f"{float(base_return):.2f}")}</li>
        </ul>
      </div>
      <div>
        <p style="margin: 0 0 0.25rem 0"><strong>Tarih:</strong> {compare_label}
          <span style="opacity: 0.7">({compare_period})</span>
        </p>
        <ul style="list-style: none; padding-left: 0; margin: 0">
          <li><strong>Toplam Değer:</strong> {_format_currency(compare_value, portfolio_currency)}</li>
          <li><strong>Toplam Maliyet:</strong> {_format_currency(compare_cost, portfolio_currency)}</li>
          {compare_target_ratio_html}
          <li><strong>Toplam Getiri (%):</strong> {escape(f"{float(compare_return):.2f}")}</li>
        </ul>
      </div>
    </div>
    <div style="margin-top: 0.75rem; padding-top: 0.75rem; border-top: 1px solid #eee">
      <p style="margin: 0"><strong>Değişim:</strong> Toplam Değer {_format_currency(value_delta, portfolio_currency)},
        Getiri {escape(f"{float(return_delta):.2f}")}%{target_ratio_delta_html}</p>
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

    def safe_float(value):
        try:
            return float(value or 0)
        except TypeError:
            return 0.0

    payload = {
        "labels": ["Toplam Maliyet", "Toplam Değer"],
        "base": [
            safe_float(base.total_cost),
            safe_float(base.total_value),
        ],
        "compare": [
            safe_float(compare.total_cost),
            safe_float(compare.total_value),
        ],
        "base_label": f"{base.snapshot_date}",
        "compare_label": f"{compare.snapshot_date}",
    }
    comparison_json = escape(json.dumps(payload, cls=DjangoJSONEncoder))

    return """
<section class="portfolio-comparison-charts" style="margin: 1rem 0" data-portfolio-comparison="{comparison_json}">
  <div class="portfolio-comparison-chart-fallback" style="display:none; padding: 0.75rem 1rem; border: 1px solid #f2c2c2; background: #fff5f5; border-radius: 8px; margin-bottom: 1rem;">
    Grafikler yüklenemedi. (Tarayıcı eklentisi / ağ politikası / CSP engelliyor olabilir.)
  </div>
  <div style="border: 1px solid #eee; border-radius: 8px; padding: 1rem">
    <h4 style="margin-top: 0">Karşılaştırma Özeti</h4>
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
    period_display = escape(
        snapshot.get_period_display() if hasattr(snapshot, "get_period_display") else ""
    )
    snapshot_date = escape(str(snapshot.snapshot_date))
    total_amount = escape(str(snapshot.total_amount))

    html = f"""
<section class="cashflow-snapshot">
  <h3>Bu yazının nakit akışı özeti</h3>
  <div style="border: 1px solid #ddd; border-radius: 8px; padding: 1rem; margin: 1rem 0">
    <p style="margin: 0 0 0.25rem 0"><strong>Nakit Akışı:</strong> {cashflow_name}</p>
    <p style="margin: 0 0 0.75rem 0"><strong>Tarih:</strong> {snapshot_date}
      <span style="opacity: 0.7">({period_display})</span>
    </p>
    <ul style="list-style: none; padding-left: 0; margin: 0">
      <li><strong>Toplam Nakit Akışı:</strong> {total_amount}</li>
    </ul>
  </div>
</section>
"""
    return html


def _render_cashflow_charts_html(snapshot) -> str:
    if not snapshot:
        return ""

    items = snapshot.items.order_by("-allocation_pct")
    allocation = {
        "labels": [item.get_category_display() for item in items],
        "values": [float(item.allocation_pct or 0) * 100 for item in items],
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
        "values": [float(v) for _, v in snapshots_qs],
    }
    allocation_json = escape(json.dumps(allocation, cls=DjangoJSONEncoder))
    timeseries_json = escape(json.dumps(timeseries, cls=DjangoJSONEncoder))

    return """
<section class="cashflow-charts" style="margin: 1rem 0" data-cashflow-allocation="{allocation_json}" data-cashflow-timeseries="{timeseries_json}">
    <div class="cashflow-chart-fallback" style="display:none; padding: 0.75rem 1rem; border: 1px solid #f2c2c2; background: #fff5f5; border-radius: 8px; margin-bottom: 1rem;">
    Grafikler yüklenemedi. (Tarayıcı eklentisi / ağ politikası / CSP engelliyor olabilir.)
  </div>

  <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem">
    <div style="border: 1px solid #eee; border-radius: 8px; padding: 1rem">
      <h4 style="margin-top: 0">Nakit Akışı Dağılımı</h4>
      <canvas data-chart-kind="cashflow-allocation" height="220"></canvas>
    </div>

    <div style="border: 1px solid #eee; border-radius: 8px; padding: 1rem">
      <h4 style="margin-top: 0">Nakit Akışı (Zaman Serisi)</h4>
      <canvas data-chart-kind="cashflow-timeseries" height="220"></canvas>
    </div>
  </div>
</section>
""".format(
        allocation_json=allocation_json,
        timeseries_json=timeseries_json,
    )


def _render_cashflow_comparison_summary_html(comparison) -> str:
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

    base_amount = _safe_decimal(base.total_amount)
    compare_amount = _safe_decimal(compare.total_amount)
    delta = compare_amount - base_amount
    pct_change = (
        (delta / base_amount) * Decimal("100") if base_amount > 0 else Decimal("0")
    )

    html = f"""
<section class="cashflow-comparison">
  <h3>Nakit Akışı Karşılaştırması</h3>
  <div style="border: 1px solid #ddd; border-radius: 8px; padding: 1rem; margin: 1rem 0">
    <div style="display:grid; gap: 1rem; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));">
      <div>
        <p style="margin: 0 0 0.25rem 0"><strong>Tarih:</strong> {base_label}
          <span style="opacity: 0.7">({base_period})</span>
        </p>
        <ul style="list-style: none; padding-left: 0; margin: 0">
          <li><strong>Toplam Nakit Akışı:</strong> {escape(str(base_amount))}</li>
        </ul>
      </div>
      <div>
        <p style="margin: 0 0 0.25rem 0"><strong>Tarih:</strong> {compare_label}
          <span style="opacity: 0.7">({compare_period})</span>
        </p>
        <ul style="list-style: none; padding-left: 0; margin: 0">
          <li><strong>Toplam Nakit Akışı:</strong> {escape(str(compare_amount))}</li>
        </ul>
      </div>
    </div>
    <div style="margin-top: 0.75rem; padding-top: 0.75rem; border-top: 1px solid #eee">
      <p style="margin: 0"><strong>Değişim:</strong> {escape(str(delta))} ({escape(f"{float(pct_change):.2f}")}%)</p>
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

    def safe_float(value):
        try:
            return float(value or 0)
        except TypeError:
            return 0.0

    payload = {
        "labels": ["Toplam Nakit Akışı"],
        "base": [safe_float(base.total_amount)],
        "compare": [safe_float(compare.total_amount)],
        "base_label": f"{base.snapshot_date}",
        "compare_label": f"{compare.snapshot_date}",
    }
    comparison_json = escape(json.dumps(payload, cls=DjangoJSONEncoder))

    return """
<section class="cashflow-comparison-charts" style="margin: 1rem 0" data-cashflow-comparison="{comparison_json}">
  <div class="cashflow-comparison-chart-fallback" style="display:none; padding: 0.75rem 1rem; border: 1px solid #f2c2c2; background: #fff5f5; border-radius: 8px; margin-bottom: 1rem;">
    Grafikler yüklenemedi. (Tarayıcı eklentisi / ağ politikası / CSP engelliyor olabilir.)
  </div>
  <div style="border: 1px solid #eee; border-radius: 8px; padding: 1rem">
    <h4 style="margin-top: 0">Nakit Akışı Karşılaştırma Özeti</h4>
    <canvas data-chart-kind="cashflow-comparison" height="260"></canvas>
  </div>
</section>
""".format(
        comparison_json=comparison_json,
    )


@register.simple_tag(takes_context=True)
def portfolio_summary(context, index=None):
    """Post içindeki snapshot özetini HTML olarak döndürür."""
    post = context.get("post")
    snapshot = _get_indexed_item(_get_portfolio_snapshots(post), index)
    return mark_safe(_render_portfolio_summary_html(snapshot))


@register.simple_tag(takes_context=True)
def portfolio_charts(context, index=None):
    """Post içindeki snapshot grafik alanını HTML olarak döndürür."""
    post = context.get("post")
    snapshot = _get_indexed_item(_get_portfolio_snapshots(post), index)
    return mark_safe(_render_portfolio_charts_html(snapshot))


@register.simple_tag(takes_context=True)
def portfolio_comparison_summary(context, index=None):
    """Post içindeki karşılaştırma özetini HTML olarak döndürür."""
    post = context.get("post")
    comparison = _get_indexed_item(_get_portfolio_comparisons(post), index)
    return mark_safe(_render_portfolio_comparison_summary_html(comparison))


@register.simple_tag(takes_context=True)
def portfolio_comparison_charts(context, index=None):
    """Post içindeki karşılaştırma grafik alanını HTML olarak döndürür."""
    post = context.get("post")
    comparison = _get_indexed_item(_get_portfolio_comparisons(post), index)
    return mark_safe(_render_portfolio_comparison_charts_html(comparison))


@register.simple_tag(takes_context=True)
def cashflow_summary(context):
    """Post içindeki nakit akışı snapshot özetini HTML olarak döndürür."""
    post = context.get("post")
    snapshot = _get_indexed_item(_get_cashflow_snapshots(post), None)
    return mark_safe(_render_cashflow_summary_html(snapshot))


@register.simple_tag(takes_context=True)
def cashflow_charts(context):
    """Post içindeki nakit akışı snapshot grafik alanını HTML olarak döndürür."""
    post = context.get("post")
    snapshot = _get_indexed_item(_get_cashflow_snapshots(post), None)
    return mark_safe(_render_cashflow_charts_html(snapshot))


@register.simple_tag(takes_context=True)
def cashflow_comparison_summary(context):
    """Post içindeki nakit akışı karşılaştırma özetini HTML olarak döndürür."""
    post = context.get("post")
    comparison = _get_indexed_item(_get_cashflow_comparisons(post), None)
    return mark_safe(_render_cashflow_comparison_summary_html(comparison))


@register.simple_tag(takes_context=True)
def cashflow_comparison_charts(context):
    """Post içindeki nakit akışı karşılaştırma grafik alanını HTML olarak döndürür."""
    post = context.get("post")
    comparison = _get_indexed_item(_get_cashflow_comparisons(post), None)
    return mark_safe(_render_cashflow_comparison_charts_html(comparison))


@register.simple_tag(takes_context=True)
def render_post_body(context, post):
    """BlogPost içeriğini (markdown) render eder; image + portfolio placeholder'larını genişletir.

    Kullanım:
      {% render_post_body post %}

    Markdown içinde kullanılabilen marker'lar:
      {{ image:1 }}  (1-based)
      {{ portfolio_summary:1 }}
      {{ portfolio_charts:1 }}
      {{ portfolio_comparison_summary:1 }}
      {{ portfolio_comparison_charts:1 }}
      {{ cashflow_summary:1 }}
      {{ cashflow_charts:1 }}
      {{ cashflow_comparison_summary:1 }}
      {{ cashflow_comparison_charts:1 }}
    """
    images = list(
        getattr(post, "images", []).all() if getattr(post, "images", None) else []  # pyright: ignore[reportAttributeAccessIssue]
    )
    content = getattr(post, "content", "") or ""

    def image_replacer(match):
        index = int(match.group(1)) - 1
        if index < 0 or index >= len(images):
            return ""
        img = images[index]

        figure = f"""
<figure>
  <img
    src="{img.image_1200.url}"
    srcset="{img.image_600.url} 600w, {img.image_900.url} 900w, {img.image_1200.url} 1200w"
    sizes="(max-width: 768px) 100vw, 720px"
    alt="{escape(img.alt_text or "")}"
    loading="lazy"
  />
"""
        if img.caption:
            figure += f"<figcaption>{escape(img.caption)}</figcaption>\n"
        figure += "</figure>"
        return figure

    expanded = IMAGE_PATTERN.sub(image_replacer, content)

    portfolio_snapshots = _get_portfolio_snapshots(post)
    portfolio_comparisons = _get_portfolio_comparisons(post)

    def portfolio_summary_replacer(match):
        index = int(match.group(1)) if match.group(1) else None
        snapshot = _get_indexed_item(portfolio_snapshots, index)
        return _render_portfolio_summary_html(snapshot)

    def portfolio_charts_replacer(match):
        index = int(match.group(1)) if match.group(1) else None
        snapshot = _get_indexed_item(portfolio_snapshots, index)
        return _render_portfolio_charts_html(snapshot)

    def portfolio_comparison_summary_replacer(match):
        index = int(match.group(1)) if match.group(1) else None
        comparison = _get_indexed_item(portfolio_comparisons, index)
        return _render_portfolio_comparison_summary_html(comparison)

    def portfolio_comparison_charts_replacer(match):
        index = int(match.group(1)) if match.group(1) else None
        comparison = _get_indexed_item(portfolio_comparisons, index)
        return _render_portfolio_comparison_charts_html(comparison)

    expanded = PORTFOLIO_SUMMARY_PATTERN.sub(portfolio_summary_replacer, expanded)
    expanded = PORTFOLIO_CHARTS_PATTERN.sub(portfolio_charts_replacer, expanded)
    expanded = PORTFOLIO_COMPARISON_SUMMARY_PATTERN.sub(
        portfolio_comparison_summary_replacer, expanded
    )
    expanded = PORTFOLIO_COMPARISON_CHARTS_PATTERN.sub(
        portfolio_comparison_charts_replacer, expanded
    )
    cashflow_snapshots = _get_cashflow_snapshots(post)
    cashflow_comparisons = _get_cashflow_comparisons(post)

    def cashflow_summary_replacer(match):
        index = int(match.group(1)) if match.group(1) else None
        snapshot = _get_indexed_item(cashflow_snapshots, index)
        return _render_cashflow_summary_html(snapshot)

    def cashflow_charts_replacer(match):
        index = int(match.group(1)) if match.group(1) else None
        snapshot = _get_indexed_item(cashflow_snapshots, index)
        return _render_cashflow_charts_html(snapshot)

    def cashflow_comparison_summary_replacer(match):
        index = int(match.group(1)) if match.group(1) else None
        comparison = _get_indexed_item(cashflow_comparisons, index)
        return _render_cashflow_comparison_summary_html(comparison)

    def cashflow_comparison_charts_replacer(match):
        index = int(match.group(1)) if match.group(1) else None
        comparison = _get_indexed_item(cashflow_comparisons, index)
        return _render_cashflow_comparison_charts_html(comparison)

    expanded = CASHFLOW_SUMMARY_PATTERN.sub(cashflow_summary_replacer, expanded)
    expanded = CASHFLOW_CHARTS_PATTERN.sub(cashflow_charts_replacer, expanded)
    expanded = CASHFLOW_COMPARISON_SUMMARY_PATTERN.sub(
        cashflow_comparison_summary_replacer, expanded
    )
    expanded = CASHFLOW_COMPARISON_CHARTS_PATTERN.sub(
        cashflow_comparison_charts_replacer, expanded
    )

    return mark_safe(render_markdown(expanded))


@register.filter
def mul100(value):
    """Decimal/float oranı yüzdeye çevirir. Örn: 0.12 -> 12.0"""
    try:
        return (value or 0) * 100
    except TypeError:
        return 0
