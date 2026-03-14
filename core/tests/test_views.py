from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from blog.models import BlogPost, Category
from core.helpers import CAPTCHA_SESSION_KEY
from core.models import AboutPage, ContactMessage, SiteSettings

User = get_user_model()


@override_settings(SECURE_SSL_REDIRECT=False)
class ViewsTest(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(email="test@example.com", password="test")
        self.category = Category.objects.create(name="Tech", slug="tech")

        self.post = BlogPost.objects.create(
            author=self.user,
            title="A title",
            slug="a-title",
            status=BlogPost.Status.PUBLISHED,
            category=self.category,
            published_at=timezone.now(),
            is_featured=True,
        )

        SiteSettings.objects.all().delete()
        self.settings = SiteSettings.get_settings()

    def test_home_view(self):
        url = reverse("core:home")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/home.html")
        self.assertEqual(response.context["active_nav"], "home")

        self.assertEqual(response.context["featured_post"], self.post)
        self.assertIn(self.post, response.context["latest_posts"])

    def test_about_view(self):
        AboutPage.objects.create(title="About", content="Some content")
        url = reverse("core:about")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/about.html")
        self.assertEqual(response.context["active_nav"], "about")
        self.assertIsNotNone(response.context["about_page"])
        self.assertEqual(response.context["about_page"].title, "About")

    def test_contact_view_get(self):
        url = reverse("core:contact")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/contact.html")
        self.assertEqual(response.context["active_nav"], "contact")
        self.assertIn("form", response.context)
        self.assertIn("num1", response.context)
        self.assertIn("num2", response.context)

    def test_contact_view_post_disabled(self):
        self.settings.is_contact_enabled = False
        self.settings.save()

        url = reverse("core:contact")
        response = self.client.post(url, {})
        self.assertRedirects(response, url)
        messages = list(response.wsgi_request._messages)
        self.assertEqual(str(messages[0]), "İletişim formu şu anda kapalıdır.")

    def test_contact_view_post_invalid_captcha(self):
        url = reverse("core:contact")
        session = self.client.session
        session[CAPTCHA_SESSION_KEY] = 5
        session.save()

        response = self.client.post(url, {"captcha": "10"})
        self.assertRedirects(response, url)
        messages = list(response.wsgi_request._messages)
        self.assertEqual(
            str(messages[0]), "Toplam alanı boş ya da hatalı. Lütfen tekrar deneyin."
        )

    def test_contact_view_post_valid(self):
        url = reverse("core:contact")

        session = self.client.session
        session[CAPTCHA_SESSION_KEY] = 5
        session.save()

        data = {
            "captcha": "5",
            "name": "Jane",
            "subject": "Greetings",
            "email": "jane@example.com",
            "message": "Hello from Jane",
        }

        response = self.client.post(url, data)
        self.assertRedirects(response, url)

        messages = list(response.wsgi_request._messages)
        self.assertEqual(
            str(messages[0]),
            "Mesajınız alınmıştır. En kısa sürede sizinle iletişime geçeceğiz.",
        )
        self.assertTrue(
            ContactMessage.objects.filter(email="jane@example.com").exists()
        )

    def test_contact_view_post_website_field(self):
        # tests honeypot field
        url = reverse("core:contact")

        session = self.client.session
        session[CAPTCHA_SESSION_KEY] = 5
        session.save()

        data = {
            "captcha": "5",
            "name": "Spam",
            "subject": "Spam subject",
            "email": "spam@example.com",
            "message": "Spam message",
            "website": "http://spam.com",
        }

        response = self.client.post(url, data)
        self.assertRedirects(response, url)

        messages = list(response.wsgi_request._messages)
        self.assertEqual(
            str(messages[0]),
            "Mesajınız alınmıştır. En kısa sürede sizinle iletişime geçeceğiz.",
        )
        self.assertFalse(
            ContactMessage.objects.filter(email="spam@example.com").exists()
        )

    def test_contact_view_post_invalid_form(self):
        url = reverse("core:contact")

        session = self.client.session
        session[CAPTCHA_SESSION_KEY] = 5
        session.save()

        data = {
            "captcha": "5",
        }

        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)

        messages = list(response.context["messages"])
        self.assertEqual(str(messages[0]), "Lütfen form alanlarını kontrol edin.")
