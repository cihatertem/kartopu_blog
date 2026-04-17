import ipaddress
from unittest.mock import patch

from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from blog.models import BlogPost, Category
from comments.models import Comment
from comments.views import _get_comment_status, _validate_parent_comment
from core.models import SiteSettings

User = get_user_model()


class GetCommentStatusTests(TestCase):
    def setUp(self):
        class MockForm:
            def __init__(self, cleaned_data=None):
                self.cleaned_data = cleaned_data or {}

        self.MockForm = MockForm

    def test_staff_user_with_website_is_approved(self):
        # Even if a staff user leaves a website, it shouldn't be marked as spam
        form = self.MockForm(cleaned_data={"website": "https://example.com"})
        status = _get_comment_status(form, is_staff=True)
        self.assertEqual(status, Comment.Status.APPROVED)

    def test_staff_user_without_website_is_approved(self):
        form = self.MockForm(cleaned_data={})
        status = _get_comment_status(form, is_staff=True)
        self.assertEqual(status, Comment.Status.APPROVED)

    def test_regular_user_with_website_is_spam(self):
        form = self.MockForm(cleaned_data={"website": "https://spam.com"})
        status = _get_comment_status(form, is_staff=False)
        self.assertEqual(status, Comment.Status.SPAM)

    def test_regular_user_without_website_is_pending(self):
        form = self.MockForm(cleaned_data={})
        status = _get_comment_status(form, is_staff=False)
        self.assertEqual(status, Comment.Status.PENDING)


