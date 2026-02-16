from __future__ import annotations

from urllib.parse import urlparse

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import iri_to_uri

from core.decorators import log_exceptions
from core.imagekit import safe_file_url

from .models import (
    Announcement,
    AnnouncementStatus,
    DirectEmail,
    EmailQueue,
    Subscriber,
    SubscriberStatus,
)
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


def prepare_templated_email(
    *,
    subject: str,
    to_email: str,
    template_prefix: str,
    context: dict,
    from_name: str = "Kartopu.Money Blog",
) -> dict:
    text_body = render_to_string(f"newsletter/email/{template_prefix}.txt", context)
    html_body = render_to_string(f"newsletter/email/{template_prefix}.html", context)

    full_from = f'"{from_name}" <{settings.DEFAULT_FROM_EMAIL}>'

    return {
        "subject": subject,
        "from_email": full_from,
        "to_email": to_email,
        "text_body": text_body,
        "html_body": html_body,
    }


@log_exceptions(message="Error sending templated email")
def send_templated_email(**kwargs) -> None:
    data = prepare_templated_email(**kwargs)
    message = EmailMultiAlternatives(
        subject=data["subject"],
        body=data["text_body"],
        from_email=data["from_email"],
        to=[data["to_email"]],
    )
    message.attach_alternative(data["html_body"], "text/html")
    message.send(fail_silently=False)


@log_exceptions(message="Error sending subscribe confirmation")
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


@log_exceptions(message="Error sending unsubscribe confirmation")
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


@log_exceptions(message="Error queuing post published email")
def send_post_published_email(post) -> None:
    subscribers = Subscriber.objects.filter(status=SubscriberStatus.ACTIVE)
    post_url = build_absolute_uri(post.get_absolute_url())
    cover_image_url = None
    cover_field = getattr(post, "cover_image", None)
    if cover_field:
        cover_rendition = getattr(post, "cover_rendition", None)
        cover_url = (
            cover_rendition["src"] if cover_rendition else safe_file_url(cover_field)
        )
        if cover_url:
            cover_image_url = build_absolute_uri(cover_url)

    queue_items = []
    for subscriber in subscribers:
        unsubscribe_url = build_unsubscribe_url(subscriber.email)
        context = {
            "post": post,
            "cover_image_url": iri_to_uri(cover_image_url) if cover_image_url else None,
            "post_url": iri_to_uri(post_url),
            "unsubscribe_url": iri_to_uri(unsubscribe_url),
            "site_name": getattr(settings, "SITE_NAME", "Kartopu Blog"),
        }
        email_data = prepare_templated_email(
            subject=f"Yeni yazı yayında: {post.title}",
            to_email=subscriber.email,
            template_prefix="new_post",
            context=context,
        )
        queue_items.append(EmailQueue(**email_data))

    if queue_items:
        EmailQueue.objects.bulk_create(queue_items)


@log_exceptions(message="Error queuing announcement", default=0)
def send_announcement(announcement: Announcement) -> int:
    subscribers = Subscriber.objects.filter(status=SubscriberStatus.ACTIVE)
    queue_items = []
    for subscriber in subscribers:
        unsubscribe_url = build_unsubscribe_url(subscriber.email)
        context = {
            "announcement": announcement,
            "unsubscribe_url": iri_to_uri(unsubscribe_url),
            "site_name": getattr(settings, "SITE_NAME", "Kartopu Blog"),
        }
        email_data = prepare_templated_email(
            subject=announcement.subject,
            to_email=subscriber.email,
            template_prefix="announcement",
            context=context,
        )
        queue_items.append(EmailQueue(**email_data))

    sent_count = len(queue_items)
    if queue_items:
        EmailQueue.objects.bulk_create(queue_items)

    announcement.status = AnnouncementStatus.SENT
    announcement.sent_at = timezone.now()
    announcement.save(update_fields=["status", "sent_at"])
    return sent_count


@log_exceptions(message="Error sending direct email", default=False)
def send_direct_email(direct_email: DirectEmail) -> bool:
    from core.markdown import render_markdown

    html_body = render_markdown(direct_email.body)
    text_body = direct_email.body  # Markdown text is readable enough for fallback

    # Use a generic base template or just the rendered markdown
    # Here we wrap it in a simple HTML structure if needed, or just send the rendered markdown.
    # The existing templated emails use specific templates.
    # For simplicity, we just send the rendered markdown as html_body.

    from_email = '"Kartopu Money" <info@kartopu.money>'

    message = EmailMultiAlternatives(
        subject=direct_email.subject,
        body=text_body,
        from_email=from_email,
        to=[direct_email.to_email],
    )
    message.attach_alternative(html_body, "text/html")

    for attachment in direct_email.attachments.all():  # pyright: ignore[reportAttributeAccessIssue]
        # Open the file and read its content
        with attachment.file.open("rb") as f:
            content = f.read()
            message.attach(attachment.file.name.split("/")[-1], content)

    message.send(fail_silently=False)

    direct_email.sent_at = timezone.now()
    direct_email.save(update_fields=["sent_at"])
    return True
