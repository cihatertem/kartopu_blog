from io import StringIO

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from blog.models import (
    POPULARITY_COMMENT_WEIGHT,
    POPULARITY_REACTION_WEIGHT,
    POPULARITY_VIEW_WEIGHT,
    BlogPost,
    BlogPostReaction,
)
from blog.services import recalculate_popularity_score, recalculate_popularity_scores
from comments.models import Comment

User = get_user_model()


class PopularityScoreTests(TestCase):
    def setUp(self):
        cache.clear()
        self.author = User.objects.create_user(
            email="author@test.com", password="password"
        )
        self.reader = User.objects.create_user(
            email="reader@test.com", password="password"
        )
        self.post = BlogPost.objects.create(
            title="Popular Post",
            slug="popular-post",
            author=self.author,
            status=BlogPost.Status.PUBLISHED,
            published_at=timezone.now(),
            view_count=10,
        )

    def _score(self):
        return BlogPost.objects.values_list("popularity_score", flat=True).get(
            pk=self.post.pk
        )

    def test_post_save_sets_baseline_score_from_views(self):
        # Sadece view_count varken skor = view_count * VIEW_WEIGHT.
        self.assertEqual(self._score(), 10 * POPULARITY_VIEW_WEIGHT)

    def test_approved_comment_increases_score(self):
        Comment.objects.create(
            post=self.post,
            author=self.reader,
            body="great",
            status=Comment.Status.APPROVED,
        )
        self.assertEqual(
            self._score(),
            10 * POPULARITY_VIEW_WEIGHT + 1 * POPULARITY_COMMENT_WEIGHT,
        )

    def test_pending_comment_does_not_count(self):
        Comment.objects.create(
            post=self.post,
            author=self.reader,
            body="waiting",
            status=Comment.Status.PENDING,
        )
        self.assertEqual(self._score(), 10 * POPULARITY_VIEW_WEIGHT)

    def test_reaction_is_debounced_and_marks_dirty(self):
        from blog.popularity_queue import drain_popularity_dirty

        BlogPostReaction.objects.create(
            post=self.post,
            user=self.reader,
            reaction=BlogPostReaction.Reaction.KALP.value,
        )
        # Reaction debounce edilir: skor anında yeniden hesaplanmaz, taban kalır.
        self.assertEqual(self._score(), 10 * POPULARITY_VIEW_WEIGHT)
        # Bunun yerine yazı "kirli" kuyruğa düşer.
        self.assertEqual(drain_popularity_dirty(), {str(self.post.pk)})

    def test_pending_command_applies_reaction_score(self):
        out = StringIO()
        BlogPostReaction.objects.create(
            post=self.post,
            user=self.reader,
            reaction=BlogPostReaction.Reaction.KALP.value,
        )

        call_command(
            "recalculate_popularity_scores", "--pending", verbosity=2, stdout=out
        )

        self.assertEqual(
            self._score(),
            10 * POPULARITY_VIEW_WEIGHT + 1 * POPULARITY_REACTION_WEIGHT,
        )
        self.assertIn("popularity_score güncellendi: 1 yazı.", out.getvalue())

    def test_pending_command_no_pending_items(self):
        out = StringIO()
        BlogPost.objects.filter(pk=self.post.pk).update(popularity_score=999)

        call_command(
            "recalculate_popularity_scores", "--pending", verbosity=2, stdout=out
        )

        # Kuyruk boşken hiçbir UPDATE çalışmaz; bozuk skor olduğu gibi kalır.
        self.assertEqual(self._score(), 999)
        self.assertIn("Bekleyen popülerlik güncellemesi yok.", out.getvalue())

    def test_recalculate_single_post(self):
        # Skoru kasten bozup tek post yeniden hesaplamayi dogrula.
        BlogPost.objects.filter(pk=self.post.pk).update(popularity_score=999)
        recalculate_popularity_score(self.post.pk)
        self.assertEqual(self._score(), 10 * POPULARITY_VIEW_WEIGHT)

    def test_recalculate_all_returns_row_count(self):
        BlogPost.objects.filter(pk=self.post.pk).update(popularity_score=0)
        updated = recalculate_popularity_scores()
        self.assertEqual(updated, BlogPost.objects.count())
        self.assertEqual(self._score(), 10 * POPULARITY_VIEW_WEIGHT)

    def test_management_command_recalculates(self):
        BlogPost.objects.filter(pk=self.post.pk).update(popularity_score=0)
        out = StringIO()

        call_command("recalculate_popularity_scores", stdout=out)

        self.assertEqual(out.getvalue(), "")
        self.assertEqual(self._score(), 10 * POPULARITY_VIEW_WEIGHT)

    def test_management_command_outputs_when_verbose(self):
        out = StringIO()

        call_command("recalculate_popularity_scores", verbosity=2, stdout=out)

        self.assertIn("popularity_score güncellendi: 1 yazı.", out.getvalue())
