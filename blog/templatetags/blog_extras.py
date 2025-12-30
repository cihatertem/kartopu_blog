import re

from django import template

from core.markdown import render_markdown

register = template.Library()

IMAGE_PATTERN = re.compile(r"\{\{\s*image:(\d+)\s*\}\}")


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


@register.filter
def mul100(value):
    """Decimal/float oranı yüzdeye çevirir. Örn: 0.12 -> 12.0"""
    try:
        return (value or 0) * 100
    except TypeError:
        return 0
