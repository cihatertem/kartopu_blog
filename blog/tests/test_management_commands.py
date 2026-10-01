from collections.abc import Iterator
from contextlib import contextmanager
from io import StringIO
from unittest import skipIf, skipUnless
from unittest.mock import MagicMock, patch
from uuid import UUID

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, connection
from django.db.models import QuerySet
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext

from blog.cache_keys import SEARCH_CACHE_VERSION_KEY
from blog.models import BlogPost
from blog.signals import invalidate_search_cache, update_search_vector

User = get_user_model()
COMMAND_MODULE = "blog.management.commands.rebuild_search_vectors"


def create_command_posts(author: User) -> list[BlogPost]:
    return BlogPost.objects.bulk_create(
        [
            BlogPost(
                id=UUID(int=number * 10),
                title=f"MİGROS {number}",
                content="Finansal sonuçlar",
                slug=f"command-post-{number}",
                author=author,
                status=status,
            )
            for number, status in enumerate(
                [BlogPost.Status.PUBLISHED] * 4
                + [BlogPost.Status.DRAFT, BlogPost.Status.ARCHIVED],
                start=1,
            )
        ]
    )


def clear_missing_vectors(posts: list[BlogPost]) -> None:
    BlogPost.objects.filter(pk=posts[0].pk).update(
        search_vector=None, search_vector_exact=None
    )
    BlogPost.objects.filter(pk=posts[1].pk).update(search_vector=None)
    BlogPost.objects.filter(pk=posts[2].pk).update(search_vector_exact=None)


class RebuildSearchVectorsCommandTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(email="command_author@example.com")
        self.posts = create_command_posts(self.user)
        BlogPost.objects.filter(status=BlogPost.Status.PUBLISHED).update(
            search_vector="existing", search_vector_exact="existing"
        )
        clear_missing_vectors(self.posts)

    @contextmanager
    def mocked_command(self) -> Iterator[tuple[MagicMock, MagicMock]]:
        # Only the command's backend guard is replaced, never SQLite's vendor.
        with (
            patch(f"{COMMAND_MODULE}.connection") as backend,
            patch(f"{COMMAND_MODULE}.update_search_vector", return_value=1) as update,
            patch(f"{COMMAND_MODULE}.invalidate_search_cache") as invalidate,
        ):
            backend.vendor = "postgresql"
            yield update, invalidate

    def test_default_rebuilds_either_missing_vector_once(self) -> None:
        output = StringIO()
        with self.mocked_command() as (update, invalidate):
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                call_command("rebuild_search_vectors", stdout=output)
                invalidate.assert_not_called()
            self.assertEqual(len(callbacks), 1)
            self.assertEqual(
                [call.args[0].pk for call in update.call_args_list],
                [post.pk for post in self.posts[:3]],
            )
            invalidate.assert_called_once_with()
        self.assertIn("Updated 3 posts; skipped 1.", output.getvalue())

    def test_all_rebuilds_every_published_post_in_batches(self) -> None:
        output = StringIO()
        with self.mocked_command() as (update, invalidate):
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                call_command(
                    "rebuild_search_vectors", "--all", "--batch-size", "2", stdout=output
                )
            self.assertEqual(len(callbacks), 2)
            self.assertEqual(invalidate.call_count, 2)
            self.assertEqual(
                [call.args[0].pk for call in update.call_args_list],
                [post.pk for post in self.posts[:4]],
            )
        self.assertIn("Updated 4 posts; skipped 0.", output.getvalue())

    def test_zero_updates_advance_and_do_not_invalidate(self) -> None:
        output = StringIO()
        with self.mocked_command() as (update, invalidate):
            update.return_value = 0
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                call_command("rebuild_search_vectors", batch_size=1, stdout=output)
            self.assertEqual(update.call_count, 3)
            self.assertEqual(callbacks, [])
            invalidate.assert_not_called()
        self.assertIn("Updated 0 posts; skipped 4.", output.getvalue())

    def test_mixed_rowcounts_invalidate_only_nonempty_update_batches(self) -> None:
        output = StringIO()
        with self.mocked_command() as (update, invalidate):
            update.side_effect = [0, 1, 0]
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                call_command("rebuild_search_vectors", batch_size=1, stdout=output)
            self.assertEqual(len(callbacks), 1)
            invalidate.assert_called_once_with()
        self.assertIn("Updated 1 posts; skipped 3.", output.getvalue())

    def test_no_missing_vectors_performs_no_updates(self) -> None:
        BlogPost.objects.filter(status=BlogPost.Status.PUBLISHED).update(
            search_vector="present", search_vector_exact="present"
        )
        with self.mocked_command() as (update, invalidate):
            call_command("rebuild_search_vectors", stdout=StringIO())
            update.assert_not_called()
            invalidate.assert_not_called()

    def test_no_published_posts_performs_no_updates(self) -> None:
        BlogPost.objects.update(status=BlogPost.Status.DRAFT)
        output = StringIO()
        with self.mocked_command() as (update, invalidate):
            call_command("rebuild_search_vectors", stdout=output)
            update.assert_not_called()
            invalidate.assert_not_called()
        self.assertIn("Updated 0 posts; skipped 0.", output.getvalue())

    def test_batch_size_must_be_positive(self) -> None:
        with self.mocked_command() as (update, invalidate):
            for value in (0, -1):
                with (
                    self.subTest(value=value),
                    self.assertRaisesMessage(CommandError, "positive"),
                ):
                    call_command("rebuild_search_vectors", batch_size=value)
            update.assert_not_called()
            invalidate.assert_not_called()

    def test_batch_size_must_be_an_integer(self) -> None:
        with self.assertRaises(CommandError):
            call_command("rebuild_search_vectors", "--batch-size", "invalid")

    @skipIf(connection.vendor == "postgresql", "Requires an unsupported real backend")
    def test_real_unsupported_backend_raises_without_queries(self) -> None:
        with (
            self.assertNumQueries(0),
            self.assertRaisesMessage(CommandError, "PostgreSQL"),
        ):
            call_command("rebuild_search_vectors")

    def test_default_batch_limit_and_projection(self) -> None:
        with (
            self.mocked_command() as (update, _),
            CaptureQueriesContext(connection) as queries,
        ):
            call_command("rebuild_search_vectors", stdout=StringIO())
        batches = [
            query["sql"] for query in queries
            if query["sql"].startswith('SELECT "blog_blogpost"."id",')
        ]
        self.assertTrue(batches)
        for sql in batches:
            self.assertEqual(
                sql.split(" FROM ")[0],
                'SELECT "blog_blogpost"."id", "blog_blogpost"."status"',
            )
            self.assertIn("LIMIT 100", sql)
            self.assertNotIn("OFFSET", sql)
        for call in update.call_args_list:
            self.assertIn("content", call.args[0].get_deferred_fields())

    def test_failed_batch_does_not_count_or_schedule_its_updates(self) -> None:
        with self.mocked_command() as (update, invalidate):
            update.side_effect = [1, 1, 1, DatabaseError("batch failed")]
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                with self.assertRaisesMessage(CommandError, "Updated 2 posts"):
                    call_command("rebuild_search_vectors", "--all", batch_size=2)
            self.assertEqual(len(callbacks), 1)
            invalidate.assert_called_once_with()


