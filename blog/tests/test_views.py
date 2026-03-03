import json

from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from blog.models import BlogPost, BlogPostReaction, Category, Tag
from blog.views import post_reaction

User = get_user_model()


class BlogViewsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email="testauthor@example.com", password="password"
        )
        self.reader = User.objects.create_user(
            email="reader@example.com", password="password"
        )

        self.category = Category.objects.create(name="Tech")
        self.tag = Tag.objects.create(name="Python")

        self.published_post = BlogPost.objects.create(
            title="A Published Post",
            author=self.user,
            category=self.category,
            content="Hello world",
            status=BlogPost.Status.PUBLISHED,
            published_at=timezone.now(),
        )
        self.published_post.tags.add(self.tag)

        self.draft_post = BlogPost.objects.create(
            title="A Draft Post",
            author=self.user,
            category=self.category,
            content="WIP",
            status=BlogPost.Status.DRAFT,
        )

    def test_post_list_view(self):
        response = self.client.get(reverse("blog:post_list"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A Published Post")
        self.assertNotContains(response, "A Draft Post")

    def test_post_detail_view_published(self):
        url = reverse("blog:post_detail", kwargs={"slug": self.published_post.slug})
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A Published Post")

        # Test view count increases
        self.published_post.refresh_from_db()
        self.assertEqual(self.published_post.view_count, 1)

    def test_post_detail_view_draft_404(self):
        url = reverse("blog:post_detail", kwargs={"slug": self.draft_post.slug})
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 404)

    def test_post_preview_unauthenticated(self):
        url = reverse("blog:post_preview", kwargs={"slug": self.draft_post.slug})
        response = self.client.get(url, follow=True)
        # Login view is disabled in test or returns 404, we just check the redirect chain
        redirect_chain = getattr(response, "redirect_chain", [])
        has_login_redirect = any(
            r[0].startswith("/accounts/login/") for r in redirect_chain
        )
        self.assertTrue(has_login_redirect)

    def test_post_preview_authenticated_author(self):
        self.client.force_login(self.user)
        url = reverse("blog:post_preview", kwargs={"slug": self.draft_post.slug})
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A Draft Post")

    def test_post_preview_authenticated_non_author(self):
        self.client.force_login(self.reader)
        url = reverse("blog:post_preview", kwargs={"slug": self.draft_post.slug})
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 403)  # PermissionDenied

    def test_archive_detail_view(self):
        year = self.published_post.published_at.year
        month = self.published_post.published_at.month
        url = reverse("blog:archive_detail", kwargs={"year": year, "month": month})
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A Published Post")

    def test_category_detail_view(self):
        url = reverse("blog:category_detail", kwargs={"slug": self.category.slug})
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A Published Post")
        self.assertContains(response, "Tech")

    def test_tag_detail_view(self):
        url = reverse("blog:tag_detail", kwargs={"slug": self.tag.slug})
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A Published Post")
        self.assertContains(response, "#Python")

    def test_search_results_view(self):
        # Full text search in SQLite might fail if not enabled/installed.
        # We will mock it instead or skip if it causes NotImplementedError.
        from unittest.mock import patch

        with patch("blog.views.SearchVector") as mock_vector:
            url = reverse("blog:search_results")

            # Empty search
            response = self.client.get(url, follow=True)
            self.assertEqual(response.status_code, 200)

            # Valid search mocked
            with patch("blog.views.published_posts_queryset") as mock_qs:
                # Return empty list or fake qs to avoid execution
                mock_qs.return_value.none.return_value = BlogPost.objects.none()
                response = self.client.get(url, {"q": "Published"}, follow=True)
                self.assertEqual(response.status_code, 200)

    def test_post_reaction_requires_social_account(self):
        url = reverse("blog:post_reaction", kwargs={"slug": self.published_post.slug})
        request = self.factory.post(
            url, {"reaction": BlogPostReaction.Reaction.KALP.value}
        )
        request.user = self.reader  # User has no social account

        response = post_reaction(request, slug=self.published_post.slug)
        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertEqual(data["detail"], "Sosyal hesap gereklidir.")

    def test_post_reaction_invalid_reaction(self):
        SocialAccount.objects.create(user=self.reader, provider="google", uid="123")
        url = reverse("blog:post_reaction", kwargs={"slug": self.published_post.slug})

        request = self.factory.post(url, {"reaction": "fake_reaction"})
        request.user = self.reader

        response = post_reaction(request, slug=self.published_post.slug)
        self.assertEqual(response.status_code, 400)

    def test_post_reaction_success(self):
        SocialAccount.objects.create(user=self.reader, provider="google", uid="123")
        url = reverse("blog:post_reaction", kwargs={"slug": self.published_post.slug})

        # Add reaction
        request = self.factory.post(
            url, {"reaction": BlogPostReaction.Reaction.KALP.value}
        )
        request.user = self.reader
        response = post_reaction(request, slug=self.published_post.slug)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["selected"], BlogPostReaction.Reaction.KALP.value)
        self.assertEqual(data["counts"].get(BlogPostReaction.Reaction.KALP.value), 1)

        # Remove reaction by sending empty
        request = self.factory.post(url, {"reaction": ""})
        request.user = self.reader
        response = post_reaction(request, slug=self.published_post.slug)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["selected"], "")
        self.assertEqual(data["counts"].get(BlogPostReaction.Reaction.KALP.value), None)

        # Toggle reaction (send same one)
        request = self.factory.post(
            url, {"reaction": BlogPostReaction.Reaction.KALP.value}
        )
        request.user = self.reader
        post_reaction(request, slug=self.published_post.slug)  # Add

        request = self.factory.post(
            url, {"reaction": BlogPostReaction.Reaction.KALP.value}
        )
        request.user = self.reader
        response = post_reaction(request, slug=self.published_post.slug)  # Remove

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["selected"], "")

        # Change reaction
        request = self.factory.post(
            url, {"reaction": BlogPostReaction.Reaction.KALP.value}
        )
        request.user = self.reader
        post_reaction(request, slug=self.published_post.slug)  # Add

        request = self.factory.post(
            url, {"reaction": BlogPostReaction.Reaction.ROKET.value}
        )
        request.user = self.reader
        response = post_reaction(request, slug=self.published_post.slug)  # Change

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["selected"], BlogPostReaction.Reaction.ROKET.value)
        self.assertEqual(data["counts"].get(BlogPostReaction.Reaction.ROKET.value), 1)
