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
PORTFOLIO_SUMMARY_PATTERN = re.compile(r"\{\{\s*portfolio_summary\s*\}\}")
PORTFOLIO_CHARTS_PATTERN = re.compile(r"\{\{\s*portfolio_charts\s*\}\}")
PORTFOLIO_COMPARISON_SUMMARY_PATTERN = re.compile(
    r"\{\{\s*portfolio_comparison_summary\s*\}\}"
)
PORTFOLIO_COMPARISON_CHARTS_PATTERN = re.compile(
    r"\{\{\s*portfolio_comparison_charts\s*\}\}"
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
    total_value = escape(str(snapshot.total_value))
    total_cost = escape(str(snapshot.total_cost))
    target_value = (
        escape(str(snapshot.target_value)) if snapshot.target_value is not None else ""
    )
    total_return_pct_s = escape(f"{float(total_return_pct):.2f}")

    target_li = (
        f"<li><strong>Hedef Değer:</strong> {target_value}</li>" if target_value else ""
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
      <li><strong>Toplam Getiri (%):</strong> {total_return_pct_s}</li>
    </ul>
  </div>
</section>
"""
    return html


def _render_portfolio_charts_html(snapshot) -> str:
    if not snapshot:
        return ""

    return """
<section class="portfolio-charts" style="margin: 1rem 0">
  <div id="chartFallback" style="display:none; padding: 0.75rem 1rem; border: 1px solid #f2c2c2; background: #fff5f5; border-radius: 8px; margin-bottom: 1rem;">
    Grafikler yüklenemedi. (Tarayıcı eklentisi / ağ politikası / CSP engelliyor olabilir.)
  </div>

  <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem">
    <div style="border: 1px solid #eee; border-radius: 8px; padding: 1rem">
      <h4 style="margin-top: 0">Dağılım</h4>
      <canvas id="allocationDonut" height="220"></canvas>
    </div>

    <div style="border: 1px solid #eee; border-radius: 8px; padding: 1rem">
      <h4 style="margin-top: 0">Portföy Değeri (Zaman Serisi)</h4>
      <canvas id="valueSeries" height="220"></canvas>
    </div>
  </div>
</section>
"""


def _safe_decimal(value) -> Decimal:
    try:
        return value or Decimal("0")
    except TypeError:
        return Decimal("0")


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

    value_delta = compare_value - base_value
    return_delta = compare_return - base_return

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
          <li><strong>Toplam Değer:</strong> {escape(str(base_value))}</li>
          <li><strong>Toplam Maliyet:</strong> {escape(str(base_cost))}</li>
          <li><strong>Toplam Getiri (%):</strong> {escape(f"{float(base_return):.2f}")}</li>
        </ul>
      </div>
      <div>
        <p style="margin: 0 0 0.25rem 0"><strong>Tarih:</strong> {compare_label}
          <span style="opacity: 0.7">({compare_period})</span>
        </p>
        <ul style="list-style: none; padding-left: 0; margin: 0">
          <li><strong>Toplam Değer:</strong> {escape(str(compare_value))}</li>
          <li><strong>Toplam Maliyet:</strong> {escape(str(compare_cost))}</li>
          <li><strong>Toplam Getiri (%):</strong> {escape(f"{float(compare_return):.2f}")}</li>
        </ul>
      </div>
    </div>
    <div style="margin-top: 0.75rem; padding-top: 0.75rem; border-top: 1px solid #eee">
      <p style="margin: 0"><strong>Değişim:</strong> Toplam Değer {escape(str(value_delta))},
        Getiri {escape(f"{float(return_delta):.2f}")}%</p>
    </div>
  </div>
</section>
"""
    return html


def _render_portfolio_comparison_charts_html(comparison) -> str:
    if not comparison:
        return ""

    return """
<section class="portfolio-comparison-charts" style="margin: 1rem 0">
  <div id="comparisonChartFallback" style="display:none; padding: 0.75rem 1rem; border: 1px solid #f2c2c2; background: #fff5f5; border-radius: 8px; margin-bottom: 1rem;">
    Grafikler yüklenemedi. (Tarayıcı eklentisi / ağ politikası / CSP engelliyor olabilir.)
  </div>
  <div style="border: 1px solid #eee; border-radius: 8px; padding: 1rem">
    <h4 style="margin-top: 0">Karşılaştırma Özeti</h4>
    <canvas id="comparisonChart" height="260"></canvas>
  </div>
</section>
"""


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
def portfolio_summary(context):
    """Post içindeki snapshot özetini HTML olarak döndürür."""
    post = context.get("post")
    snapshot = getattr(post, "portfolio_snapshot", None) if post else None
    return mark_safe(_render_portfolio_summary_html(snapshot))


@register.simple_tag(takes_context=True)
def portfolio_charts(context):
    """Post içindeki snapshot grafik alanını HTML olarak döndürür."""
    post = context.get("post")
    snapshot = getattr(post, "portfolio_snapshot", None) if post else None
    return mark_safe(_render_portfolio_charts_html(snapshot))


@register.simple_tag(takes_context=True)
def portfolio_comparison_summary(context):
    """Post içindeki karşılaştırma özetini HTML olarak döndürür."""
    post = context.get("post")
    comparison = getattr(post, "portfolio_comparison", None) if post else None
    return mark_safe(_render_portfolio_comparison_summary_html(comparison))


@register.simple_tag(takes_context=True)
def portfolio_comparison_charts(context):
    """Post içindeki karşılaştırma grafik alanını HTML olarak döndürür."""
    post = context.get("post")
    comparison = getattr(post, "portfolio_comparison", None) if post else None
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
      {{ portfolio_summary }}
      {{ portfolio_charts }}
      {{ portfolio_comparison_summary }}
      {{ portfolio_comparison_charts }}
      {{ cashflow_summary:1 }}
      {{ cashflow_charts:1 }}
      {{ cashflow_comparison_summary:1 }}
      {{ cashflow_comparison_charts:1 }}
    """
    images = list(
        getattr(post, "images", []).all() if getattr(post, "images", None) else []  # pyright: ignore[reportAttributeAccessIssue]
    )
    snapshot = getattr(post, "portfolio_snapshot", None)
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

    expanded = PORTFOLIO_SUMMARY_PATTERN.sub(
        _render_portfolio_summary_html(snapshot), expanded
    )
    expanded = PORTFOLIO_CHARTS_PATTERN.sub(
        _render_portfolio_charts_html(snapshot), expanded
    )
    comparison = getattr(post, "portfolio_comparison", None)
    expanded = PORTFOLIO_COMPARISON_SUMMARY_PATTERN.sub(
        _render_portfolio_comparison_summary_html(comparison), expanded
    )
    expanded = PORTFOLIO_COMPARISON_CHARTS_PATTERN.sub(
        _render_portfolio_comparison_charts_html(comparison), expanded
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
