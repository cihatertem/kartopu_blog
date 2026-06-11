"""
Reaction kaynaklı popülerlik yeniden hesaplaması için hafif bir debounce/
kuyruk katmanı.

Neden: `BlogPostReaction` save/delete sinyali yüksek frekanslıdır. Her olayda
`recalculate_popularity_score` (korelasyonlu Subquery'li UPDATE) + nav cache
invalidation çalıştırmak, t3.micro üzerinde gereksiz DB yazma yükü ve nav cache
thrash/stampede üretir. Bunun yerine ilgili `post_id` "kirli" bir kümeye yazılır
ve periyodik bir komut (`recalculate_popularity_scores --pending`) tüm bekleyen
yazıları **tek bir UPDATE** ile birleştirip işler, nav cache'i de **bir kez**
geçersiz kılar.

Backend-agnostik: django-redis mevcutsa atomik native set işlemleri (SADD /
SMEMBERS+DELETE) kullanılır; aksi halde (örn. testlerdeki LocMemCache) standart
cache get/set ile küme tutulur. Native set yaklaşımı Redis'te (≤100MB,
allkeys-lru) tek küçük anahtar tükettiği için bellek dostudur.
"""

from django.core.cache import cache

from blog.cache_keys import BLOG_POPULARITY_DIRTY_KEY


def _get_redis_client():
    """Mevcutsa ham Redis bağlantısını döndürür, yoksa None."""
    try:
        from django_redis import get_redis_connection

        return get_redis_connection("default")
    except Exception:
        # django-redis yok ya da backend Redis değil (örn. LocMemCache).
        return None


def mark_popularity_dirty(post_id) -> None:
    """Bir yazıyı popülerlik yeniden hesaplaması için bekleyenler kümesine ekler."""
    if post_id is None:
        return

    # BlogPost PK'si UUID; backend-agnostik depolama için string olarak tutulur.
    post_id = str(post_id)
    client = _get_redis_client()
    if client is not None:
        # Atomik; aynı post için yarış durumunda mükerrer kayıt oluşmaz.
        client.sadd(BLOG_POPULARITY_DIRTY_KEY, post_id)
        return

    pending = set(cache.get(BLOG_POPULARITY_DIRTY_KEY) or ())
    pending.add(post_id)
    # TTL=None: periyodik komut işleyene kadar kalıcı kalsın.
    cache.set(BLOG_POPULARITY_DIRTY_KEY, pending, None)


def drain_popularity_dirty() -> set[str]:
    """
    Bekleyen yazı id'lerini döndürür ve kümeyi temizler.

    Redis tarafında SMEMBERS + DELETE tek pipeline'da çalıştırılarak, drain ile
    yeni eklemeler arasındaki yarış penceresi en aza indirilir.
    """
    client = _get_redis_client()
    if client is not None:
        pipe = client.pipeline()
        pipe.smembers(BLOG_POPULARITY_DIRTY_KEY)
        pipe.delete(BLOG_POPULARITY_DIRTY_KEY)
        members, _ = pipe.execute()
        # Redis bytes döndürür; tek tip string'e normalize edilir.
        return {
            member.decode() if isinstance(member, bytes) else str(member)
            for member in members
        }

    pending = cache.get(BLOG_POPULARITY_DIRTY_KEY) or ()
    cache.delete(BLOG_POPULARITY_DIRTY_KEY)
    return {str(post_id) for post_id in pending}
