from unittest.mock import patch

from django.contrib.messages import get_messages
from django.core import signing
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import SiteSettings
from newsletter.models import Subscriber, SubscriberStatus
from newsletter.tokens import make_token


@override_settings(SECURE_SSL_REDIRECT=False)
class NewsletterSubscribeViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse("newsletter:subscribe_request")
        self.site_settings = SiteSettings.get_settings()
        self.site_settings.is_newsletter_enabled = True
        self.site_settings.save()

    def test_get_method_redirects(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, "/", fetch_redirect_response=False)

    def test_newsletter_disabled(self):
        self.site_settings.is_newsletter_enabled = False
        self.site_settings.save()

        response = self.client.post(self.url, {"email": "test@example.com"})

        self.assertRedirects(response, "/", fetch_redirect_response=False)
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), "Bülten aboneliği şu anda kapalıdır.")

    def test_invalid_form(self):
        response = self.client.post(
            self.url, {"email": "invalid-email"}, HTTP_REFERER="/some-page/"
        )

        self.assertRedirects(response, "/some-page/", fetch_redirect_response=False)
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), "Lütfen geçerli bir e-posta adresi girin.")

    def test_honeypot_field(self):
        response = self.client.post(
            self.url,
            {"email": "test@example.com", "name": "bot"},
            HTTP_REFERER="/some-page/",
        )

        self.assertRedirects(response, "/some-page/", fetch_redirect_response=False)
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            str(messages[0]),
            "Aboneliğiniz alınmıştır. Lütfen gelen kutunuzu kontrol edin.",
        )
        self.assertEqual(Subscriber.objects.count(), 0)

    @patch("newsletter.views.send_subscribe_confirmation")
    def test_already_active_subscriber(self, mock_send):
        Subscriber.objects.create(
            email="test@example.com", status=SubscriberStatus.ACTIVE
        )

        response = self.client.post(
            self.url, {"email": "test@example.com"}, HTTP_REFERER="/some-page/"
        )

        self.assertRedirects(response, "/some-page/", fetch_redirect_response=False)
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), "Bu adres zaten aktif bir abonelikte.")
        mock_send.assert_not_called()

    @patch("newsletter.views.send_subscribe_confirmation")
    def test_new_subscriber(self, mock_send):
        response = self.client.post(
            self.url, {"email": "test@example.com"}, HTTP_REFERER="/some-page/"
        )

        self.assertRedirects(response, "/some-page/", fetch_redirect_response=False)
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            str(messages[0]),
            "Aboneliğinizi onaylamak için e-posta gönderildi. Lütfen gelen kutunuzu kontrol edin.",
        )

        subscriber = Subscriber.objects.get(email="test@example.com")
        self.assertEqual(subscriber.status, SubscriberStatus.PENDING)
        self.assertIsNotNone(subscriber.subscribed_at)
        self.assertIsNone(subscriber.unsubscribed_at)
        mock_send.assert_called_once_with("test@example.com")


@override_settings(SECURE_SSL_REDIRECT=False)
class NewsletterUnsubscribeViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse("newsletter:unsubscribe_request")

    def test_get_method_redirects(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, "/", fetch_redirect_response=False)

    def test_invalid_form(self):
        response = self.client.post(
            self.url, {"email": "invalid-email"}, HTTP_REFERER="/some-page/"
        )

        self.assertRedirects(response, "/some-page/", fetch_redirect_response=False)
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), "Lütfen geçerli bir e-posta adresi girin.")

    @patch("newsletter.views.send_unsubscribe_confirmation")
    def test_non_existent_subscriber(self, mock_send):
        response = self.client.post(
            self.url, {"email": "notfound@example.com"}, HTTP_REFERER="/some-page/"
        )

        self.assertRedirects(response, "/some-page/", fetch_redirect_response=False)
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            str(messages[0]),
            "Eğer bu e-posta kayıtlıysa iptal onayı gönderildi. Lütfen gelen kutunuzu kontrol edin.",
        )
        mock_send.assert_not_called()

    @patch("newsletter.views.send_unsubscribe_confirmation")
    def test_existing_subscriber(self, mock_send):
        Subscriber.objects.create(email="test@example.com")

        response = self.client.post(
            self.url, {"email": "test@example.com"}, HTTP_REFERER="/some-page/"
        )

        self.assertRedirects(response, "/some-page/", fetch_redirect_response=False)
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(
            str(messages[0]),
            "Eğer bu e-posta kayıtlıysa iptal onayı gönderildi. Lütfen gelen kutunuzu kontrol edin.",
        )
        mock_send.assert_called_once_with("test@example.com")


@override_settings(SECURE_SSL_REDIRECT=False)
class NewsletterConfirmSubscriptionViewTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_expired_token(self):
        with patch(
            "newsletter.views.parse_token", side_effect=signing.SignatureExpired
        ):
            url = reverse("newsletter:confirm", kwargs={"token": "expired-token"})
            response = self.client.get(url)

            self.assertEqual(response.status_code, 400)
            self.assertContains(
                response,
                "Onay linkinin süresi dolmuş. Lütfen yeniden deneyin.",
                status_code=400,
            )

    def test_invalid_token(self):
        with patch("newsletter.views.parse_token", side_effect=signing.BadSignature):
            url = reverse("newsletter:confirm", kwargs={"token": "invalid-token"})
            response = self.client.get(url)

            self.assertEqual(response.status_code, 400)
            self.assertContains(
                response,
                "Onay linki geçersiz. Lütfen yeniden deneyin.",
                status_code=400,
            )

    def test_invalid_payload(self):
        with patch(
            "newsletter.views.parse_token",
            return_value={"email": "test@example.com", "action": "invalid"},
        ):
            url = reverse("newsletter:confirm", kwargs={"token": "token"})
            response = self.client.get(url)

            self.assertEqual(response.status_code, 400)
            self.assertContains(
                response, "Talep bilgileri eksik veya hatalı.", status_code=400
            )

    def test_valid_subscribe_token(self):
        token = make_token("test@example.com", "subscribe")
        url = reverse("newsletter:confirm", kwargs={"token": token})

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Newsletter aboneliğiniz başarıyla aktif edildi.")

        subscriber = Subscriber.objects.get(email="test@example.com")
        self.assertEqual(subscriber.status, SubscriberStatus.ACTIVE)

    def test_valid_unsubscribe_token(self):
        Subscriber.objects.create(
            email="test@example.com", status=SubscriberStatus.ACTIVE
        )

        token = make_token("test@example.com", "unsubscribe")
        url = reverse("newsletter:confirm", kwargs={"token": token})

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Newsletter aboneliğiniz iptal edildi.")

        subscriber = Subscriber.objects.get(email="test@example.com")
        self.assertEqual(subscriber.status, SubscriberStatus.UNSUBSCRIBED)
