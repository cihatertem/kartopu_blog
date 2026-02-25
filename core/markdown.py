from __future__ import annotations

from urllib.parse import urlparse

import bleach
import markdown as md
from bleach.css_sanitizer import CSSSanitizer
from django.conf import settings

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
        "border-collapse",
        "opacity",
        "display",
        "grid",
        "grid-template-rows",
        "grid-template-columns",
        "gap",
        "min-width",
        "max-width",
        "height",
        "font-size",
        "flex",
        "flex-direction",
        "justify-content",
        "align-items",
        "text-indent",
        "text-align",
        "color",
        "background-color",
        "width",
        "float",
        "text-decoration",
        "font-weight",
        "font-family",
        "box-shadow",
        "line-height",
        "overflow",
        "white-space",
        "vertical-align",
        "list-style-type",
        "text-transform",
        "letter-spacing",
        "box-sizing",
        "object-fit",
        "object-position",
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
        "table",
        "thead",
        "tbody",
        "tr",
        "th",
        "td",
        "caption",
    }
)

ALLOWED_ATTRIBUTES = {
    **bleach.sanitizer.ALLOWED_ATTRIBUTES,
    "a": ["href", "title", "rel", "id"],
    "img": ["src", "alt", "title", "loading", "sizes", "srcset", "id"],
    "code": ["class"],
    "span": ["class", "style", "id"],
    "pre": ["class"],
    "div": ["class", "id", "style"],
    "article": ["class", "id", "style"],
    "section": [
        "class",
        "id",
        "style",
        "data-cashflow-allocation",
        "data-cashflow-timeseries",
        "data-cashflow-comparison",
        "data-portfolio-allocation",
        "data-portfolio-timeseries",
        "data-portfolio-comparison",
        "data-portfolio-irr",
        "data-portfolio-category-allocation",
        "data-dividend-allocation",
        "data-savings-rate-timeseries",
    ],
    "main": ["class", "id", "style"],
    "table": ["class", "id", "style"],
    "thead": ["class", "id", "style"],
    "tbody": ["class", "id", "style"],
    "tr": ["class", "id", "style"],
    "th": ["class", "id", "style"],
    "td": ["class", "id", "style"],
    "canvas": ["id", "height", "width", "class", "data-chart-kind"],
    "h1": ["class", "style", "id"],
    "h2": ["class", "style", "id"],
    "h3": ["class", "style", "id"],
    "h4": ["class", "style", "id"],
    "h5": ["class", "style", "id"],
    "h6": ["class", "style", "id"],
    "p": ["class", "style", "id"],
    "figure": ["class", "style", "id"],
    "figcaption": ["class", "style", "id"],
    "caption": ["class", "style", "id"],
}

ALLOWED_PROTOCOLS = ["http", "https", "mailto"]


def set_link_attributes(attrs, new=False):
    href = attrs.get((None, "href"), "")
    if not href:
        return attrs

    is_internal = False
    if href.startswith("/") and not href.startswith("//"):
        is_internal = True
    elif href.startswith("#"):
        is_internal = True
    else:
        parsed_href = urlparse(href)
        if not parsed_href.netloc:
            is_internal = True
        else:
            site_url = getattr(settings, "SITE_BASE_URL", "")
            if site_url:
                parsed_site = urlparse(site_url)
                if (
                    parsed_href.netloc == parsed_site.netloc
                    or parsed_href.netloc.endswith("." + parsed_site.netloc)
                ):
                    is_internal = True

    rel = attrs.get((None, "rel"), "")
    rel_list = rel.split() if rel else []

    if is_internal:
        if "nofollow" in rel_list:
            rel_list.remove("nofollow")
    else:
        if "nofollow" not in rel_list:
            rel_list.append("nofollow")

    if rel_list:
        attrs[(None, "rel")] = " ".join(rel_list)
    else:
        attrs.pop((None, "rel"), None)

    return attrs


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

    cleaned = bleach.linkify(cleaned, callbacks=[set_link_attributes])
    return cleaned
