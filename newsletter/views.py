from django.conf import settings
from django.contrib import messages
from django.core import signing
from django.shortcuts import redirect, render
from django.utils import timezone

from .forms import NewsletterEmailForm
from .models import Subscriber, SubscriberStatus
from .services import send_subscribe_confirmation, send_unsubscribe_confirmation
from .tokens import parse_token


def subscribe_request(request):
    if request.method != "POST":
        return redirect("/")

    form = NewsletterEmailForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Lütfen geçerli bir e-posta adresi girin.")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    if bool(form.cleaned_data.get("name")):
        messages.success(
            request,
            "Aboneliğiniz alınmıştır. Lütfen gelen kutunuzu kontrol edin.",
        )
        return redirect(request.META.get("HTTP_REFERER", "/"))

    email = form.cleaned_data["email"].lower()
    subscriber, created = Subscriber.objects.get_or_create(email=email)

    if subscriber.status == SubscriberStatus.ACTIVE:
        messages.info(request, "Bu adres zaten aktif bir abonelikte.")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    if created or subscriber.status != SubscriberStatus.PENDING:
        subscriber.status = SubscriberStatus.PENDING
        subscriber.subscribed_at = timezone.now()
        subscriber.unsubscribed_at = None
        subscriber.save(update_fields=["status", "subscribed_at", "unsubscribed_at"])

    send_subscribe_confirmation(email)
    messages.success(
        request,
        "Aboneliğinizi onaylamak için e-posta gönderildi."
        " Lütfen gelen kutunuzu kontrol edin.",
    )
    return redirect(request.META.get("HTTP_REFERER", "/"))


def unsubscribe_request(request):
    if request.method != "POST":
        return redirect("/")

    form = NewsletterEmailForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Lütfen geçerli bir e-posta adresi girin.")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    email = form.cleaned_data["email"].lower()
    subscriber = Subscriber.objects.filter(email=email).first()

    if subscriber:
        send_unsubscribe_confirmation(email)

    messages.success(
        request,
        "Eğer bu e-posta kayıtlıysa iptal onayı gönderildi."
        " Lütfen gelen kutunuzu kontrol edin.",
    )
    return redirect(request.META.get("HTTP_REFERER", "/"))


def confirm_subscription(request, token: str):
    max_age = getattr(settings, "NEWSLETTER_TOKEN_MAX_AGE", 60 * 60 * 24 * 7)
    try:
        payload = parse_token(token, max_age=max_age)
    except signing.SignatureExpired:
        return render(
            request,
            "newsletter/confirm_result.html",
            {
                "title": "Link Süresi Doldu",
                "message": "Onay linkinin süresi dolmuş. Lütfen yeniden deneyin.",
            },
            status=400,
        )
    except signing.BadSignature:
        return render(
            request,
            "newsletter/confirm_result.html",
            {
                "title": "Geçersiz Link",
                "message": "Onay linki geçersiz. Lütfen yeniden deneyin.",
            },
            status=400,
        )

    email = payload.get("email")
    action = payload.get("action")

    if not email or action not in {"subscribe", "unsubscribe"}:
        return render(
            request,
            "newsletter/confirm_result.html",
            {
                "title": "Geçersiz Talep",
                "message": "Talep bilgileri eksik veya hatalı.",
            },
            status=400,
        )

    subscriber, _ = Subscriber.objects.get_or_create(email=email)

    if action == "subscribe":
        subscriber.activate()
        title = "Abonelik Onaylandı"
        message = "Newsletter aboneliğiniz başarıyla aktif edildi."
    else:
        subscriber.unsubscribe()
        title = "Abonelik İptal Edildi"
        message = "Newsletter aboneliğiniz iptal edildi."

    return render(
        request,
        "newsletter/confirm_result.html",
        {
            "title": title,
            "message": message,
        },
    )
