from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from blog.models import BlogPost

User = get_user_model()


class RebuildSearchVectorsCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="command_author@example.com", password="password"
        )
        self.missing_vector_post = BlogPost.objects.create(
            title="Missing vector",
            author=self.user,
            slug="missing-vector",
            status=BlogPost.Status.PUBLISHED,
        )
        self.existing_vector_post = BlogPost.objects.create(
            title="Existing vector",
            author=self.user,
            slug="existing-vector",
            status=BlogPost.Status.PUBLISHED,
        )
        BlogPost.objects.filter(pk=self.existing_vector_post.pk).update(
            search_vector="existing"
        )
        BlogPost.objects.create(
            title="Draft", author=self.user, slug="draft-vector"
        )
        BlogPost.objects.create(
            title="Archived",
            author=self.user,
            slug="archived-vector",
            status=BlogPost.Status.ARCHIVED,
        )

    @patch("blog.management.commands.rebuild_search_vectors.invalidate_search_cache")
    @patch("blog.management.commands.rebuild_search_vectors.update_search_vector")
    def test_default_rebuilds_only_published_posts_without_vectors(
        self, mock_update_search_vector, mock_invalidate_search_cache
    ):
        output = StringIO()

        call_command("rebuild_search_vectors", stdout=output)

        mock_update_search_vector.assert_called_once_with(self.missing_vector_post)
        mock_invalidate_search_cache.assert_called_once()
        self.assertIn("Updated 1 posts; skipped 1.", output.getvalue())

    @patch("blog.management.commands.rebuild_search_vectors.invalidate_search_cache")
    @patch("blog.management.commands.rebuild_search_vectors.update_search_vector")
    def test_all_rebuilds_every_published_post(
        self, mock_update_search_vector, mock_invalidate_search_cache
    ):
        output = StringIO()

        call_command("rebuild_search_vectors", "--all", stdout=output)

        self.assertCountEqual(
            [call.args[0] for call in mock_update_search_vector.call_args_list],
            [self.missing_vector_post, self.existing_vector_post],
        )
        mock_invalidate_search_cache.assert_called_once()
        self.assertIn("Updated 2 posts; skipped 0.", output.getvalue())

    @patch("blog.management.commands.rebuild_search_vectors.invalidate_search_cache")
    @patch("blog.management.commands.rebuild_search_vectors.update_search_vector")
    def test_does_not_invalidate_cache_when_no_vectors_are_rebuilt(
        self, mock_update_search_vector, mock_invalidate_search_cache
    ):
        BlogPost.objects.filter(pk=self.missing_vector_post.pk).update(
            search_vector="present"
        )

        call_command("rebuild_search_vectors")

        mock_update_search_vector.assert_not_called()
        mock_invalidate_search_cache.assert_not_called()
