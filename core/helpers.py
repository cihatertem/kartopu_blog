import ipaddress
import secrets

from django.conf import settings
from django.utils.http import url_has_allowed_host_and_scheme

CAPTCHA_SESSION_KEY = "contact_captcha_answer"


def normalize_search_query(q: str) -> str:
    """
    Arama terimini tokenize eder.
    Websearch mantığına uygun olacak şekilde döndürür.
    """
    return q.strip()


def get_client_ip(request) -> str | None:
    remote = request.META.get("REMOTE_ADDR")
    if not remote:
        return None

    try:
        ra = ipaddress.ip_address(remote)
    except ValueError:
        return remote

    trusted_nets = getattr(settings, "TRUSTED_PROXY_NETS", None) or []

    # Sadece trusted proxy'den geliyorsa XFF'e güven
    if trusted_nets and any(ra in net for net in trusted_nets):
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            parsed_xff = xff.split(",")[0].strip()
            if parsed_xff:
                return parsed_xff

    return remote


def client_ip_key(group, request):
    # request None olmasın, ip yoksa sabit değer ver
    return get_client_ip(request) or "unknown"


def captcha_is_valid(request) -> bool:
    """
    Returns True if posted captcha matches expected answer in session.
    Missing/invalid values return False.
    """
    expected = request.session.get(CAPTCHA_SESSION_KEY)
    got = request.POST.get("captcha")

    if not expected or not got:
        return False

    return str(got).strip().upper() == str(expected).upper()


def _generate_captcha(request):
    import base64
    import io
    import os
    import string

    from django.conf import settings
    from PIL import Image, ImageDraw, ImageFont

    FONT_PATH = os.path.join(
        settings.BASE_DIR, "static", "fonts", "UbuntuMono-Regular.ttf"
    )

    alphabet = string.ascii_uppercase + string.digits
    captcha_text = "".join(secrets.choice(alphabet) for _ in range(5))

    img = Image.new("RGB", (100, 40), color=(240, 240, 240))
    draw = ImageDraw.Draw(img)
    try:
        font_size = 20
        font = ImageFont.truetype(FONT_PATH, font_size)
    except IOError:
        # Font dosyası bulunamazsa fallback olarak varsayılanı kullanır
        font = ImageFont.load_default()

    for _ in range(7):
        draw.line(
            [
                (secrets.randbelow(100), secrets.randbelow(40)),
                (secrets.randbelow(100), secrets.randbelow(40)),
            ],
            fill=(150, 150, 150),
            width=2,
        )

    draw.text((25, 10), captcha_text, fill=(50, 50, 50), font=font)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    request.session[CAPTCHA_SESSION_KEY] = captcha_text
    return b64


def get_safe_referer(request, default: str = "/") -> str:
    """
    HTTP_REFERER header'ını güvenli bir şekilde döner.
    Eğer header geçersizse veya farklı bir host'a yönlendiriyorsa default değeri döner.
    """
    referer = request.META.get("HTTP_REFERER")
    if referer and url_has_allowed_host_and_scheme(
        url=referer,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return referer
    return default
