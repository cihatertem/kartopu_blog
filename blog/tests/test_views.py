import json
from unittest.mock import patch

from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from blog.models import BlogPost, BlogPostReaction, Category, Tag
from blog.views import (
    _build_comment_context,
    _build_reaction_context,
    _extract_social_avatar_url,
    _normalize_avatar_url,
    archive_index,
    post_reaction,
)

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

        self.published_post.refresh_from_db()
        self.assertEqual(self.published_post.view_count, 1)

    def test_post_detail_view_draft_404(self):
        url = reverse("blog:post_detail", kwargs={"slug": self.draft_post.slug})
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 404)

    def test_post_preview_unauthenticated(self):
        url = reverse("blog:post_preview", kwargs={"slug": self.draft_post.slug})
        response = self.client.get(url, follow=True)
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
        from unittest.mock import patch

        with patch("blog.views.SearchVector"):
            url = reverse("blog:search_results")

            response = self.client.get(url, follow=True)
            self.assertEqual(response.status_code, 200)

            with patch("blog.views.published_posts_queryset") as mock_qs:
                mock_qs.return_value.none.return_value = BlogPost.objects.none()
                response = self.client.get(url, {"q": "Published"}, follow=True)
                self.assertEqual(response.status_code, 200)

    def test_search_results_websearch_and_cache(self):
        from unittest.mock import MagicMock, patch

        from django.core.cache import cache

        cache.clear()

        # FTS queries we want to test
        queries = [
            "temettü yatırım",  # Standard AND
            '"finansal özgürlük"',  # Exact Phrase
            "hisse -vergi",  # Negation
            "bist100 OR sp500",  # OR logic
        ]

        url = reverse("blog:search_results")

        for q in queries:
            with patch("blog.views.SearchQuery") as MockSearchQuery:
                with patch("blog.views.get_page_obj") as mock_get_page_obj:
                    # Mocking page_obj to return a dummy paginated list of our published post
                    mock_page = MagicMock()
                    mock_page.object_list = [self.published_post]
                    mock_page.paginator.count = 1
                    mock_get_page_obj.return_value = mock_page

                    response = self.client.get(url, {"q": q}, follow=True)
                    self.assertEqual(response.status_code, 200)

                    # Ensure SearchQuery was called with the exact input string and websearch type
                    MockSearchQuery.assert_called_with(
                        q, search_type="websearch", config="turkish"
                    )

            # Now test cache hits and assertNumQueries
            with patch("blog.views.SearchQuery") as MockSearchQuery:
                # Mock published_posts_queryset to prevent executing any further query logic
                # 1 query for base_qs.in_bulk(post_ids)
                # plus other queries required for template rendering (e.g., seo data, global site context)
                # But it shouldn't execute FTS SearchRank queries.
                # Let's mock the render to only count view queries if we strictly want 1,
                # or just assert NumQueries doesn't include the FTS search query by asserting MockSearchQuery is not called
                response = self.client.get(url, {"q": q}, follow=True)
                self.assertEqual(response.status_code, 200)
                # It shouldn't evaluate FTS logic again
                MockSearchQuery.assert_not_called()

    def test_search_results_view_malicious_payloads(self):

        from unittest.mock import MagicMock, patch

        payloads = [
            "a|echo | dveq38oqyl||echo",
            "1%>\"%>'%>zj<%=7337*6123%>zj",
            "'';'()(null",
            "apple & | ! orange",
        ]

        url = reverse("blog:search_results")

        with patch("blog.views.get_page_obj") as mock_get_page_obj:
            mock_page = MagicMock()
            mock_page.object_list = []
            mock_page.paginator.count = 0
            mock_get_page_obj.return_value = mock_page
            for payload in payloads:
                response = self.client.get(url, {"q": payload}, follow=True)
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

    @patch("accounts.signals._download_and_save_social_avatar")
    def test_post_reaction_invalid_reaction(self, mock_download_avatar):
        SocialAccount.objects.create(user=self.reader, provider="google", uid="123")
        url = reverse("blog:post_reaction", kwargs={"slug": self.published_post.slug})

        request = self.factory.post(url, {"reaction": "fake_reaction"})
        request.user = self.reader

        response = post_reaction(request, slug=self.published_post.slug)
        self.assertEqual(response.status_code, 400)

    @patch("accounts.signals._download_and_save_social_avatar")
    def test_post_reaction_add(self, mock_download_avatar):
        SocialAccount.objects.create(user=self.reader, provider="google", uid="123")
        url = reverse("blog:post_reaction", kwargs={"slug": self.published_post.slug})

        request = self.factory.post(
            url, {"reaction": BlogPostReaction.Reaction.KALP.value}
        )
        request.user = self.reader
        response = post_reaction(request, slug=self.published_post.slug)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["selected"], BlogPostReaction.Reaction.KALP.value)
        self.assertEqual(data["counts"].get(BlogPostReaction.Reaction.KALP.value), 1)

    @patch("accounts.signals._download_and_save_social_avatar")
    def test_post_reaction_remove_empty(self, mock_download_avatar):
        SocialAccount.objects.create(user=self.reader, provider="google", uid="123")
        url = reverse("blog:post_reaction", kwargs={"slug": self.published_post.slug})

        # Add initially
        request = self.factory.post(
            url, {"reaction": BlogPostReaction.Reaction.KALP.value}
        )
        request.user = self.reader
        post_reaction(request, slug=self.published_post.slug)

        # Remove with empty
        request = self.factory.post(url, {"reaction": ""})
        request.user = self.reader
        response = post_reaction(request, slug=self.published_post.slug)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["selected"], "")
        self.assertEqual(data["counts"].get(BlogPostReaction.Reaction.KALP.value), None)

    @patch("accounts.signals._download_and_save_social_avatar")
    def test_post_reaction_remove_toggle(self, mock_download_avatar):
        SocialAccount.objects.create(user=self.reader, provider="google", uid="123")
        url = reverse("blog:post_reaction", kwargs={"slug": self.published_post.slug})

        # Add initially
        request = self.factory.post(
            url, {"reaction": BlogPostReaction.Reaction.KALP.value}
        )
        request.user = self.reader
        post_reaction(request, slug=self.published_post.slug)

        # Remove by toggling (sending same again)
        request = self.factory.post(
            url, {"reaction": BlogPostReaction.Reaction.KALP.value}
        )
        request.user = self.reader
        response = post_reaction(request, slug=self.published_post.slug)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["selected"], "")
        self.assertEqual(data["counts"].get(BlogPostReaction.Reaction.KALP.value), None)

    @patch("accounts.signals._download_and_save_social_avatar")
    def test_post_reaction_change(self, mock_download_avatar):
        SocialAccount.objects.create(user=self.reader, provider="google", uid="123")
        url = reverse("blog:post_reaction", kwargs={"slug": self.published_post.slug})

        # Add initially
        request = self.factory.post(
            url, {"reaction": BlogPostReaction.Reaction.KALP.value}
        )
        request.user = self.reader
        post_reaction(request, slug=self.published_post.slug)

        # Change
        request = self.factory.post(
            url, {"reaction": BlogPostReaction.Reaction.ROKET.value}
        )
        request.user = self.reader
        response = post_reaction(request, slug=self.published_post.slug)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["selected"], BlogPostReaction.Reaction.ROKET.value)
        self.assertEqual(data["counts"].get(BlogPostReaction.Reaction.ROKET.value), 1)
        self.assertEqual(data["counts"].get(BlogPostReaction.Reaction.KALP.value), None)

    @patch("accounts.signals._download_and_save_social_avatar")
    def test_post_reaction_bad_slug(self, mock_download_avatar):
        SocialAccount.objects.create(user=self.reader, provider="google", uid="123")
        url = reverse("blog:post_reaction", kwargs={"slug": "missing"})
        request = self.factory.post(
            url, {"reaction": BlogPostReaction.Reaction.KALP.value}
        )
        request.user = self.reader

        from django.http import Http404

        with self.assertRaises(Http404):
            post_reaction(request, slug="missing")


