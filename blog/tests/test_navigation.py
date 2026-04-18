from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from blog.models import BlogPost, Category

User = get_user_model()


class PostNavigationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email="author@example.com", password="password"
        )
        self.category = Category.objects.create(name="Tech")

        self.post1 = BlogPost.objects.create(
            title="First Post",
            slug="first-post",
            author=self.user,
            category=self.category,
            status=BlogPost.Status.PUBLISHED,
            published_at=timezone.now() - timezone.timedelta(days=2),
        )
        self.post2 = BlogPost.objects.create(
            title="Second Post",
            slug="second-post",
            author=self.user,
            category=self.category,
            status=BlogPost.Status.PUBLISHED,
            published_at=timezone.now() - timezone.timedelta(days=1),
            previous_post=self.post1,
        )
        self.post3 = BlogPost.objects.create(
            title="Third Post",
            slug="third-post",
            author=self.user,
            category=self.category,
            status=BlogPost.Status.PUBLISHED,
            published_at=timezone.now(),
            previous_post=self.post2,
        )

    def test_navigation_presence(self):
        # Post2 should have both prev (post1) and next (post3)
        url = reverse("blog:post_detail", kwargs={"slug": self.post2.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Önceki Yazı")
        self.assertContains(response, "Sonraki Yazı")
        self.assertContains(response, self.post1.title)
        self.assertContains(response, self.post3.title)

    def test_navigation_prev_only(self):
        # Post1 has no prev, next (post2)
        url = reverse("blog:post_detail", kwargs={"slug": self.post1.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Önceki Yazı")
        self.assertContains(response, "Sonraki Yazı")
        self.assertContains(response, self.post2.title)

    def test_navigation_next_only(self):
        # Post3 has prev (post2), no next
        url = reverse("blog:post_detail", kwargs={"slug": self.post3.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Önceki Yazı")
        self.assertNotContains(response, "Sonraki Yazı")
        self.assertContains(response, self.post2.title)
