from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from blog.models import BlogPost, Category
from core.helpers import CAPTCHA_SESSION_KEY
from core.models import AboutPage, ContactMessage, SiteSettings
from core.views import _handle_contact_post

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

    def test_home_view_caches_posts(self):
        from blog.cache_keys import HOME_PAGE_KEY

        url = reverse("core:home")

        # İlk istek cache miss: latest + featured sorguları çalışır ve cache dolar.
        self.assertIsNone(cache.get(HOME_PAGE_KEY))
        first = self.client.get(url)
        self.assertEqual(first.status_code, 200)

        cached = cache.get(HOME_PAGE_KEY)
        self.assertIsNotNone(cached)
        self.assertIn("latest_posts", cached)
        self.assertIn("featured_post", cached)

        # İkinci istek cache hit: anasayfa için ek BlogPost sorgusu yapılmamalı.
        with self.assertNumQueries(0):
            cache.get(HOME_PAGE_KEY)

    def test_home_view_cache_invalidated_on_post_save(self):
        from blog.cache_keys import HOME_PAGE_KEY

        url = reverse("core:home")
        self.client.get(url)
        self.assertIsNotNone(cache.get(HOME_PAGE_KEY))

        # BlogPost değişimi home cache'ini invalide etmeli.
        self.post.title = "Updated title"
        self.post.save()
        self.assertIsNone(cache.get(HOME_PAGE_KEY))

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
        self.assertIn("captcha_image", response.context)
        self.assertIsInstance(response.context["captcha_image"], str)

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
        session[CAPTCHA_SESSION_KEY] = "ABCDE"
        session.save()

        response = self.client.post(url, {"captcha": "WRONG"})
        self.assertRedirects(response, url)
        messages = list(response.wsgi_request._messages)
        self.assertEqual(
            str(messages[0]), "Güvenlik kodu boş ya da hatalı. Lütfen tekrar deneyin."
        )

    def test_contact_view_post_valid(self):
        url = reverse("core:contact")

        session = self.client.session
        session[CAPTCHA_SESSION_KEY] = "ABCDE"
        session.save()

        data = {
            "captcha": "abcde",
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
        session[CAPTCHA_SESSION_KEY] = "ABCDE"
        session.save()

        data = {
            "captcha": "ABCDE",
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
        session[CAPTCHA_SESSION_KEY] = "ABCDE"
        session.save()

        data = {
            "captcha": "abcde",
        }

        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)

        messages = list(response.context["messages"])
        self.assertEqual(str(messages[0]), "Lütfen form alanlarını kontrol edin.")

    @patch("django_ratelimit.decorators.is_ratelimited", return_value=True)
    def test_contact_view_post_rate_limited(self, mock_is_ratelimited):
        url = reverse("core:contact")

        response = self.client.post(url, {})
        self.assertRedirects(response, url)

        messages = list(response.wsgi_request._messages)
        self.assertEqual(
            str(messages[0]),
            "Çok fazla istek gönderdiniz. Lütfen biraz sonra tekrar deneyin.",
        )


class HandleContactPostTest(TestCase):
    def setUp(self):
        from unittest.mock import MagicMock

        from django.test import RequestFactory

        self.factory = RequestFactory()
        self.request = self.factory.post("/iletisim/")
        self.request.session = {CAPTCHA_SESSION_KEY: "test"}
        setattr(self.request, "_messages", FallbackStorage(self.request))
        self.site_settings = MagicMock()
        self.site_settings.is_contact_enabled = True
        self.form = MagicMock()
        self.form.is_valid.return_value = True
        self.form.cleaned_data = {}

    @patch("core.views.messages")
    def test_contact_disabled(self, mock_messages):
        self.site_settings.is_contact_enabled = False
        response = _handle_contact_post(self.request, self.site_settings, self.form)
        self.assertEqual(response.url, reverse("core:contact"))
        mock_messages.error.assert_called_once_with(
            self.request, "İletişim formu şu anda kapalıdır."
        )

    @patch("core.views.messages")
    def test_request_limited(self, mock_messages):
        self.request.limited = True
        response = _handle_contact_post(self.request, self.site_settings, self.form)
        self.assertEqual(response.url, reverse("core:contact"))
        mock_messages.error.assert_called_once_with(
            self.request,
            "Çok fazla istek gönderdiniz. Lütfen biraz sonra tekrar deneyin.",
        )

    @patch("core.views.messages")
    @patch("core.views.captcha_is_valid", return_value=False)
    def test_invalid_captcha(self, mock_captcha_is_valid, mock_messages):
        response = _handle_contact_post(self.request, self.site_settings, self.form)
        self.assertEqual(response.url, reverse("core:contact"))
        mock_messages.error.assert_called_once_with(
            self.request, "Güvenlik kodu boş ya da hatalı. Lütfen tekrar deneyin."
        )

    @patch("core.views.messages")
    @patch("core.views.captcha_is_valid", return_value=True)
    def test_invalid_form(self, mock_captcha_is_valid, mock_messages):
        self.form.is_valid.return_value = False
        response = _handle_contact_post(self.request, self.site_settings, self.form)
        self.assertIsNone(response)
        mock_messages.error.assert_called_once_with(
            self.request, "Lütfen form alanlarını kontrol edin."
        )
        self.assertNotIn(CAPTCHA_SESSION_KEY, self.request.session)

    @patch("core.views.messages")
    @patch("core.views.captcha_is_valid", return_value=True)
    def test_honeypot_filled(self, mock_captcha_is_valid, mock_messages):
        self.form.cleaned_data = {"website": "http://spam.com"}
        response = _handle_contact_post(self.request, self.site_settings, self.form)
        self.assertEqual(response.url, reverse("core:contact"))
        mock_messages.success.assert_called_once_with(
            self.request,
            "Mesajınız alınmıştır. En kısa sürede sizinle iletişime geçeceğiz.",
        )
        self.form.save.assert_called_once_with(commit=False)
        contact_message = self.form.save.return_value
        contact_message.save.assert_not_called()

    @patch("core.views.messages")
    @patch("core.views.get_client_ip", return_value="127.0.0.1")
    @patch("core.views.captcha_is_valid", return_value=True)
    def test_valid_submission(
        self, mock_captcha_is_valid, mock_get_client_ip, mock_messages
    ):
        self.request.META["HTTP_USER_AGENT"] = "Test Agent"
        response = _handle_contact_post(self.request, self.site_settings, self.form)
        self.assertEqual(response.url, reverse("core:contact"))
        mock_messages.success.assert_called_once_with(
            self.request,
            "Mesajınız alınmıştır. En kısa sürede sizinle iletişime geçeceğiz.",
        )
        contact_message = self.form.save.return_value
        self.assertEqual(contact_message.ip_address, "127.0.0.1")
        self.assertEqual(contact_message.user_agent, "Test Agent")
        contact_message.save.assert_called_once()
