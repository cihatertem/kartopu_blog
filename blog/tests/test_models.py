from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils.text import slugify

from blog.models import KARTOPU_MONEY_BASE_URL, BlogPost


class BlogPostModelTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            email="author@example.com",
            password="testpass123",
            first_name="Author",
        )

    def test_slug_auto_generated(self):
        post = BlogPost(author=self.user, title="My Awesome Blog Post")
        post.save()

        expected_slug = slugify("My Awesome Blog Post")
        self.assertEqual(post.slug, expected_slug)
        self.assertEqual(
            post.canonical_url, f"{KARTOPU_MONEY_BASE_URL}/blog/{expected_slug}/"
        )

    def test_canonical_url_auto_generated(self):
        post = BlogPost(author=self.user, title="Another Post", slug="custom-slug")
        post.save()

        self.assertEqual(post.slug, "custom-slug")
        self.assertEqual(
            post.canonical_url, f"{KARTOPU_MONEY_BASE_URL}/blog/custom-slug/"
        )

    def test_canonical_url_not_overwritten_if_provided(self):
        post = BlogPost(
            author=self.user,
            title="Post with explicit canonical",
            canonical_url="https://example.com/original-post/",
        )
        post.save()

        self.assertEqual(post.canonical_url, "https://example.com/original-post/")

    def test_slug_not_overwritten_if_provided(self):
        post = BlogPost(author=self.user, title="Post title", slug="explicit-slug")
        post.save()

        self.assertEqual(post.slug, "explicit-slug")
