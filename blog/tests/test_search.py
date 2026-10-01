import unicodedata

from django.db import connection
from django.db.models import Value
from django.test import SimpleTestCase

from blog.models import BlogPost
from blog.search import (
    DEFAULT_SEARCH_MODE,
    SEARCH_MODES,
    TR_ASCII_FROM,
    TR_ASCII_TO,
    build_search_query,
    normalize_search_expression,
    normalize_search_mode,
    normalize_search_text,
)


class SearchNormalizationTests(SimpleTestCase):
    def test_modes_are_allowlisted(self) -> None:
        self.assertEqual(SEARCH_MODES["exact"], ("search_vector_exact", "simple"))
        self.assertEqual(SEARCH_MODES["stemmed"], ("search_vector", "turkish"))
        for mode in (None, "", "invalid", "TURKISH", "title"):
            self.assertEqual(normalize_search_mode(mode), DEFAULT_SEARCH_MODE)
        self.assertEqual(normalize_search_mode("stemmed"), "stemmed")
        self.assertEqual(normalize_search_mode("exact"), "exact")

    def test_search_normalization_bridges_turkish_and_ascii(self) -> None:
        pairs = [
            ("yünsa", "yunsa"),
            ("YÜNSA", "yunsa"),
            ("YUNSA", "yunsa"),
            ("yunsa", "yunsa"),
            ("migros", "migros"),
            ("Migros", "migros"),
            ("MIGROS", "migros"),
            ("mıgros", "migros"),
            ("sirket", "sirket"),
            ("şirket", "sirket"),
            ("ŞİRKET", "sirket"),
            ("ışık", "isik"),
            ("IŞIK", "isik"),
            ("isik", "isik"),
        ]
        for query, expected in pairs:
            with self.subTest(query=query):
                self.assertEqual(normalize_search_text(query), expected)

    def test_build_search_query_creates_clean_websearch_query(self) -> None:
        query = build_search_query("yunsa", config="simple")
        query_str = str(query)
        self.assertIn("yunsa", query_str)

    def test_turkish_case_and_canonical_normalization(self) -> None:
        for source, expected in (
            (" MİGROS ", "migros"), ("Migros", "migros"),
            ("MIGROS", "migros"), ("mıgros", "migros"),
            ("IŞIK", "isik"), ("ışık", "isik"), ("isik", "isik"),
            ("YÜNSA", "yunsa"), ("yünsa", "yunsa"), ("yunsa", "yunsa"),
            ("İ i I ı", "i i i i"), ("Ü U", "u u"),
        ):
            for form in ("NFC", "NFD"):
                with self.subTest(source=source, form=form):
                    self.assertEqual(
                        normalize_search_text(unicodedata.normalize(form, source)), expected
                    )

    def test_websearch_punctuation_is_preserved(self) -> None:
        self.assertEqual(
            normalize_search_text('"YÜNSA HİSSE" OR MİGROS -VERGİ'),
            '"yunsa hisse" or migros -vergi',
        )

    def test_sql_expression_uses_bound_parameters(self) -> None:
        source = "İ' OR I"
        expression = normalize_search_expression(Value(source))
        compiler = BlogPost.objects.all().query.get_compiler(connection=connection)
        sql, params = compiler.compile(expression)
        self.assertEqual(sql, "LOWER(translate(normalize(%s), %s, %s))")
        self.assertEqual(tuple(params), (source, TR_ASCII_FROM, TR_ASCII_TO))