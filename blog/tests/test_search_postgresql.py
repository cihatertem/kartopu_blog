from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from io import StringIO
import unicodedata
from unittest import skipUnless
from unittest.mock import patch
from uuid import UUID

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.cache.utils import make_template_fragment_key
from django.core.management import call_command
from django.db import connection
from django.db.models import QuerySet, Value
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from blog.cache_keys import SEARCH_CACHE_VERSION_KEY
from blog.models import BlogPost
from blog.search import normalize_search_expression, normalize_search_text
from blog.signals import update_search_vector
from blog.views import POST_PAGE_SIZE, _perform_database_search
from core.services.blog import published_posts_queryset


@skipUnless(connection.vendor == "postgresql", "Requires real PostgreSQL full-text search")
class PostgreSQLSearchTests(TestCase):
    full_title = "Migros 2026 3 Aylık Finansal Sonuçları"
    default_configs = ("english", "turkish", "simple")
    modes = ("exact", "stemmed")

    @classmethod
    def setUpTestData(cls) -> None:
        cls.author = get_user_model().objects.create_user(email="fts@example.invalid")
        cls.published_at = timezone.now() - timedelta(days=1)
        cls.title_post, cls.content_post, cls.unrelated_post = BlogPost.objects.bulk_create(
            [
                BlogPost(
                    author=cls.author,
                    title=title,
                    content=content,
                    excerpt="",
                    slug=slug,
                    status=BlogPost.Status.PUBLISHED,
                    published_at=cls.published_at,
                )
                for title, content, slug in (
                    (cls.full_title, "", "fts-title"),
                    ("Piyasa Notları", cls.full_title, "fts-content"),
                    ("Hava Durumu", "Güneşli hava", "fts-unrelated"),
                )
            ]
        )
        # Bulk insertion avoids unrelated publication notifications, not real FTS.
        for post in (cls.title_post, cls.content_post, cls.unrelated_post):
            update_search_vector(post)

    def setUp(self) -> None:
        self.factory = RequestFactory()
        cache.clear()
        self.addCleanup(cache.clear)

    @contextmanager
    def _default_config(self, config: str) -> Iterator[None]:
        with connection.cursor() as cursor:
            cursor.execute("SHOW default_text_search_config")
            original = cursor.fetchone()[0]
            cursor.execute(
                "SELECT set_config('default_text_search_config', %s, true)", [config]
            )
            try:
                yield
            finally:
                cursor.execute(
                    "SELECT set_config('default_text_search_config', %s, true)", [original]
                )

    def _search(
        self,
        query: str,
        base_qs: QuerySet[BlogPost] | None = None,
        *,
        mode: str = "exact",
        page_number: int = 1,
    ) -> list[BlogPost]:
        if base_qs is None:
            base_qs = published_posts_queryset(include_tags=False)
        page = _perform_database_search(
            self.factory.get(
                "/search/", {"q": query, "mode": mode, "page": page_number}
            ),
            base_qs,
            normalize_search_text(query),
            f"postgresql-search:{self.id()}:{mode}:{page_number}",
            mode=mode,
        )
        return list(page.object_list)

    def _create_posts(self, *titles: str) -> list[BlogPost]:
        posts = BlogPost.objects.bulk_create(
            [
                BlogPost(
                    author=self.author,
                    title=title,
                    content="",
                    excerpt="",
                    slug=f"fts-{self._testMethodName}-{number}",
                    status=BlogPost.Status.PUBLISHED,
                    published_at=self.published_at,
                )
                for number, title in enumerate(titles)
            ]
        )
        for post in posts:
            update_search_vector(post)
        return posts

    def test_postgresql_18(self) -> None:
        self.assertEqual(connection.pg_version // 10000, 18)

    def test_python_and_sql_normalization_agree(self) -> None:
        for text in ("MİGROS", "MIGROS", "IŞIK", "YÜNSA", "İ i I ı ü u", '"İ" OR I -Ü'):
            for form in ("NFC", "NFD"):
                source = unicodedata.normalize(form, text)
                with self.subTest(source=source):
                    actual = BlogPost.objects.annotate(
                        normalized=normalize_search_expression(Value(source))
                    ).values_list("normalized", flat=True).first()
                    self.assertEqual(actual, normalize_search_text(source))

    def test_both_vectors_are_populated_with_field_weights(self) -> None:
        self.title_post.refresh_from_db()
        self.content_post.refresh_from_db()
        for field in ("search_vector", "search_vector_exact"):
            self.assertIn("B", getattr(self.title_post, field))
            self.assertIn("migros", getattr(self.title_post, field))
            self.assertIn("migros", getattr(self.content_post, field))

    def test_both_gin_indexes_exist(self) -> None:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT indexname FROM pg_indexes WHERE tablename = %s AND indexdef LIKE %s",
                [BlogPost._meta.db_table, "%USING gin%"],
            )
            self.assertEqual(
                {row[0] for row in cursor.fetchall()},
                {"blogpost_fts_gin", "blogpost_fts_exact_gin"},
            )

    def test_full_financial_title_matches_and_preserves_field_weights(self) -> None:
        for mode in self.modes:
            with self.subTest(mode=mode):
                results = self._search(self.full_title, mode=mode)
                self.assertEqual(
                    [post.pk for post in results],
                    [self.title_post.pk, self.content_post.pk],
                )
                self.assertGreater(results[0].rank, results[1].rank)
                self.assertGreater(results[1].rank, 0)

    def test_title_only_match(self) -> None:
        for mode in self.modes:
            with self.subTest(mode=mode):
                results = self._search(
                    self.full_title,
                    published_posts_queryset(include_tags=False).filter(
                        pk__in=[self.title_post.pk, self.unrelated_post.pk]
                    ),
                    mode=mode,
                )
                self.assertEqual([post.pk for post in results], [self.title_post.pk])
                self.assertGreater(results[0].rank, 0)

    def test_content_only_match(self) -> None:
        for mode in self.modes:
            with self.subTest(mode=mode):
                results = self._search(
                    self.full_title,
                    published_posts_queryset(include_tags=False).filter(
                        pk__in=[self.content_post.pk, self.unrelated_post.pk]
                    ),
                    mode=mode,
                )
                self.assertEqual([post.pk for post in results], [self.content_post.pk])
                self.assertGreater(results[0].rank, 0)

    def test_vector_and_search_ignore_database_default_config(self) -> None:
        baseline = {}
        for config in self.default_configs:
            with self.subTest(config=config), self._default_config(config):
                for post in (self.title_post, self.content_post, self.unrelated_post):
                    update_search_vector(post)
                vectors = list(
                    BlogPost.objects.order_by("pk").values_list(
                        "pk", "search_vector", "search_vector_exact"
                    )
                )
                for mode in self.modes:
                    with self.subTest(mode=mode):
                        results = self._search(self.full_title, mode=mode)
                        self.assertEqual(
                            [post.pk for post in results],
                            [self.title_post.pk, self.content_post.pk],
                        )
                        self.assertTrue(all(post.rank > 0 for post in results))
                        actual = (vectors, [(post.pk, post.rank) for post in results])
                        if mode not in baseline:
                            baseline[mode] = actual
                        else:
                            self.assertEqual(actual, baseline[mode])

    def test_negative_only_query_keeps_zero_rank_matches(self) -> None:
        for config in self.default_configs:
            with self.subTest(config=config), self._default_config(config):
                for mode in self.modes:
                    with self.subTest(mode=mode):
                        results = self._search("-migros", mode=mode)
                        self.assertEqual(
                            [post.pk for post in results], [self.unrelated_post.pk]
                        )
                        self.assertEqual(results[0].rank, 0)

    def test_yunsa_exact_excludes_stemming_collision(self) -> None:
        company, collision = self._create_posts("Yünsa", "y")
        for query in ("Yünsa", "YÜNSA", unicodedata.normalize("NFD", "YÜNSA")):
            for mode in self.modes:
                with self.subTest(query=query, mode=mode):
                    results = self._search(query, mode=mode)
                    expected = [company.pk]
                    if mode == "stemmed":
                        expected.append(collision.pk)
                    self.assertCountEqual([post.pk for post in results], expected)

    def test_database_search_defaults_to_exact(self) -> None:
        company, collision = self._create_posts("Yünsa", "y")
        page = _perform_database_search(
            self.factory.get("/search/", {"q": "YÜNSA"}),
            published_posts_queryset(include_tags=False).filter(
                pk__in=[company.pk, collision.pk]
            ),
            normalize_search_text("YÜNSA"),
            f"postgresql-search:{self.id()}",
        )
        self.assertEqual([post.pk for post in page.object_list], [company.pk])

    def test_real_turkish_inflection_matches_only_in_stemmed_mode(self) -> None:
        singular, plural = self._create_posts("kitap", "kitaplar")
        for query, exact_post in (("kitap", singular), ("kitaplar", plural)):
            with self.subTest(query=query):
                self.assertEqual(
                    [post.pk for post in self._search(query, mode="exact")],
                    [exact_post.pk],
                )
                self.assertCountEqual(
                    [post.pk for post in self._search(query, mode="stemmed")],
                    [singular.pk, plural.pk],
                )

    def test_turkish_casing_and_unicode_forms_match_seamlessly(self) -> None:
        letter_groups = (("I", "ı", "İ", "i"), ("U", "u", "Ü", "ü"))
        forms = ("NFC", "NFD")
        # Create posts for each representative upper letter in both NFC and NFD
        posts = self._create_posts(
            *(unicodedata.normalize(form, group[0]) for group in letter_groups for form in forms)
        )
        base_qs = published_posts_queryset(include_tags=False).filter(
            pk__in=[post.pk for post in posts]
        )
        for index, group in enumerate(letter_groups):
            start = index * len(forms)
            expected = [post.pk for post in posts[start:start + len(forms)]]
            for variant in group:
                for form in forms:
                    query = unicodedata.normalize(form, variant)
                    for mode in self.modes:
                        with self.subTest(query=query, form=form, mode=mode):
                            results = self._search(query, base_qs, mode=mode)
                            self.assertCountEqual(
                                [post.pk for post in results],
                                expected,
                            )

    def test_websearch_operators(self) -> None:
        adjacent, reversed_post, separated, cat, dog, unrelated = self._create_posts(
            "kedi köpek", "köpek kedi", "kedi küçük köpek", "kedi", "köpek", "balık"
        )
        base_qs = published_posts_queryset(include_tags=False).filter(
            pk__in=[
                post.pk for post in (adjacent, reversed_post, separated, cat, dog, unrelated)
            ]
        )
        cases = (
            ("kedi köpek", [adjacent, reversed_post, separated]),
            ('"kedi köpek"', [adjacent]),
            ("kedi -köpek", [cat]),
            *(
                (f"kedi {operator} köpek", [adjacent, reversed_post, separated, cat, dog])
                for operator in ("OR", "or", "Or", "oR")
            ),
        )
        for mode in self.modes:
            for query, expected in cases:
                with self.subTest(mode=mode, query=query):
                    self.assertCountEqual(
                        [post.pk for post in self._search(query, base_qs, mode=mode)],
                        [post.pk for post in expected],
                    )

    def test_empty_and_punctuation_queries_return_no_matches(self) -> None:
        for mode in self.modes:
            for query in ("", "   ", "...", "!!!", '""', "-"):
                with self.subTest(mode=mode, query=query):
                    self.assertEqual(self._search(query, mode=mode), [])

    def test_equal_ranks_use_publication_date_then_descending_pk(self) -> None:
        posts = BlogPost.objects.bulk_create(
            [
                BlogPost(
                    id=UUID(int=number),
                    author=self.author,
                    title="Eşitlik",
                    content="",
                    slug=f"fts-tie-{number}",
                    status=BlogPost.Status.PUBLISHED,
                    published_at=published_at,
                )
                for number, published_at in (
                    (1, self.published_at),
                    (3, self.published_at),
                    (2, self.published_at),
                    (4, self.published_at - timedelta(days=1)),
                )
            ]
        )
        for post in posts:
            update_search_vector(post)
        for mode in self.modes:
            with self.subTest(mode=mode):
                results = self._search("Eşitlik", mode=mode)
                self.assertEqual(
                    [post.pk for post in results], [UUID(int=n) for n in (3, 2, 1, 4)]
                )
                self.assertGreater(results[0].rank, 0)
                self.assertTrue(all(post.rank == results[0].rank for post in results))

    def test_equal_ranks_have_stable_order_across_pages(self) -> None:
        page_count = 3
        post_count = POST_PAGE_SIZE * (page_count - 1) + 1
        posts = self._create_posts(*(["Eşitlik"] * post_count))
        expected = sorted((post.pk for post in posts), reverse=True)
        for mode in self.modes:
            with self.subTest(mode=mode):
                results = [
                    post
                    for page_number in range(1, page_count + 1)
                    for post in self._search("Eşitlik", mode=mode, page_number=page_number)
                ]
                self.assertEqual([post.pk for post in results], expected)
                self.assertGreater(results[0].rank, 0)
                self.assertTrue(all(post.rank == results[0].rank for post in results))
                for page_number in reversed(range(1, page_count + 1)):
                    repeated = self._search("Eşitlik", mode=mode, page_number=page_number)
                    offset = (page_number - 1) * POST_PAGE_SIZE
                    self.assertEqual(
                        [post.pk for post in repeated],
                        expected[offset:offset + POST_PAGE_SIZE],
                    )

    def test_full_rebuild_removes_old_tokens_and_refreshes_both_caches(self) -> None:
        first, second = self._create_posts("Backfill First", "Backfill Second")
        BlogPost.objects.filter(pk=first.pk).update(content="oldtoken")
        update_search_vector(first)
        cache.set(SEARCH_CACHE_VERSION_KEY, "before-backfill", timeout=None)
        url = reverse("blog:search_results")
        old_tokens = {}
        for mode in self.modes:
            response = self.client.get(url, {"q": "oldtoken", "mode": mode})
            self.assertEqual([p.pk for p in response.context["page_obj"]], [first.pk])
            token = response.context["search_cache_token"]
            old_tokens[mode] = token
            self.assertEqual(cache.get("search_" + token), (1, [first.pk]))
            self.assertIn(
                first.title,
                cache.get(make_template_fragment_key("post_list_search_v3", [token])),
            )

        BlogPost.objects.filter(pk=first.pk).update(content="freshword")
        BlogPost.objects.filter(pk=second.pk).update(content="oldtoken")
        for mode in self.modes:
            with patch("blog.views._perform_database_search") as search:
                stale = self.client.get(url, {"q": "oldtoken", "mode": mode})
            search.assert_not_called()
            self.assertEqual([p.pk for p in stale.context["page_obj"]], [first.pk])

        with self.captureOnCommitCallbacks(execute=True):
            call_command("rebuild_search_vectors", "--all", "--batch-size", "2", stdout=StringIO())

        self.assertNotEqual(cache.get(SEARCH_CACHE_VERSION_KEY), "before-backfill")
        first.refresh_from_db()
        for field in ("search_vector", "search_vector_exact"):
            self.assertNotIn("oldtoken", getattr(first, field))
            self.assertIn("freshword", getattr(first, field))
        for mode in self.modes:
            fresh = self.client.get(url, {"q": "oldtoken", "mode": mode})
            self.assertEqual([p.pk for p in fresh.context["page_obj"]], [second.pk])
            self.assertNotEqual(fresh.context["search_cache_token"], old_tokens[mode])
            main = fresh.content.decode().split("<main>")[1].split("</main>")[0]
            self.assertIn(second.title, main)
            self.assertNotIn(first.title, main)
            self.assertEqual([p.pk for p in self._search("freshword", mode=mode)], [first.pk])

    def test_default_backfill_fills_null_exact_vector(self) -> None:
        BlogPost.objects.filter(pk=self.title_post.pk).update(search_vector_exact=None)
        with self.captureOnCommitCallbacks(execute=True):
            call_command("rebuild_search_vectors", stdout=StringIO())
        self.title_post.refresh_from_db()
        self.assertIsNotNone(self.title_post.search_vector_exact)
        self.assertIsNotNone(self.title_post.search_vector)
        for mode in self.modes:
            self.assertIn(self.title_post.pk, [p.pk for p in self._search(self.full_title, mode=mode)])