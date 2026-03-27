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

        self.published_post = BlogPost.objects.create(
            author=self.user,
            title="Published Post",
            slug="published",
            status=BlogPost.Status.PUBLISHED,
            category=self.category,
            published_at=timezone.now() - timezone.timedelta(days=1),
        )
        self.published_post.tags.add(self.tag)

        BlogPost.objects.create(
            author=self.user,
            title="Draft Post",
            slug="draft",
            status=BlogPost.Status.DRAFT,
            category=self.category,
        )

        BlogPost.objects.create(
            author=self.user,
            title="Archived Post",
            slug="archived",
            status=BlogPost.Status.ARCHIVED,
            category=self.category,
        )

        self.published_no_cat = BlogPost.objects.create(
            author=self.user,
            title="Published No Category",
            slug="published-no-cat",
            status=BlogPost.Status.PUBLISHED,
            category=None,
            published_at=timezone.now(),
        )

    def test_published_posts_queryset(self):
        with self.assertNumQueries(2):
            qs = published_posts_queryset()
            posts = list(qs)

        self.assertEqual(len(posts), 2)
        post = posts[0]
        self.assertEqual(post.title, "Published No Category")
        self.assertIsNone(post.category)

        post2 = posts[1]
        self.assertEqual(post2.title, "Published Post")

        with self.assertNumQueries(0):
            self.assertEqual(post2.author.email, "test@user.com")
            self.assertEqual(post2.category.name, "Tech")
            self.assertEqual(post2.tags.all()[0].name, "Django")

    def test_published_posts_queryset_no_tags(self):
        with self.assertNumQueries(1):
            qs = published_posts_queryset(include_tags=False)
            posts = list(qs)

        self.assertEqual(len(posts), 2)
        post = posts[1]
        self.assertEqual(post.title, "Published Post")

        with self.assertNumQueries(0):
            self.assertEqual(post.author.email, "test@user.com")
            self.assertEqual(post.category.name, "Tech")

        with self.assertNumQueries(1):
            self.assertEqual(post.tags.all()[0].name, "Django")

    def test_published_posts_queryset_excludes_non_published(self):
        qs = published_posts_queryset()
        self.assertEqual(qs.count(), 2)

        for post in qs:
            self.assertEqual(post.status, BlogPost.Status.PUBLISHED)

    def test_published_posts_queryset_ordering(self):
        posts = list(published_posts_queryset())

        self.assertEqual(posts[0].title, "Published No Category")
        self.assertEqual(posts[1].title, "Published Post")

        now = timezone.now()
        self.published_no_cat.published_at = now
        self.published_no_cat.save()

        BlogPost.objects.create(
            author=self.user,
            title="Same Date Newer",
            slug="same-date-newer",
            status=BlogPost.Status.PUBLISHED,
            published_at=now,
        )

        posts = list(published_posts_queryset())
        self.assertEqual(posts[0].title, "Same Date Newer")
        self.assertEqual(posts[1].title, "Published No Category")
        self.assertEqual(posts[2].title, "Published Post")

    def test_published_posts_queryset_no_category(self):
        posts = list(published_posts_queryset())
        no_cat_post = next(p for p in posts if p.slug == "published-no-cat")
        self.assertIsNone(no_cat_post.category)
