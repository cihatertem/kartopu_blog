from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from blog.models import BlogPost, Category
from core.services.blog import published_posts_queryset


class BlogServicesTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(email="test@user.com")
        self.category = Category.objects.create(name="Tech", slug="tech")

        BlogPost.objects.create(
            author=self.user,
            title="Published Post",
            slug="published",
            status=BlogPost.Status.PUBLISHED,
            category=self.category,
            published_at=timezone.now(),
        )
        BlogPost.objects.create(
            author=self.user,
            title="Draft Post",
            slug="draft",
            status=BlogPost.Status.DRAFT,
            category=self.category,
        )

    def test_published_posts_queryset(self):
        qs = published_posts_queryset()
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().title, "Published Post")

    def test_published_posts_queryset_no_tags(self):
        qs = published_posts_queryset(include_tags=False)
        self.assertEqual(qs.count(), 1)
