from unittest.mock import patch

from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from blog.models import BlogPost, Category
from comments.models import Comment
from core.models import SiteSettings

User = get_user_model()


class PostCommentTests(TestCase):
    def setUp(self):
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
        # Should redirect to login since @login_required is used
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("account_login")))

    @patch("comments.views.SiteSettings.get_settings")
    def test_comments_disabled(self, mock_get_settings):
        # Mock site settings to disable comments
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
        # Comment should not be created
        self.assertEqual(Comment.objects.count(), 0)

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

        # Comment should be created as PENDING
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

        # Comment should be created as APPROVED
        self.assertEqual(Comment.objects.count(), 1)
        comment = Comment.objects.first()
        self.assertEqual(comment.status, Comment.Status.APPROVED)
        self.assertEqual(comment.author, self.staff_user)

    @patch("accounts.signals._download_and_save_social_avatar")
    def test_honeypot_spam(self, mock_download_avatar):
        # Use regular user with social account to avoid staff auto-approve override
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

        # Comment should be created as SPAM
        self.assertEqual(Comment.objects.count(), 1)
        comment = Comment.objects.first()
        self.assertEqual(comment.status, Comment.Status.SPAM)

    def test_invalid_form_body(self):
        self.client.login(email="staff2@example.com", password="password")
        response = self.client.post(
            self.url, {"body": ""}, follow=False, HTTP_HOST="localhost", secure=True
        )  # Empty body is invalid
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.post.get_absolute_url())

        # Comment should not be created
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

        # Comment should be created with parent set
        self.assertEqual(Comment.objects.count(), 2)
        reply = Comment.objects.exclude(id=parent_comment.id).first()
        self.assertEqual(reply.parent, parent_comment)

    def test_invalid_parent_comment(self):
        # Parent comment pending, so it can't be replied to
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

        # Reply should not be created
        self.assertEqual(Comment.objects.count(), 1)

    @patch("comments.views.ratelimit")
    def test_rate_limit(self, mock_ratelimit):
        # Since the actual ratelimit decorator executes before our view logic,
        # we test the view logic that checks request.limited.
        # We simulate the ratelimit middleware setting limited=True.
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.http import HttpRequest

        from comments.views import post_comment

        request = HttpRequest()
        request.method = "POST"
        request.limited = True
        request.user = self.staff_user
        request.POST = {"body": "Rate limited comment"}

        # Setup messages framework on request
        setattr(request, "session", "session")
        messages = FallbackStorage(request)
        setattr(request, "_messages", messages)

        response = post_comment(request, self.post.id)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.post.get_absolute_url())
        self.assertEqual(Comment.objects.count(), 0)


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
