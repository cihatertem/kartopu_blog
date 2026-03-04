from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from blog.models import BlogPost, Category
from comments.admin import CommentAdmin
from comments.models import Comment

User = get_user_model()


class MockRequest:
    pass


class CommentAdminTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.site = AdminSite()
        self.admin = CommentAdmin(Comment, self.site)

        self.user = User.objects.create_user(
            email="adminuser@example.com",
            password="testpassword",
            is_staff=True,
            is_superuser=True,
        )
        self.category = Category.objects.create(name="Admin Cat", slug="admin-cat")
        self.post = BlogPost.objects.create(
            title="Admin Post",
            author=self.user,
            category=self.category,
            status=BlogPost.Status.PUBLISHED,
        )
        self.comment1 = Comment.objects.create(
            post=self.post,
            author=self.user,
            body="First comment",
            status=Comment.Status.PENDING,
        )
        self.comment2 = Comment.objects.create(
            post=self.post,
            author=self.user,
            body="Second comment",
            status=Comment.Status.PENDING,
        )
        self.queryset = Comment.objects.all()

    def test_approve_comments_action(self):
        request = self.factory.post("/")
        self.admin.approve_comments(request, self.queryset)
        self.comment1.refresh_from_db()
        self.comment2.refresh_from_db()
        self.assertEqual(self.comment1.status, Comment.Status.APPROVED)
        self.assertEqual(self.comment2.status, Comment.Status.APPROVED)

    def test_reject_comments_action(self):
        request = self.factory.post("/")
        self.admin.reject_comments(request, self.queryset)
        self.comment1.refresh_from_db()
        self.comment2.refresh_from_db()
        self.assertEqual(self.comment1.status, Comment.Status.REJECTED)
        self.assertEqual(self.comment2.status, Comment.Status.REJECTED)

    def test_mark_spam_action(self):
        request = self.factory.post("/")
        self.admin.mark_spam(request, self.queryset)
        self.comment1.refresh_from_db()
        self.comment2.refresh_from_db()
        self.assertEqual(self.comment1.status, Comment.Status.SPAM)
        self.assertEqual(self.comment2.status, Comment.Status.SPAM)
