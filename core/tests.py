from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from blog.models import BlogPost, BlogPostReaction, Category
from comments.models import Comment
from core.context_processors import categories_tags_context
from core.markdown import render_markdown
from core.models import SiteSettings


class SiteSettingsTest(TestCase):
    def setUp(self):
        cache.clear()
        # Clean up any existing settings just in case
        SiteSettings.objects.all().delete()

    def test_singleton(self):
        SiteSettings.objects.create()

        with self.assertRaises(ValidationError):
            settings = SiteSettings(is_comments_enabled=False)
            settings.full_clean()
            settings.save()

    def test_get_settings_creates_default(self):
        settings = SiteSettings.get_settings()
        self.assertIsNotNone(settings)
        self.assertTrue(settings.is_comments_enabled)
        self.assertTrue(settings.is_newsletter_enabled)
        self.assertTrue(settings.is_contact_enabled)

    def test_cache_update_on_save(self):
        settings = SiteSettings.get_settings()
        settings.is_comments_enabled = False
        settings.save()

        cached_settings = cache.get("site_settings")
        self.assertFalse(cached_settings.is_comments_enabled)

        settings_from_method = SiteSettings.get_settings()
        self.assertFalse(settings_from_method.is_comments_enabled)


class MarkdownLinkTest(TestCase):
    @override_settings(SITE_BASE_URL="https://kartopu.money")
    def test_internal_links_no_nofollow(self):
        test_md = """
[Internal Relative](/blog/)
[Internal Absolute](https://kartopu.money/about/)
[External](https://www.google.com)
"""
        html = render_markdown(test_md)

        # Internal links should NOT have rel="nofollow"
        self.assertIn('<a href="/blog/">Internal Relative</a>', html)
        self.assertIn(
            '<a href="https://kartopu.money/about/">Internal Absolute</a>', html
        )

        # External links SHOULD have rel="nofollow"
        self.assertIn(
            '<a href="https://www.google.com" rel="nofollow">External</a>', html
        )

    @override_settings(SITE_BASE_URL="https://kartopu.money")
    def test_subdomain_is_internal(self):
        test_md = "[Subdomain](https://blog.kartopu.money/)"
        html = render_markdown(test_md)
        self.assertIn('<a href="https://blog.kartopu.money/">Subdomain</a>', html)
        self.assertNotIn('rel="nofollow"', html)

    @override_settings(SITE_BASE_URL="https://kartopu.money")
    def test_plain_text_links(self):
        test_md = "Check this: https://kartopu.money/contact/ and https://bing.com"
        html = render_markdown(test_md)

        # Internal plain text link might or might not be linkified depending on bleach,
        # but if it is, it shouldn't have nofollow.
        # External plain text link should be linkified with nofollow.
        self.assertIn('rel="nofollow"', html)
        self.assertIn("https://bing.com", html)


class PopularPostsContextProcessorTest(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(
            email="test@example.com", password="password"
        )  # pyright: ignore[reportCallIssue]
        self.category = Category.objects.create(
            name="Test Category", slug="test-category"
        )
        self.factory = RequestFactory()

    def _get_context(self, request):
        if not hasattr(request, "user"):
            request.user = AnonymousUser()
        return categories_tags_context(request)

    def test_popular_posts_ranking(self):
        # Create 3 posts
        # Post A: 10 views, 2 comments, 5 reactions.
        #   Old Score: 10 + 2*5 = 20
        #   New Score: 10 + 2*5 + 5*3 = 10 + 10 + 15 = 35
        post_a = BlogPost.objects.create(
            author=self.user,
            title="Post A",
            slug="post-a",
            status=BlogPost.Status.PUBLISHED,
            published_at=timezone.now(),
            view_count=10,
            category=self.category,
        )
        Comment.objects.create(
            post=post_a, author=self.user, body="C1", status=Comment.Status.APPROVED
        )
        Comment.objects.create(
            post=post_a, author=self.user, body="C2", status=Comment.Status.APPROVED
        )
        for _ in range(5):
            u = get_user_model().objects.create_user(
                email=f"user_a_{_}@example.com", password="p"
            )  # pyright: ignore[reportCallIssue]
            BlogPostReaction.objects.create(
                post=post_a, user=u, reaction=BlogPostReaction.Reaction.ALKIS
            )

        # Post B: 50 views, 0 comments, 0 reactions.
        #   Old Score: 50 + 0*5 = 50
        #   New Score: 50 + 0*5 + 0*3 = 50
        post_b = BlogPost.objects.create(
            author=self.user,
            title="Post B",
            slug="post-b",
            status=BlogPost.Status.PUBLISHED,
            published_at=timezone.now(),
            view_count=50,
            category=self.category,
        )

        # Post C: 5 views, 5 comments, 2 reactions.
        #   Old Score: 5 + 5*5 = 30
        #   New Score: 5 + 5*5 + 2*3 = 5 + 25 + 6 = 36
        post_c = BlogPost.objects.create(
            author=self.user,
            title="Post C",
            slug="post-c",
            status=BlogPost.Status.PUBLISHED,
            published_at=timezone.now(),
            view_count=5,
            category=self.category,
        )
        for _ in range(5):
            Comment.objects.create(
                post=post_c,
                author=self.user,
                body=f"C{_}",
                status=Comment.Status.APPROVED,
            )
        for _ in range(2):
            u = get_user_model().objects.create_user(
                email=f"user_c_{_}@example.com", password="p"
            )  # pyright: ignore[reportCallIssue]
            BlogPostReaction.objects.create(
                post=post_c, user=u, reaction=BlogPostReaction.Reaction.ALKIS
            )

        request = self.factory.get("/")
        context = self._get_context(request)
        popular_posts = context["nav_popular_posts"]

        # New logic: Post B (50), Post C (36), Post A (35)
        self.assertEqual(popular_posts[0].title, "Post B")
        self.assertEqual(popular_posts[1].title, "Post C")
        self.assertEqual(popular_posts[2].title, "Post A")

        # Adjust Post A to have 10 reactions and 11 views
        # New Score A: 11 + 2*5 + 10*3 = 11 + 10 + 30 = 51.
        # Score B: 50
        # Score C: 36

        post_a.view_count = 11
        post_a.save()
        for _ in range(5, 10):
            u = get_user_model().objects.create_user(
                email=f"user_a_{_}@example.com", password="p"
            )  # pyright: ignore[reportCallIssue]
            BlogPostReaction.objects.create(
                post=post_a, user=u, reaction=BlogPostReaction.Reaction.ALKIS
            )

        cache.clear()
        context = self._get_context(request)
        popular_posts = context["nav_popular_posts"]

        # After MY CHANGE (NEW logic): Post A (51) > Post B (50) > Post C (36)
        self.assertEqual(popular_posts[0].title, "Post A")
        self.assertEqual(popular_posts[1].title, "Post B")
        self.assertEqual(popular_posts[2].title, "Post C")
