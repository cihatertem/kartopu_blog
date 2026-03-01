from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from blog.models import BlogPost, Category
from comments.models import Comment

User = get_user_model()


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
