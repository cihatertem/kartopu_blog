"""Cache key helpers used by Django cache backends."""

from django.conf import settings
from django.utils.crypto import salted_hmac

CACHE_KEY_HASH_SALT = "kartopu_blog.cache_key"


def secure_cache_key(key: str, key_prefix: str, version: int) -> str:
    """Return a stable HMAC cache key that does not expose raw identifiers.

    django-ratelimit keys can include request-derived identifiers such as IP
    addresses. Hashing the final logical key prevents those identifiers from
    being stored in plaintext by persistent/shared cache backends while keeping
    cache lookups deterministic across workers.
    """

    logical_key = f"{key_prefix}:{version}:{key}"
    digest = salted_hmac(
        CACHE_KEY_HASH_SALT,
        logical_key,
        secret=settings.SECRET_KEY,
        algorithm="sha256",
    ).hexdigest()
    return f"{key_prefix}:{version}:{digest}"
