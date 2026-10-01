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