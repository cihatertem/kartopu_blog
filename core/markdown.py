from __future__ import annotations

import bleach
import markdown as md

# Basit ama yeterli whitelist (ihtiyaca göre genişletiriz)
ALLOWED_TAGS = bleach.sanitizer.ALLOWED_TAGS.union(
    {
        "p",
        "pre",
        "code",
        "blockquote",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "hr",
        "br",
        "img",
        "figure",
        "figcaption",
        "span",
    }
)

ALLOWED_ATTRIBUTES = {
    **bleach.sanitizer.ALLOWED_ATTRIBUTES,
    "a": ["href", "title", "rel"],
    "img": ["src", "alt", "title", "loading", "sizes", "srcset"],
    "code": ["class"],
    "span": ["class"],
    "pre": ["class"],
}

ALLOWED_PROTOCOLS = ["http", "https", "mailto"]


def render_markdown(text: str) -> str:
    """
    Markdown -> HTML -> sanitize
    """
    html = md.markdown(
        text or "",
        extensions=[
            "fenced_code",
            "codehilite",
            "tables",
            "toc",
            "nl2br",
        ],
        output_format="html",
    )

    cleaned = bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    )

    # linkleri daha güvenli yapalım
    cleaned = bleach.linkify(cleaned)
    return cleaned
