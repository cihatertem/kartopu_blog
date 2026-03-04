from django.contrib.auth import get_user_model
from django.test import TestCase

from blog.models import BlogPost, Category
from comments.models import Comment

User = get_user_model()


class CommentModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="testuser@example.com",
            password="testpassword",
            first_name="Test",
            last_name="User",
        )
        self.category = Category.objects.create(name="Test Category", slug="test-cat")
        self.post = BlogPost.objects.create(
            title="Test Post",
            author=self.user,
            category=self.category,
            status=BlogPost.Status.PUBLISHED,
        )
        self.comment = Comment.objects.create(
            post=self.post,
            author=self.user,
            body="This is a test comment",
            status=Comment.Status.PENDING,
        )

    def test_str_representation(self):
        expected_str = f"Test Post - {self.user.full_name}"
        self.assertEqual(str(self.comment), expected_str)

    def test_is_public_property(self):
        # Initial status is PENDING
        self.assertFalse(self.comment.is_public)

        # Change to APPROVED
        self.comment.status = Comment.Status.APPROVED
        self.comment.save()
        self.assertTrue(self.comment.is_public)

        # Change to REJECTED
        self.comment.status = Comment.Status.REJECTED
        self.comment.save()
        self.assertFalse(self.comment.is_public)

        # Change to SPAM
        self.comment.status = Comment.Status.SPAM
        self.comment.save()
        self.assertFalse(self.comment.is_public)
