from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from blog.models import BlogPost, Category, Tag
from core.services.blog import published_posts_queryset


class BlogServicesTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(email="test@user.com")
        self.category = Category.objects.create(name="Tech", slug="tech")
        self.tag = Tag.objects.create(name="Django", slug="django")

        published_post = BlogPost.objects.create(
            author=self.user,
            title="Published Post",
            slug="published",
            status=BlogPost.Status.PUBLISHED,
            category=self.category,
            published_at=timezone.now(),
        )
        published_post.tags.add(self.tag)

        BlogPost.objects.create(
            author=self.user,
            title="Draft Post",
            slug="draft",
            status=BlogPost.Status.DRAFT,
            category=self.category,
        )

    def test_published_posts_queryset(self):
        with self.assertNumQueries(2):
            qs = published_posts_queryset()
            posts = list(qs)

        self.assertEqual(len(posts), 1)
        post = posts[0]
        self.assertEqual(post.title, "Published Post")

        with self.assertNumQueries(0):
            self.assertEqual(post.author.email, "test@user.com")
            self.assertEqual(post.category.name, "Tech")
            self.assertEqual(post.tags.all()[0].name, "Django")

    def test_published_posts_queryset_no_tags(self):
        with self.assertNumQueries(1):
            qs = published_posts_queryset(include_tags=False)
            posts = list(qs)

        self.assertEqual(len(posts), 1)
        post = posts[0]
        self.assertEqual(post.title, "Published Post")

        with self.assertNumQueries(0):
            self.assertEqual(post.author.email, "test@user.com")
            self.assertEqual(post.category.name, "Tech")

        with self.assertNumQueries(1):
            self.assertEqual(post.tags.all()[0].name, "Django")
