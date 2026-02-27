from django import template
from django.conf import settings
from django.db.models import Q
from django.utils.translation import get_language

from core.models import PageSEO, SiteSettings

register = template.Library()


@register.simple_tag(takes_context=True)
def get_seo_data(context):
    request = context.get("request")
    if not request:
        return {}

    site_settings = SiteSettings.get_settings()
    site_base_url = getattr(settings, "SITE_BASE_URL", "https://kartopu.money").rstrip(
        "/"
    )
    site_name = getattr(settings, "SITE_NAME", "Kartopu Money")

    def make_absolute(url):
        if not url:
            return ""
        if str(url).startswith("http"):
            return str(url)
        # Ensure url starts with /
        url_str = str(url)
        if not url_str.startswith("/"):
            url_str = "/" + url_str
        return f"{site_base_url}{url_str}"

    # 1. Varsayılan Ayarlar
    default_title = site_settings.default_meta_title or site_name
    default_description = (
        site_settings.default_meta_description
        or "Finansal özgürlük yolculuğunuzda size eşlik ediyoruz."
    )
    default_image = (
        make_absolute(site_settings.default_meta_image.url)
        if site_settings.default_meta_image
        else make_absolute("/media/seo/og_twit_card.jpeg")
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

    # Blog Post
    if context.get("post"):
        post = context["post"]
        seo["title"] = post.effective_meta_title
        seo["description"] = post.effective_meta_description
        if post.cover_image:
            seo["image"] = make_absolute(post.cover_image.url)
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
        if post.tags.exists():
            seo["article_tags"] = [tag.name for tag in post.tags.all()]

    # Hakkımda Sayfası
    elif context.get("about_page"):
        about_page = context["about_page"]
        seo["title"] = about_page.meta_title or f"{about_page.title} | {site_name}"
        if about_page.meta_description:
            seo["description"] = about_page.meta_description

        # İlk görseli kullan
        first_image = about_page.images.order_by("order").first()
        if first_image and first_image.image:
            seo["image"] = make_absolute(first_image.image.url)

    # Kategori Detay Sayfası
    elif context.get("category") and context.get("active_category_slug"):
        category = context["category"]
        seo["title"] = f"{category.name} | {site_name}"
        if category.description:
            seo["description"] = category.description

    # Etiket Detay Sayfası
    elif context.get("tag") and context.get("active_tag_slug"):
        tag = context["tag"]
        seo["title"] = f"#{tag.name} | {site_name}"
        seo["description"] = f"#{tag.name} etiketine ait blog yazıları."

    # Arşiv Sayfası
    elif context.get("archive_month") and context.get("active_archive_key"):
        archive_month = context["archive_month"]
        seo["title"] = f"{archive_month} Arşivi | {site_name}"
        seo["description"] = f"{archive_month} ayına ait blog yazıları."

    # Arama Sonuçları
    elif context.get("q"):
        query = context["q"]
        seo["title"] = f"'{query}' Arama Sonuçları | {site_name}"
        seo["description"] = f"'{query}' için arama sonuçları."

    try:
        path = request.path
        page_seo = PageSEO.objects.filter(
            Q(path=path) | Q(path=path.rstrip("/")) | Q(path=path.rstrip("/") + "/"),
            is_active=True,
        ).first()

        if page_seo:
            if page_seo.title:
                seo["title"] = page_seo.title
            if page_seo.description:
                seo["description"] = page_seo.description
            if page_seo.image:
                seo["image"] = make_absolute(page_seo.image.url)

    except Exception:
        pass

    return seo
