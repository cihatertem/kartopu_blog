import unicodedata

from django.db.models import Expression, Func, TextField, Value
from django.db.models.functions import Lower


SEARCH_MODES = {
    "exact": ("search_vector_exact", "simple"),
    "stemmed": ("search_vector", "turkish"),
}
DEFAULT_SEARCH_MODE = "exact"


def normalize_search_mode(mode: str | None) -> str:
    return mode if mode in SEARCH_MODES else DEFAULT_SEARCH_MODE


def normalize_search_text(text: str) -> str:
    return unicodedata.normalize("NFC", text).translate(
        str.maketrans({"I": "ı", "İ": "i"})
    ).lower().strip()


def normalize_search_expression(expression: Expression | str) -> Expression:
    return Lower(
        Func(
            Func(expression, function="normalize", output_field=TextField()),
            Value("Iİ"),
            Value("ıi"),
            function="translate",
            output_field=TextField(),
        )
    )


TR_TO_ASCII = str.maketrans({
    "ç": "c",
    "ğ": "g",
    "ı": "i",
    "ö": "o",
    "ş": "s",
    "ü": "u",
})


def to_ascii(text: str) -> str:
    return text.translate(TR_TO_ASCII)


def get_search_variants(normalized_q: str) -> list[str]:
    """Generate search variants to bridge Turkish and ASCII input seamlessly.

    For example:
    - 'yunsa' <-> 'yünsa'
    - 'mıgros' <-> 'migros'
    - 'sirket' <-> 'şirket'
    - 'isik' <-> 'ışık'
    """
    if not normalized_q:
        return []

    variants: list[str] = [normalized_q]

    # 1. ASCII version (e.g. 'yünsa' -> 'yunsa', 'mıgros' -> 'migros', 'şirket' -> 'sirket')
    ascii_v = to_ascii(normalized_q)
    if ascii_v not in variants:
        variants.append(ascii_v)

    # 2. Turkish diacritic candidate with all replacements (e.g. 'isik' -> 'ışık', 'tupras' -> 'tüpraş')
    tr_candidate = (
        normalized_q.replace("u", "ü")
        .replace("o", "ö")
        .replace("c", "ç")
        .replace("g", "ğ")
        .replace("s", "ş")
        .replace("i", "ı")
    )
    if tr_candidate not in variants:
        variants.append(tr_candidate)

    # 3. Handle 'i' remaining 'i' with other consonants converted (e.g. 'sirket' -> 'şirket')
    tr_with_i = (
        normalized_q.replace("u", "ü")
        .replace("o", "ö")
        .replace("c", "ç")
        .replace("g", "ğ")
        .replace("s", "ş")
    )
    if tr_with_i not in variants:
        variants.append(tr_with_i)

    # 4. Handle vowels only converted (e.g. 'yunsa' -> 'yünsa')
    tr_vowels = normalized_q.replace("u", "ü").replace("o", "ö")
    if tr_vowels not in variants:
        variants.append(tr_vowels)

    # 5. Handle i <-> ı differences (e.g. 'mıgros' <-> 'migros')
    if "ı" in normalized_q:
        dotted = normalized_q.replace("ı", "i")
        if dotted not in variants:
            variants.append(dotted)
    if "i" in normalized_q:
        dotless = normalized_q.replace("i", "ı")
        if dotless not in variants:
            variants.append(dotless)

    return variants


def build_search_query(normalized_q: str, *, config: str = "simple"):
    """Build a SearchQuery object with Turkish/ASCII variants combined via OR."""
    from django.contrib.postgres.search import SearchQuery

    variants = get_search_variants(normalized_q)
    if not variants:
        return SearchQuery(normalized_q, search_type="websearch", config=config)
    query = SearchQuery(variants[0], search_type="websearch", config=config)
    for variant in variants[1:]:
        query |= SearchQuery(variant, search_type="websearch", config=config)
    return query