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



TR_ASCII_FROM = "çğıöşüÇĞIİÖŞÜ"
TR_ASCII_TO = "cgiosuCGIIOSU"

TR_TO_ASCII = str.maketrans({
    "ç": "c", "Ç": "c",
    "ğ": "g", "Ğ": "g",
    "ı": "i", "I": "i",
    "İ": "i", "i": "i",
    "ö": "o", "Ö": "o",
    "ş": "s", "Ş": "s",
    "ü": "u", "Ü": "u",
})


def normalize_search_text(text: str) -> str:
    return unicodedata.normalize("NFC", text).translate(TR_TO_ASCII).lower().strip()


def normalize_search_expression(expression: Expression | str) -> Expression:
    return Lower(
        Func(
            Func(expression, function="normalize", output_field=TextField()),
            Value(TR_ASCII_FROM),
            Value(TR_ASCII_TO),
            function="translate",
            output_field=TextField(),
        )
    )


def to_ascii(text: str) -> str:
    return text.translate(TR_TO_ASCII)


def get_search_variants(normalized_q: str) -> list[str]:
    if not normalized_q:
        return []
    return [normalized_q]


def build_search_query(normalized_q: str, *, config: str = "simple"):
    """Build a SearchQuery object for full-text search."""
    from django.contrib.postgres.search import SearchQuery

    return SearchQuery(normalized_q, search_type="websearch", config=config)