import unicodedata

from django.db import connection
from django.db.models import Value
from django.test import SimpleTestCase

from blog.models import BlogPost
from blog.search import (
    DEFAULT_SEARCH_MODE,
    SEARCH_MODES,
    build_search_query,
    get_search_variants,
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

    def test_search_variants_bridge_turkish_and_ascii(self) -> None:
        cases = [
            ("yünsa", ["yünsa", "yunsa"]),
            ("yunsa", ["yunsa", "yünsa"]),
            ("migros", ["migros", "mıgros"]),
            ("mıgros", ["mıgros", "migros"]),
            ("sirket", ["sirket", "şirket"]),
            ("şirket", ["şirket", "sirket"]),
            ("ışık", ["ışık", "isik"]),
        ]
        for query, expected_subsets in cases:
            with self.subTest(query=query):
                variants = get_search_variants(query)
                for item in expected_subsets:
                    self.assertIn(item, variants)

    def test_build_search_query_combines_variants_with_websearch(self) -> None:
        query = build_search_query("yunsa", config="simple")
        # In Django, combined queries contain SearchQuery items
        query_str = str(query)
        self.assertIn("yunsa", query_str)
        self.assertIn("yünsa", query_str)

    def test_turkish_case_and_canonical_normalization(self) -> None:
        for source, expected in (
            (" MİGROS ", "migros"), ("Migros", "migros"),
            ("MIGROS", "mıgros"), ("IŞIK", "ışık"), ("YÜNSA", "yünsa"),
            ("İ i I ı", "i i ı ı"), ("Ü U", "ü u"),
        ):
            for form in ("NFC", "NFD"):
                with self.subTest(source=source, form=form):
                    self.assertEqual(
                        normalize_search_text(unicodedata.normalize(form, source)), expected
                    )

    def test_websearch_punctuation_is_preserved(self) -> None:
        self.assertEqual(
            normalize_search_text('"YÜNSA HİSSE" OR MİGROS -VERGİ'),
            '"yünsa hisse" or migros -vergi',
        )

    def test_sql_expression_uses_bound_parameters(self) -> None:
        source = "İ' OR I"
        expression = normalize_search_expression(Value(source))
        compiler = BlogPost.objects.all().query.get_compiler(connection=connection)
        sql, params = compiler.compile(expression)
        self.assertEqual(sql, "LOWER(translate(normalize(%s), %s, %s))")
        self.assertEqual(tuple(params), (source, "Iİ", "ıi"))