@skipUnless(connection.vendor == "postgresql", "Requires real PostgreSQL full-text search")
class PostgreSQLRebuildSearchVectorsCommandTests(TransactionTestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(email="command_pg@example.invalid")
        self.posts = create_command_posts(self.user)
        for post in self.posts[:4]:
            self.assertEqual(update_search_vector(post), 1)
        clear_missing_vectors(self.posts)
        cache.clear()
        cache.set(SEARCH_CACHE_VERSION_KEY, "before", timeout=None)
        self.addCleanup(cache.clear)

    def assert_vectors_present(self, posts: list[BlogPost]) -> None:
        for post in posts:
            post.refresh_from_db()
            self.assertIsNotNone(post.search_vector)
            self.assertIsNotNone(post.search_vector_exact)

    def test_multiple_batches_commit_cache_versions_without_save_or_newsletter(self) -> None:
        versions = []
        committed_counts = []

        def invalidate() -> None:
            self.assertFalse(connection.in_atomic_block)
            invalidate_search_cache()
            versions.append(cache.get(SEARCH_CACHE_VERSION_KEY))
            committed_counts.append(
                BlogPost.objects.filter(
                    status=BlogPost.Status.PUBLISHED,
                    search_vector__isnull=False,
                    search_vector_exact__isnull=False,
                ).count()
            )

        output = StringIO()
        with (
            patch(
                f"{COMMAND_MODULE}.invalidate_search_cache", side_effect=invalidate
            ) as invalidate_mock,
            patch.object(BlogPost, "save", side_effect=AssertionError("Must not save")),
            patch("newsletter.signals.queue_post_published_notification") as notify,
        ):
            call_command("rebuild_search_vectors", batch_size=2, stdout=output)
            self.assertEqual(invalidate_mock.call_count, 2)
            notify.assert_not_called()
        self.assertEqual(committed_counts, [3, 4])
        self.assertEqual(len(set(versions + ["before"])), 3)
        self.assert_vectors_present(self.posts[:4])
        for post in self.posts[4:]:
            post.refresh_from_db()
            self.assertIsNone(post.search_vector)
            self.assertIsNone(post.search_vector_exact)
        self.assertIn("Updated 3 posts; skipped 1.", output.getvalue())

    def test_all_rebuilds_both_existing_vectors(self) -> None:
        BlogPost.objects.filter(status=BlogPost.Status.PUBLISHED).update(
            search_vector="obsolete", search_vector_exact="obsolete"
        )
        output = StringIO()
        with patch(
            f"{COMMAND_MODULE}.invalidate_search_cache", wraps=invalidate_search_cache
        ) as invalidate:
            call_command("rebuild_search_vectors", "--all", batch_size=2, stdout=output)
        self.assertEqual(invalidate.call_count, 2)
        for post in self.posts[:4]:
            post.refresh_from_db()
            self.assertNotIn("obsolete", post.search_vector)
            self.assertNotIn("obsolete", post.search_vector_exact)
        self.assertIn("Updated 4 posts; skipped 0.", output.getvalue())

    def test_no_work_does_not_change_cache_version(self) -> None:
        for post in self.posts[:3]:
            update_search_vector(post)
        with (
            patch(
                f"{COMMAND_MODULE}.update_search_vector", wraps=update_search_vector
            ) as update,
            patch(
                f"{COMMAND_MODULE}.invalidate_search_cache", wraps=invalidate_search_cache
            ) as invalidate,
        ):
            call_command("rebuild_search_vectors", stdout=StringIO())
            update.assert_not_called()
            invalidate.assert_not_called()
        self.assertEqual(cache.get(SEARCH_CACHE_VERSION_KEY), "before")

    def test_zero_row_batch_after_concurrent_status_change_advances(self) -> None:
        seen = []
        other = connection.copy()
        self.addCleanup(other.close)

        def update(post: BlogPost) -> int:
            seen.append(post.pk)
            if post.pk in {item.pk for item in self.posts[:2]}:
                with other.cursor() as cursor:
                    cursor.execute(
                        'UPDATE "blog_blogpost" SET "status" = %s WHERE "id" = %s',
                        [BlogPost.Status.DRAFT, post.pk],
                    )
                self.assertEqual(cache.get(SEARCH_CACHE_VERSION_KEY), "before")
            return update_search_vector(post)

        output = StringIO()
        with (
            patch(f"{COMMAND_MODULE}.update_search_vector", side_effect=update),
            patch(
                f"{COMMAND_MODULE}.invalidate_search_cache", wraps=invalidate_search_cache
            ) as invalidate,
        ):
            call_command("rebuild_search_vectors", batch_size=2, stdout=output)
        self.assertEqual(seen, [post.pk for post in self.posts[:3]])
        invalidate.assert_called_once_with()
        self.assert_vectors_present(self.posts[2:4])
        self.posts[0].refresh_from_db()
        self.assertIsNone(self.posts[0].search_vector)
        self.assertIsNone(self.posts[0].search_vector_exact)
        self.assertIn("Updated 1 posts; skipped 3.", output.getvalue())

    def test_fixed_uuid_upper_bound_excludes_new_higher_posts(self) -> None:
        seen = []

        def update(post: BlogPost) -> int:
            seen.append(post.pk)
            if len(seen) == 1:
                BlogPost.objects.bulk_create([
                    BlogPost(
                        id=UUID(int=number), title="New publication",
                        slug=f"new-publication-{number}",
                        author=self.user, status=BlogPost.Status.PUBLISHED,
                    )
                    for number in (5, 15, 45)
                ])
            return update_search_vector(post)

        output = StringIO()
        with patch(f"{COMMAND_MODULE}.update_search_vector", side_effect=update):
            call_command("rebuild_search_vectors", "--all", batch_size=1, stdout=output)
        self.assertEqual(seen, [UUID(int=number) for number in (10, 15, 20, 30, 40)])
        for number in (5, 45):
            new = BlogPost.objects.get(pk=UUID(int=number))
            self.assertIsNone(new.search_vector)
            self.assertIsNone(new.search_vector_exact)
        self.assert_vectors_present([BlogPost.objects.get(pk=UUID(int=15))])
        self.assertIn("Updated 5 posts; skipped 0.", output.getvalue())
        self.assertIn("Published snapshot: 4 posts.", output.getvalue())

    def test_sql_limits_keyset_projection_and_no_server_side_cursor(self) -> None:
        original_iterator = QuerySet.iterator

        def iterator(queryset: QuerySet, *args, **kwargs) -> Iterator:
            self.assertIsNot(queryset.model, BlogPost)
            return original_iterator(queryset, *args, **kwargs)

        with (
            CaptureQueriesContext(connection) as queries,
            patch.object(QuerySet, "iterator", iterator),
        ):
            call_command("rebuild_search_vectors", batch_size=2, stdout=StringIO())
        selects = [
            query["sql"] for query in queries
            if query["sql"].startswith('SELECT "blog_blogpost"."id"')
        ]
        self.assertIn('ORDER BY 1 DESC LIMIT 1', selects[0])
        batches = selects[1:]
        self.assertGreaterEqual(len(batches), 2)
        for sql in batches:
            self.assertEqual(
                sql.split(" FROM ")[0],
                'SELECT "blog_blogpost"."id", "blog_blogpost"."status"',
            )
            self.assertIn("LIMIT 2", sql)
            self.assertIn('"blog_blogpost"."id" <=', sql)
            self.assertIn('ORDER BY "blog_blogpost"."id" ASC', sql)
            self.assertNotIn("OFFSET", sql)
        self.assertIn('"blog_blogpost"."id" >', batches[1])
        self.assertFalse(any(
            "DECLARE" in query["sql"] and 'FROM "blog_blogpost" ' in query["sql"]
            for query in queries
        ))

    def test_partial_failure_rolls_back_batch_and_rerun_is_idempotent(self) -> None:
        BlogPost.objects.filter(status=BlogPost.Status.PUBLISHED).update(
            search_vector=None, search_vector_exact=None
        )
        seen = []

        def fail_after_update(post: BlogPost) -> int:
            seen.append(post.pk)
            result = update_search_vector(post)
            if post.pk == self.posts[3].pk:
                raise DatabaseError("injected batch failure")
            return result

        with (
            patch(
                f"{COMMAND_MODULE}.update_search_vector", side_effect=fail_after_update
            ),
            patch(
                f"{COMMAND_MODULE}.invalidate_search_cache", wraps=invalidate_search_cache
            ) as invalidate,
        ):
            with self.assertRaisesMessage(CommandError, "Updated 2 posts"):
                call_command("rebuild_search_vectors", batch_size=2, stdout=StringIO())
            invalidate.assert_called_once_with()
        self.assertEqual(seen, [post.pk for post in self.posts[:4]])
        first_version = cache.get(SEARCH_CACHE_VERSION_KEY)
        self.assertNotEqual(first_version, "before")
        self.assert_vectors_present(self.posts[:2])
        for post in self.posts[2:4]:
            post.refresh_from_db()
            self.assertIsNone(post.search_vector)
            self.assertIsNone(post.search_vector_exact)
        with (
            patch(
                f"{COMMAND_MODULE}.update_search_vector", wraps=update_search_vector
            ) as update,
            patch(
                f"{COMMAND_MODULE}.invalidate_search_cache", wraps=invalidate_search_cache
            ) as invalidate,
        ):
            call_command("rebuild_search_vectors", batch_size=2, stdout=StringIO())
            self.assertEqual(
                [call.args[0].pk for call in update.call_args_list],
                [post.pk for post in self.posts[2:4]],
            )
            invalidate.assert_called_once_with()
            self.assertNotEqual(cache.get(SEARCH_CACHE_VERSION_KEY), first_version)
            update.reset_mock()
            invalidate.reset_mock()
            final_version = cache.get(SEARCH_CACHE_VERSION_KEY)
            call_command("rebuild_search_vectors", batch_size=2, stdout=StringIO())
            update.assert_not_called()
            invalidate.assert_not_called()
            self.assertEqual(cache.get(SEARCH_CACHE_VERSION_KEY), final_version)
        self.assert_vectors_present(self.posts[:4])
