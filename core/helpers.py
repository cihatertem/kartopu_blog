import ipaddress

from django.conf import settings


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
