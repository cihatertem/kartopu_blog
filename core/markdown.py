from __future__ import annotations

import bleach
import markdown as md
from bleach.css_sanitizer import CSSSanitizer

css_sanitizer = CSSSanitizer(
    allowed_css_properties=[
        "margin",
        "margin-top",
        "margin-bottom",
        "padding",
        "padding-left",
        "border",
        "border-radius",
        "background",
        "opacity",
        "display",
        "grid-template-columns",
        "gap",
        "max-width",
        "height",
        "font-size",
    ]
)

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
        "div",
        "section",
        "canvas",
        "article",
        "main",
    }
)

ALLOWED_ATTRIBUTES = {
    **bleach.sanitizer.ALLOWED_ATTRIBUTES,
    "a": ["href", "title", "rel", "id"],
    "img": ["src", "alt", "title", "loading", "sizes", "srcset", "id"],
    "code": ["class"],
    "span": ["class", "style", "id"],
    "pre": ["class"],
    "div": ["class", "id", "style", "id"],
    "section": ["class", "id", "style"],
    "canvas": ["id", "height", "width", "class"],
    "h1": ["class", "style", "id"],
    "h2": ["class", "style", "id"],
    "h3": ["class", "style", "id"],
    "h4": ["class", "style", "id"],
    "h5": ["class", "style", "id"],
    "h6": ["class", "style", "id"],
    "p": ["class", "style", "id"],
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
        css_sanitizer=css_sanitizer,
    )

    # linkleri daha güvenli yapalım
    cleaned = bleach.linkify(cleaned)
    return cleaned
