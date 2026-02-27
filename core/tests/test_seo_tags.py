from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from blog.models import BlogPost, Category, Tag
from core.models import PageSEO, SiteSettings


@override_settings(SITE_BASE_URL="https://kartopu.money", SECURE_SSL_REDIRECT=False)
class SEOTest(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            email="test@example.com", password="password"
        )
        # SiteSettings singleton creation might fail if one already exists due to other tests
        # So we try get or create
        self.site_settings, _ = SiteSettings.objects.get_or_create(
            defaults={
                "default_meta_title": "Default Title",
                "default_meta_description": "Default Description",
            }
        )
        self.site_settings.default_meta_title = "Default Title"
        self.site_settings.default_meta_description = "Default Description"
        self.site_settings.save()

        self.category = Category.objects.create(
            name="Test Category", slug="test-category", description="Category Desc"
        )
        self.tag = Tag.objects.create(name="Test Tag", slug="test-tag")
        self.post = BlogPost.objects.create(
            author=self.user,
            title="Test Post",
            slug="test-post",
            content="Content",
            status=BlogPost.Status.PUBLISHED,
            published_at=timezone.now(),
            meta_description="Post Meta Desc",
        )
        self.post.tags.add(self.tag)

    def test_default_seo(self):
        # We need a page that doesn't have specific SEO logic to test default
        # But most pages now have something. Let's try home.
        response = self.client.get(reverse("core:home"))
        # Home page uses "Finansal Özgürlük..." hardcoded title in template usually,
        # but now we replaced it with seo tag.
        # However, Home view passes context? No, home view passes featured_post etc.
        # seo_tags logic for home:
        # if post not in context, and no about_page etc.
        # It falls back to PageSEO or Default.

        # Let's check what seo_tags produces for home
        # Note: SiteSettings default title is "Default Title"
        # But we also have PageSEO override capability.

        self.assertContains(
            response,
            "<title>Finansal Özgürlük ve Yatırım Günlüğü Ana Sayfası | Kartopu Money</title>",
        )
        self.assertContains(response, 'content="Default Description"')
        self.assertContains(response, 'property="og:type" content="website"')

    def test_post_seo(self):
        response = self.client.get(self.post.get_absolute_url())
        self.assertContains(
            response, f"<title>{self.post.effective_meta_title}</title>"
        )
        self.assertContains(response, 'content="Post Meta Desc"')
        self.assertContains(response, 'property="og:type" content="article"')
        # We need to format timezone aware datetime to what template renders (usually isoformat)
        # The template uses {{ seo.article_published_time }} which is isoformat.
        self.assertContains(response, 'property="article:published_time"')

    def test_category_seo(self):
        response = self.client.get(self.category.get_absolute_url())
        self.assertContains(
            response, "<title>Test Category Yazıları | Kartopu Money</title>"
        )
        self.assertContains(response, 'content="Category Desc"')

    def test_tag_seo(self):
        response = self.client.get(self.tag.get_absolute_url())
        self.assertContains(
            response, "<title>#Test Tag etiketli yazılar - Kartopu Money</title>"
        )

    def test_pageseo_override(self):
        path = reverse("core:contact")
        PageSEO.objects.create(
            path=path, title="Contact SEO Title", description="Contact SEO Desc"
        )
        response = self.client.get(path)
        self.assertContains(response, "<title>İletişim | Kartopu Money</title>")
        self.assertContains(response, 'content="Contact SEO Desc"')
