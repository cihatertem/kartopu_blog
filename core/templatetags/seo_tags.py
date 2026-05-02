import logging

from django import template
from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from django.utils.translation import get_language

from core.models import PageSEO, SiteSettings

logger = logging.getLogger(__name__)
register = template.Library()

PAGE_SEO_CACHE_TIMEOUT = 3600


def _make_absolute(url):
    if not url:
        return ""
    if str(url).startswith("http"):
        return str(url)

    site_base_url = getattr(settings, "SITE_BASE_URL", "https://kartopu.money").rstrip(
        "/"
    )
    url_str = str(url)
    if not url_str.startswith("/"):
        url_str = "/" + url_str
    return f"{site_base_url}{url_str}"


def _get_prefetched_objects(instance, relation_name):
    prefetched = getattr(instance, "_prefetched_objects_cache", {})
    return prefetched.get(relation_name)


def _get_post_tag_names(post):
    prefetched_tags = _get_prefetched_objects(post, "tags")
    if prefetched_tags is not None:
        return [tag.name for tag in prefetched_tags]
    return list(post.tags.values_list("name", flat=True))


def _get_about_page_first_image(about_page):
    prefetched_images = _get_prefetched_objects(about_page, "images")
    if prefetched_images is not None:
        return prefetched_images[0] if prefetched_images else None
    return about_page.images.only("image").order_by("order").first()


def _get_post_seo_data(seo, context):
    post = context["post"]
    seo["title"] = post.effective_meta_title
    seo["description"] = post.effective_meta_description
    if post.cover_image:
        seo["image"] = _make_absolute(post.cover_image.url)
    seo["type"] = "article"
    # Article specific meta tags
    seo["article_published_time"] = (
        post.published_at.isoformat() if post.published_at else ""
    )
    seo["article_modified_time"] = post.updated_at.isoformat()
    if post.author:
        seo["article_author"] = post.author.get_full_name() or post.author.email
    if post.category:
        seo["article_section"] = post.category.name
    tag_names = _get_post_tag_names(post)
    if tag_names:
        seo["article_tags"] = tag_names


def _get_about_page_seo_data(seo, context, site_name):
    about_page = context["about_page"]
    seo["title"] = about_page.meta_title or f"{about_page.title} | {site_name}"
    if about_page.meta_description:
        seo["description"] = about_page.meta_description

    first_image = _get_about_page_first_image(about_page)
    if first_image and first_image.image:
        seo["image"] = _make_absolute(first_image.image.url)


def _get_category_seo_data(seo, context, site_name):
    category = context["category"]
    seo["title"] = f"{category.name} | {site_name}"
    if category.description:
        seo["description"] = category.description


def _get_tag_seo_data(seo, context, site_name):
    tag = context["tag"]
    seo["title"] = f"#{tag.name} | {site_name}"
    seo["description"] = f"#{tag.name} etiketine ait blog yazıları."


def _get_archive_seo_data(seo, context, site_name):
    archive_month = context["archive_month"]
    seo["title"] = f"{archive_month} Arşivi | {site_name}"
    seo["description"] = f"{archive_month} ayına ait blog yazıları."


def _get_search_seo_data(seo, context, site_name):
    query = context["q"]
    seo["title"] = f"'{query}' Arama Sonuçları | {site_name}"
    seo["description"] = f"'{query}' için arama sonuçları."


def _fetch_page_seo_data(path):
    page_seo = (
        PageSEO.objects.filter(
            Q(path=path) | Q(path=path.rstrip("/")) | Q(path=path.rstrip("/") + "/"),
            is_active=True,
        )
        .only("title", "description", "image")
        .first()
    )

    if page_seo:
        return {
            "title": page_seo.title,
            "description": page_seo.description,
            "image_url": page_seo.image.url if page_seo.image else None,
        }
    return {}


def _update_seo_with_page_data(seo, page_seo_data):
    if page_seo_data:
        if page_seo_data.get("title"):
            seo["title"] = page_seo_data["title"]
        if page_seo_data.get("description"):
            seo["description"] = page_seo_data["description"]
        if page_seo_data.get("image_url"):
            seo["image"] = _make_absolute(page_seo_data["image_url"])


def _apply_page_seo_override(seo, request):
    try:
        path = request.path
        normalized_path = path.rstrip("/") or "/"
        cache_key = f"page_seo_{normalized_path}"

        page_seo_data = cache.get(cache_key)

        if page_seo_data is None:
            page_seo_data = _fetch_page_seo_data(path)
            cache.set(cache_key, page_seo_data, timeout=PAGE_SEO_CACHE_TIMEOUT)

        _update_seo_with_page_data(seo, page_seo_data)

    except Exception:
        logger.exception("Error generating SEO data for path: %s", request.path)


def _update_seo_from_context(seo, context, site_name):
    if context.get("post"):
        _get_post_seo_data(seo, context)
    elif context.get("about_page"):
        _get_about_page_seo_data(seo, context, site_name)
    elif context.get("category") and context.get("active_category_slug"):
        _get_category_seo_data(seo, context, site_name)
    elif context.get("tag") and context.get("active_tag_slug"):
        _get_tag_seo_data(seo, context, site_name)
    elif context.get("archive_month") and context.get("active_archive_key"):
        _get_archive_seo_data(seo, context, site_name)
    elif context.get("q"):
        _get_search_seo_data(seo, context, site_name)


@register.simple_tag(takes_context=True)
def get_seo_data(context):
    request = context.get("request")
    if not request:
        return {}

    site_settings = SiteSettings.get_settings()
    site_name = getattr(settings, "SITE_NAME", "Kartopu Money")

    # 1. Varsayılan Ayarlar
    default_title = site_settings.default_meta_title or site_name
    default_description = (
        site_settings.default_meta_description
        or "Finansal özgürlük yolculuğunuzda size eşlik ediyoruz."
    )
    default_image = (
        _make_absolute(site_settings.default_meta_image.url)
        if site_settings.default_meta_image
        else _make_absolute("/media/seo/og_twit_card.jpeg")
    )

    seo = {
        "title": default_title,
        "description": default_description,
        "image": default_image,
        "canonical_url": request.build_absolute_uri(request.path),
        "type": "website",
        "site_name": site_name,
        "locale": get_language() or "tr_TR",
        "twitter_card": "summary_large_image",
        "twitter_site": "@KartopuMoney",  # Sabit veya settings'den alınabilir
    }

    _update_seo_from_context(seo, context, site_name)
    _apply_page_seo_override(seo, request)

    return seo
