from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from blog.cache_keys import NAV_KEYS
from blog.models import BlogPost, Category
from comments.models import Comment

User = get_user_model()


class CommentSignalsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="signaluser@example.com",
            password="testpassword",
        )
        self.category = Category.objects.create(name="Signal Cat", slug="signal-cat")
        self.post = BlogPost.objects.create(
            title="Signal Post",
            author=self.user,
            category=self.category,
            status=BlogPost.Status.PUBLISHED,
        )

    @patch("comments.signals.recalculate_popularity_score")
    @patch("comments.signals.cache.delete_many")
    def test_cache_cleared_on_comment_save(self, mock_delete_many, mock_recalculate):
        comment = Comment.objects.create(
            post=self.post,
            author=self.user,
            body="New comment",
            status=Comment.Status.PENDING,
        )
        mock_delete_many.assert_called_with(NAV_KEYS)
        mock_recalculate.assert_called_with(self.post.id)

        mock_delete_many.reset_mock()
        mock_recalculate.reset_mock()
        comment.status = Comment.Status.APPROVED
        comment.save()
        mock_delete_many.assert_called_with(NAV_KEYS)
        mock_recalculate.assert_called_with(self.post.id)

    @patch("comments.signals.recalculate_popularity_score")
    @patch("comments.signals.cache.delete_many")
    def test_cache_cleared_on_comment_delete(self, mock_delete_many, mock_recalculate):
        comment = Comment.objects.create(
            post=self.post,
            author=self.user,
            body="Comment to delete",
            status=Comment.Status.PENDING,
        )
        mock_delete_many.reset_mock()
        mock_recalculate.reset_mock()

        comment.delete()
        mock_delete_many.assert_called_with(NAV_KEYS)
        mock_recalculate.assert_called_with(self.post.id)
