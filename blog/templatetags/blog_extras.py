import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

from core.markdown import render_markdown

register = template.Library()

IMAGE_PATTERN = re.compile(r"\{\{\s*image:(\d+)\s*\}\}")
# Markdown içindeki placeholder'lar
PORTFOLIO_SUMMARY_PATTERN = re.compile(r"\{\{\s*portfolio_summary\s*\}\}")
PORTFOLIO_CHARTS_PATTERN = re.compile(r"\{\{\s*portfolio_charts\s*\}\}")


@register.filter
def render_post_content(content, images):
    images = list(images)

    def replacer(match):
        index = int(match.group(1)) - 1
        if index < 0 or index >= len(images):
            return ""

        img = images[index]

        # Markdown içinde "ham HTML" olarak kalacak bir figure döndürüyoruz
        # srcset / sizes: senin ImageKit türevlerine göre
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

    # 1) Placeholder -> HTML figure
    expanded = IMAGE_PATTERN.sub(replacer, content or "")

    # 2) Markdown -> sanitize edilmiş HTML
    return render_markdown(expanded)


def _render_portfolio_summary_html(snapshot) -> str:
    if not snapshot:
        return ""

    # Sayısal alanlar Decimal olabilir; string'e çeviriyoruz.
    total_return_pct = snapshot.total_return_pct
    try:
        total_return_pct = (total_return_pct or 0) * 100
    except TypeError:
        total_return_pct = 0

    # escape: olası kullanıcı girdilerini güvenli hale getir
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

    # Canvas id'leri JS tarafında sabit bekleniyor.
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
def render_post_body(context, post):
    """BlogPost içeriğini (markdown) render eder; image + portfolio placeholder'larını genişletir.

    Kullanım:
      {% render_post_body post %}

    Markdown içinde kullanılabilen marker'lar:
      {{ image:1 }}  (1-based)
      {{ portfolio_summary }}
      {{ portfolio_charts }}
    """
    images = list(
        getattr(post, "images", []).all() if getattr(post, "images", None) else []
    )
    snapshot = getattr(post, "portfolio_snapshot", None)
    content = getattr(post, "content", "") or ""

    # 1) image placeholder -> <figure>
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

    # 2) portfolio placeholders
    expanded = PORTFOLIO_SUMMARY_PATTERN.sub(
        _render_portfolio_summary_html(snapshot), expanded
    )
    expanded = PORTFOLIO_CHARTS_PATTERN.sub(
        _render_portfolio_charts_html(snapshot), expanded
    )

    # 3) markdown -> sanitized html
    return mark_safe(render_markdown(expanded))


@register.filter
def mul100(value):
    """Decimal/float oranı yüzdeye çevirir. Örn: 0.12 -> 12.0"""
    try:
        return (value or 0) * 100
    except TypeError:
        return 0
