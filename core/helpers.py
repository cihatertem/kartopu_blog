import ipaddress
import math
from random import random

from django.conf import settings

from core.decorators import log_exceptions

CAPTCHA_SESSION_KEY = "contact_captcha_answer"


def normalize_search_query(q: str) -> list[str]:
    """
    Arama terimini tokenize eder.
    Sadece anlamlı kelimeleri bırakır.
    """
    tokens = [token for token in q.lower().split() if len(token) >= 3]
    return tokens


def get_client_ip(request) -> str | None:
    remote = request.META.get("REMOTE_ADDR")
    if not remote:
        return None

    ra = ipaddress.ip_address(remote)

    trusted_nets = getattr(settings, "TRUSTED_PROXY_NETS", None) or []

    # Sadece trusted proxy'den geliyorsa XFF'e güven
    if trusted_nets and any(ra in net for net in trusted_nets):
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            return xff.split(",")[0].strip()

    return remote


def client_ip_key(group, request):
    # request None olmasın, ip yoksa sabit değer ver
    return get_client_ip(request) or "unknown"


@log_exceptions(
    default=None,
    exception_types=(TypeError, ValueError),
    message="Error parsing integer",
)
def _parse_int(value: str | None) -> int | None:
    return int(value) if value not in (None, "") else None


def captcha_is_valid(request) -> bool:
    """
    Returns True if posted captcha matches expected answer in session.
    Missing/invalid values return False.
    """
    expected = _parse_int(request.session.get(CAPTCHA_SESSION_KEY))
    got = _parse_int(request.POST.get("captcha"))

    return expected is not None and got is not None and got == expected


def _generate_captcha(request):
    num_one = math.floor(random() * 10) + 1
    num_two = math.floor(random() * 10) + 1
    request.session[CAPTCHA_SESSION_KEY] = num_one + num_two
    return num_one, num_two
