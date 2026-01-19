from __future__ import annotations

from urllib.parse import urlparse

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import iri_to_uri

from django.contrib.sites.models import Site

from .models import Announcement, AnnouncementStatus, Subscriber, SubscriberStatus
from .tokens import make_token


def get_site_base_url() -> str:
    base_url = getattr(settings, "SITE_BASE_URL", "").strip()
    if base_url:
        return base_url.rstrip("/")
    current_site = Site.objects.get_current()
    protocol = "https" if not settings.DEBUG else "http"
    return f"{protocol}://{current_site.domain}".rstrip("/")


def build_absolute_uri(path: str) -> str:
    parsed = urlparse(path)
    if parsed.scheme and parsed.netloc:
        return path
    if path.startswith("//"):
        base_url = get_site_base_url()
        base_scheme = urlparse(base_url).scheme or "https"
        return f"{base_scheme}:{path}"
    base_url = get_site_base_url()
    return f"{base_url}/{path.lstrip('/')}"


def build_unsubscribe_url(email: str) -> str:
    token = make_token(email, "unsubscribe")
    path = reverse("newsletter:confirm", kwargs={"token": token})
    return build_absolute_uri(path)


def build_subscribe_confirm_url(email: str) -> str:
    token = make_token(email, "subscribe")
    path = reverse("newsletter:confirm", kwargs={"token": token})
    return build_absolute_uri(path)


def send_templated_email(
    *,
    subject: str,
    to_email: str,
    template_prefix: str,
    context: dict,
) -> None:
    text_body = render_to_string(f"newsletter/email/{template_prefix}.txt", context)
    html_body = render_to_string(f"newsletter/email/{template_prefix}.html", context)

    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email],
    )
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=False)


def send_subscribe_confirmation(email: str) -> None:
    confirm_url = build_subscribe_confirm_url(email)
    unsubscribe_url = build_unsubscribe_url(email)
    context = {
        "confirm_url": iri_to_uri(confirm_url),
        "unsubscribe_url": iri_to_uri(unsubscribe_url),
        "site_name": getattr(settings, "SITE_NAME", "Kartopu Blog"),
    }
    send_templated_email(
        subject="Newsletter aboneliğinizi onaylayın",
        to_email=email,
        template_prefix="subscribe_confirm",
        context=context,
    )


def send_unsubscribe_confirmation(email: str) -> None:
    unsubscribe_url = build_unsubscribe_url(email)
    context = {
        "unsubscribe_url": iri_to_uri(unsubscribe_url),
        "site_name": getattr(settings, "SITE_NAME", "Kartopu Blog"),
    }
    send_templated_email(
        subject="Newsletter abonelik iptal isteği",
        to_email=email,
        template_prefix="unsubscribe_confirm",
        context=context,
    )


def send_post_published_email(post) -> None:
    subscribers = Subscriber.objects.filter(status=SubscriberStatus.ACTIVE)
    post_url = build_absolute_uri(post.get_absolute_url())
    cover_image_url = None
    if getattr(post, "cover_image", None):
        cover_image_url = build_absolute_uri(post.cover_1200.url)
    for subscriber in subscribers:
        unsubscribe_url = build_unsubscribe_url(subscriber.email)
        context = {
            "post": post,
            "cover_image_url": iri_to_uri(cover_image_url) if cover_image_url else None,
            "post_url": iri_to_uri(post_url),
            "unsubscribe_url": iri_to_uri(unsubscribe_url),
            "site_name": getattr(settings, "SITE_NAME", "Kartopu Blog"),
        }
        send_templated_email(
            subject=f"Yeni yazı yayında: {post.title}",
            to_email=subscriber.email,
            template_prefix="new_post",
            context=context,
        )


def send_announcement(announcement: Announcement) -> int:
    subscribers = Subscriber.objects.filter(status=SubscriberStatus.ACTIVE)
    sent_count = 0
    for subscriber in subscribers:
        unsubscribe_url = build_unsubscribe_url(subscriber.email)
        context = {
            "announcement": announcement,
            "unsubscribe_url": iri_to_uri(unsubscribe_url),
            "site_name": getattr(settings, "SITE_NAME", "Kartopu Blog"),
        }
        send_templated_email(
            subject=announcement.subject,
            to_email=subscriber.email,
            template_prefix="announcement",
            context=context,
        )
        sent_count += 1
    announcement.status = AnnouncementStatus.SENT
    announcement.sent_at = timezone.now()
    announcement.save(update_fields=["status", "sent_at"])
    return sent_count