@override_settings(RATELIMIT_ENABLE=False)
class PostCommentTests(TestCase):
    def setUp(self):
        cache.clear()
        self.staff_user = User.objects.create_user(
            email="staff2@example.com", password="password", is_staff=True
        )
        self.regular_user = User.objects.create_user(
            email="user2@example.com", password="password"
        )
        self.category = Category.objects.create(
            name="Test Category 2", slug="test-category-2"
        )
        self.post = BlogPost.objects.create(
            title="Test Post 2",
            author=self.staff_user,
            category=self.category,
            status=BlogPost.Status.PUBLISHED,
        )
        self.client = Client(HTTP_HOST="localhost")
        self.url = reverse("comments:post_comment", kwargs={"post_id": self.post.id})

    def test_post_comment_unauthenticated(self):
        response = self.client.post(
            self.url,
            {"body": "Test comment"},
            follow=False,
            HTTP_HOST="localhost",
            secure=True,
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("account_login")))

    @patch("comments.views.SiteSettings.get_settings")
    def test_comments_disabled(self, mock_get_settings):
        mock_settings = SiteSettings()
        mock_settings.is_comments_enabled = False
        mock_get_settings.return_value = mock_settings

        self.client.login(email="staff2@example.com", password="password")
        response = self.client.post(
            self.url,
            {"body": "Test comment"},
            follow=False,
            HTTP_HOST="localhost",
            secure=True,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")

    def test_regular_user_without_social_account(self):
        self.client.login(email="user2@example.com", password="password")
        response = self.client.post(
            self.url,
            {"body": "Test comment"},
            follow=False,
            HTTP_HOST="localhost",
            secure=True,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.post.get_absolute_url())
        self.assertEqual(Comment.objects.count(), 0)

    def test_post_comment_logs_correct_ip(self):
        self.client.login(email="staff2@example.com", password="password")
        with override_settings(TRUSTED_PROXY_NETS=[ipaddress.ip_network("10.0.0.0/8")]):
            response = self.client.post(
                self.url,
                {"body": "IP test comment"},
                follow=False,
                HTTP_HOST="localhost",
                secure=True,
                REMOTE_ADDR="10.0.0.5",
                HTTP_X_FORWARDED_FOR="203.0.113.195",
            )
        self.assertEqual(response.status_code, 302)
        comment = Comment.objects.get(body="IP test comment")
        # Currently this fails because it logs 10.0.0.5
        self.assertEqual(comment.ip_address, "203.0.113.195")

    def test_post_comment_logs_correct_user_agent(self):
        self.client.login(email="staff2@example.com", password="password")
        long_ua = "Mozilla/5.0 " + ("a" * 600)
        self.client.post(
            self.url,
            {"body": "UA test comment"},
            follow=False,
            HTTP_HOST="localhost",
            secure=True,
            HTTP_USER_AGENT=long_ua,
        )
        comment = Comment.objects.get(body="UA test comment")
        self.assertEqual(len(comment.user_agent), 500)
        self.assertTrue(comment.user_agent.startswith("Mozilla/5.0"))

    @patch("accounts.signals._download_and_save_social_avatar")
    def test_regular_user_with_social_account(self, mock_download_avatar):
        SocialAccount.objects.create(user=self.regular_user, provider="google")
        self.client.login(email="user2@example.com", password="password")

        response = self.client.post(
            self.url,
            {"body": "Social comment"},
            follow=False,
            HTTP_HOST="localhost",
            secure=True,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.post.get_absolute_url())

        self.assertEqual(Comment.objects.count(), 1)
        comment = Comment.objects.first()
        self.assertEqual(comment.status, Comment.Status.PENDING)
        self.assertEqual(comment.social_provider, "google")
        self.assertEqual(comment.author, self.regular_user)
        self.assertEqual(comment.body, "Social comment")

    def test_staff_user_auto_approve(self):
        self.client.login(email="staff2@example.com", password="password")
        response = self.client.post(
            self.url,
            {"body": "Staff comment"},
            follow=False,
            HTTP_HOST="localhost",
            secure=True,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.post.get_absolute_url())

        self.assertEqual(Comment.objects.count(), 1)
        comment = Comment.objects.first()
        self.assertEqual(comment.status, Comment.Status.APPROVED)
        self.assertEqual(comment.author, self.staff_user)

    @patch("accounts.signals._download_and_save_social_avatar")
    def test_honeypot_spam(self, mock_download_avatar):
        SocialAccount.objects.create(user=self.regular_user, provider="google")
        self.client.login(email="user2@example.com", password="password")
        response = self.client.post(
            self.url,
            {"body": "Spam comment", "website": "http://spam.com"},
            follow=False,
            HTTP_HOST="localhost",
            secure=True,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.post.get_absolute_url())

        self.assertEqual(Comment.objects.count(), 1)
        comment = Comment.objects.first()
        self.assertEqual(comment.status, Comment.Status.SPAM)

    def test_invalid_form_body(self):
        self.client.login(email="staff2@example.com", password="password")
        response = self.client.post(
            self.url, {"body": ""}, follow=False, HTTP_HOST="localhost", secure=True
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.post.get_absolute_url())

        self.assertEqual(Comment.objects.count(), 0)

    def test_parent_comment(self):
        parent_comment = Comment.objects.create(
            post=self.post,
            author=self.staff_user,
            body="Parent comment",
            status=Comment.Status.APPROVED,
        )

        self.client.login(email="staff2@example.com", password="password")
        response = self.client.post(
            self.url,
            {"body": "Reply comment", "parent_id": parent_comment.id},
            follow=False,
            HTTP_HOST="localhost",
            secure=True,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.post.get_absolute_url())

        self.assertEqual(Comment.objects.count(), 2)
        reply = Comment.objects.exclude(id=parent_comment.id).first()
        self.assertEqual(reply.parent, parent_comment)

    def test_invalid_parent_comment(self):
        parent_comment = Comment.objects.create(
            post=self.post,
            author=self.staff_user,
            body="Parent comment",
            status=Comment.Status.PENDING,
        )

        self.client.login(email="staff2@example.com", password="password")
        response = self.client.post(
            self.url,
            {"body": "Reply comment", "parent_id": parent_comment.id},
            follow=False,
            HTTP_HOST="localhost",
            secure=True,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.post.get_absolute_url())

        self.assertEqual(Comment.objects.count(), 1)

    def test_invalid_parent_comment_different_post(self):
        other_post = BlogPost.objects.create(
            title="Other Post",
            author=self.staff_user,
            category=self.category,
            status=BlogPost.Status.PUBLISHED,
        )
        parent_comment = Comment.objects.create(
            post=other_post,
            author=self.staff_user,
            body="Parent comment",
            status=Comment.Status.APPROVED,
        )

        self.client.login(email="staff2@example.com", password="password")
        response = self.client.post(
            self.url,
            {"body": "Reply comment", "parent_id": parent_comment.id},
            follow=False,
            HTTP_HOST="localhost",
            secure=True,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.post.get_absolute_url())

        self.assertEqual(Comment.objects.count(), 1)
        self.assertFalse(Comment.objects.filter(body="Reply comment").exists())

    def test_invalid_parent_comment_nonexistent(self):
        self.client.login(email="staff2@example.com", password="password")
        response = self.client.post(
            self.url,
            {"body": "Reply comment", "parent_id": 99999},
            follow=False,
            HTTP_HOST="localhost",
            secure=True,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.post.get_absolute_url())

        self.assertEqual(Comment.objects.count(), 0)

    @patch("comments.views.ratelimit")
    def test_rate_limit(self, mock_ratelimit):
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.http import HttpRequest

        from comments.views import post_comment

        request = HttpRequest()
        request.method = "POST"
        request.limited = True
        request.user = self.staff_user
        request.POST = {"body": "Rate limited comment"}

        setattr(request, "session", "session")
        messages = FallbackStorage(request)
        setattr(request, "_messages", messages)

        response = post_comment(request, self.post.id)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.post.get_absolute_url())
        self.assertEqual(Comment.objects.count(), 0)

    def test_post_comment_non_published_post(self):
        draft_post = BlogPost.objects.create(
            title="Draft Post",
            author=self.staff_user,
            category=self.category,
            status=BlogPost.Status.DRAFT,
        )
        self.client.login(email="staff2@example.com", password="password")
        response = self.client.post(
            reverse("comments:post_comment", kwargs={"post_id": draft_post.id}),
            {"body": "Should not work"},
            follow=False,
            HTTP_HOST="localhost",
            secure=True,
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(Comment.objects.filter(post=draft_post).count(), 0)

    def test_post_comment_nonexistent_post(self):
        import uuid

        random_uuid = uuid.uuid4()
        self.client.login(email="staff2@example.com", password="password")
        response = self.client.post(
            reverse("comments:post_comment", kwargs={"post_id": random_uuid}),
            {"body": "Should not work"},
            follow=False,
            HTTP_HOST="localhost",
            secure=True,
        )
        self.assertEqual(response.status_code, 404)


class ValidateParentCommentTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            email="staff3@example.com", password="password", is_staff=True
        )
        self.category = Category.objects.create(
            name="Test Category 3", slug="test-category-3"
        )
        self.post = BlogPost.objects.create(
            title="Test Post 3",
            author=self.staff_user,
            category=self.category,
            status=BlogPost.Status.PUBLISHED,
        )

    def test_no_parent_id(self):
        parent, is_valid = _validate_parent_comment(None, self.post)
        self.assertIsNone(parent)
        self.assertTrue(is_valid)

        parent, is_valid = _validate_parent_comment("", self.post)
        self.assertIsNone(parent)
        self.assertTrue(is_valid)

    def test_valid_parent_comment(self):
        comment = Comment.objects.create(
            post=self.post,
            author=self.staff_user,
            body="Valid parent",
            status=Comment.Status.APPROVED,
        )
        parent, is_valid = _validate_parent_comment(comment.id, self.post)
        self.assertEqual(parent, comment)
        self.assertTrue(is_valid)

    def test_invalid_parent_comment_status(self):
        pending_comment = Comment.objects.create(
            post=self.post,
            author=self.staff_user,
            body="Pending parent",
            status=Comment.Status.PENDING,
        )
        parent, is_valid = _validate_parent_comment(pending_comment.id, self.post)
        self.assertIsNone(parent)
        self.assertFalse(is_valid)

        spam_comment = Comment.objects.create(
            post=self.post,
            author=self.staff_user,
            body="Spam parent",
            status=Comment.Status.SPAM,
        )
        parent, is_valid = _validate_parent_comment(spam_comment.id, self.post)
        self.assertIsNone(parent)
        self.assertFalse(is_valid)

    def test_invalid_parent_comment_wrong_post(self):
        other_post = BlogPost.objects.create(
            title="Other Post 3",
            author=self.staff_user,
            category=self.category,
            status=BlogPost.Status.PUBLISHED,
        )
        comment = Comment.objects.create(
            post=other_post,
            author=self.staff_user,
            body="Other post parent",
            status=Comment.Status.APPROVED,
        )
        parent, is_valid = _validate_parent_comment(comment.id, self.post)
        self.assertIsNone(parent)
        self.assertFalse(is_valid)

    def test_nonexistent_parent_id(self):
        parent, is_valid = _validate_parent_comment(99999, self.post)
        self.assertIsNone(parent)
        self.assertFalse(is_valid)


class CommentModerationTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            email="staff@example.com", password="password", is_staff=True
        )
        self.regular_user = User.objects.create_user(
            email="user@example.com", password="password"
        )
        self.category = Category.objects.create(
            name="Test Category", slug="test-category"
        )
        self.post = BlogPost.objects.create(
            title="Test Post",
            author=self.staff_user,
            category=self.category,
            status=BlogPost.Status.PUBLISHED,
        )
        self.comment = Comment.objects.create(
            post=self.post,
            author=self.regular_user,
            body="This is a test comment.",
            status=Comment.Status.PENDING,
        )
        self.client = Client(HTTP_HOST="localhost")

    def test_moderate_comment_approve_by_staff(self):
        self.client.login(email="staff@example.com", password="password")
        url = reverse(
            "comments:moderate_comment", kwargs={"comment_id": self.comment.id}
        )
        self.client.post(
            url,
            {"action": "approve", "csrfmiddlewaretoken": "test"},
            follow=True,
            HTTP_HOST="localhost",
            secure=True,
        )
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.status, Comment.Status.APPROVED)

    def test_moderate_comment_pending_by_staff(self):
        self.comment.status = Comment.Status.APPROVED
        self.comment.save()

        self.client.login(email="staff@example.com", password="password")
        url = reverse(
            "comments:moderate_comment", kwargs={"comment_id": self.comment.id}
        )
        self.client.post(
            url,
            {"action": "pending", "csrfmiddlewaretoken": "test"},
            follow=True,
            HTTP_HOST="localhost",
            secure=True,
        )
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.status, Comment.Status.PENDING)

    def test_moderate_comment_delete_by_staff(self):
        self.client.login(email="staff@example.com", password="password")
        url = reverse(
            "comments:moderate_comment", kwargs={"comment_id": self.comment.id}
        )
        self.client.post(
            url,
            {"action": "delete", "csrfmiddlewaretoken": "test"},
            follow=True,
            HTTP_HOST="localhost",
            secure=True,
        )
        with self.assertRaises(Comment.DoesNotExist):
            self.comment.refresh_from_db()

    def test_moderate_comment_unauthorized_user(self):
        self.client.login(email="user@example.com", password="password")
        url = reverse(
            "comments:moderate_comment", kwargs={"comment_id": self.comment.id}
        )
        self.client.post(
            url,
            {"action": "approve", "csrfmiddlewaretoken": "test"},
            follow=True,
            HTTP_HOST="localhost",
            secure=True,
        )
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.status, Comment.Status.PENDING)

    def test_moderate_comment_unauthenticated_user(self):
        url = reverse(
            "comments:moderate_comment", kwargs={"comment_id": self.comment.id}
        )
        self.client.post(
            url,
            {"action": "approve", "csrfmiddlewaretoken": "test"},
            follow=True,
            HTTP_HOST="localhost",
            secure=True,
        )
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.status, Comment.Status.PENDING)

    def test_moderate_comment_invalid_action(self):
        self.client.login(email="staff@example.com", password="password")
        url = reverse(
            "comments:moderate_comment", kwargs={"comment_id": self.comment.id}
        )
        response = self.client.post(
            url,
            {"action": "invalid_action", "csrfmiddlewaretoken": "test"},
            follow=False,
            HTTP_HOST="localhost",
            secure=True,
        )
        self.assertEqual(response.status_code, 302)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.status, Comment.Status.PENDING)