class ViewHelperTests(TestCase):
    def test_normalize_avatar_url(self):
        self.assertEqual(_normalize_avatar_url(None), "")
        self.assertEqual(
            _normalize_avatar_url("http://pbs.twimg.com/x.jpg"),
            "https://pbs.twimg.com/x.jpg",
        )
        self.assertEqual(
            _normalize_avatar_url("https://example.com/x.jpg"),
            "https://example.com/x.jpg",
        )
        self.assertEqual(_normalize_avatar_url("invalid_url"), "")

    def test_extract_social_avatar_url(self):
        self.assertEqual(_extract_social_avatar_url(None), "")
        self.assertEqual(
            _extract_social_avatar_url({"picture": "http://x"}), "http://x"
        )
        self.assertEqual(
            _extract_social_avatar_url({"pictureUrl": "http://y"}), "http://y"
        )
        self.assertEqual(
            _extract_social_avatar_url({"avatar_url": "http://z"}), "http://z"
        )
        self.assertEqual(
            _extract_social_avatar_url({"image": {"url": "http://i"}}), "http://i"
        )

    def test_archive_index(self):
        user = User.objects.create_user(
            email="archive@example.com", password="password"
        )
        BlogPost.objects.create(
            title="Arch1",
            author=user,
            status=BlogPost.Status.PUBLISHED,
            published_at=timezone.now(),
        )

        request = RequestFactory().get("/archive/")

        with patch("blog.views.render") as mock_render:
            mock_render.return_value = "mock_html"
            resp = archive_index(request)
            self.assertEqual(resp, "mock_html")

    def test_build_reaction_context(self):
        user = User.objects.create_user(email="react@example.com", password="password")
        post = BlogPost.objects.create(
            title="T1",
            author=user,
            status=BlogPost.Status.PUBLISHED,
            published_at=timezone.now(),
        )

        BlogPostReaction.objects.create(
            post=post, user=user, reaction=BlogPostReaction.Reaction.KALP.value
        )

        request = RequestFactory().get("/")
        request.user = user

        ctx = _build_reaction_context(request, post)
        self.assertEqual(ctx["user_reaction"], BlogPostReaction.Reaction.KALP.value)
        self.assertEqual(ctx["user_reaction_label"], "Sevgi")

    @patch("accounts.signals._download_and_save_social_avatar")
    def test_build_comment_context_avatar_fallback(self, mock_download_avatar):
        user = User.objects.create_user(email="comm@example.com", password="password")
        post = BlogPost.objects.create(
            title="T2",
            author=user,
            status=BlogPost.Status.PUBLISHED,
            published_at=timezone.now(),
        )

        from comments.models import Comment

        Comment.objects.create(
            post=post, author=user, body="c1", status=Comment.Status.APPROVED
        )

        from allauth.socialaccount.models import SocialApp

        SocialApp.objects.create(provider="google", name="google", client_id="123")
        SocialAccount.objects.create(
            user=user,
            provider="google",
            uid="12",
            extra_data={"picture": "http://g.com/1"},
        )

        request = RequestFactory().get("/")
        request.user = user

        with (
            patch(
                "allauth.socialaccount.models.SocialAccount.get_avatar_url",
                return_value="",
            ),
            patch(
                "blog.views._extract_social_profile_url",
                return_value="https://twitter.com/testuser",
            ),
        ):
            ctx = _build_comment_context(request, post)
        self.assertEqual(ctx["comment_total"], 1)
        comments = ctx["comment_page_obj"].object_list
        self.assertEqual(comments[0].social_avatar_url, "http://g.com/1")
        self.assertEqual(comments[0].social_profile_url, "https://twitter.com/testuser")

    def test_extract_social_profile_url_exception_handled(self):
        """Test that _extract_social_profile_url safely handles exceptions when getting the profile url."""
        from unittest.mock import MagicMock

        from blog.views import _extract_social_profile_url

        account = MagicMock()
        account.provider = "unknown_provider"
        account.extra_data = {}
        account.get_profile_url.side_effect = Exception("Test Exception")

        with self.assertLogs("blog.views", level="ERROR"):
            result = _extract_social_profile_url(account)

        self.assertEqual(result, "")

    @patch("accounts.signals._download_and_save_social_avatar")
    def test_build_comment_context_social_profile_url(self, mock_download_avatar):
        """Test that _build_comment_context correctly fetches and assigns social_profile_url."""
        user = User.objects.create_user(email="profiletest@example.com", password="pwd")
        post = BlogPost.objects.create(
            title="Profile Post",
            slug="profile-post",
            author=user,
            status=BlogPost.Status.PUBLISHED,
        )
        from comments.models import Comment

        Comment.objects.create(
            post=post,
            author=user,
            body="Profile comment",
            status=Comment.Status.APPROVED,
        )

        SocialAccount.objects.create(
            user=user,
            provider="github",
            uid="9999",
            extra_data={"html_url": "https://github.com/profiletest"},
        )

        request = RequestFactory().get("/")
        request.user = user

        with patch(
            "allauth.socialaccount.models.SocialAccount.get_avatar_url", return_value=""
        ):
            ctx = _build_comment_context(request, post)

        comments = ctx["comment_page_obj"].object_list
        self.assertEqual(len(comments), 1)
        self.assertEqual(
            comments[0].social_profile_url, "https://github.com/profiletest"
        )
