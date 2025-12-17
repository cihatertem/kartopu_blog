import re

from django import template

register = template.Library()

IMAGE_PATTERN = re.compile(r"\{\{\s*image:(\d+)\s*\}\}")


@register.filter
def render_post_content(content, images):
    images = list(images)

    def replacer(match):
        index = int(match.group(1)) - 1
        if index < 0 or index >= len(images):
            return ""

        image = images[index]

        return f"""
        <figure>
          <img
            src="{image.image_1200.url}"
            srcset="{image.image_600.url} 600w, {image.image_900.url} 900w, {image.image_1200.url} 1200w"
            sizes="(max-width: 768px) 100vw, 720px"
            alt="{image.alt_text}"
            loading="lazy"
          >
          {f"<figcaption>{image.caption}</figcaption>" if image.caption else ""}
        </figure>
        """

    return IMAGE_PATTERN.sub(replacer, content)
