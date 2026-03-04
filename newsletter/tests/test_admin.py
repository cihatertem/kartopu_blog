from unittest.mock import Mock, patch

from django.contrib.admin.sites import AdminSite
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, TestCase
from django.utils import timezone

from newsletter.admin import (
    AnnouncementAdmin,
    DirectEmailAdmin,
    EmailQueueAdmin,
    SubscriberAdmin,
    mark_unsubscribed,
    requeue_emails,
    send_selected_announcements,
)
from newsletter.models import (
    Announcement,
    AnnouncementStatus,
    DirectEmail,
    EmailQueue,
    EmailQueueStatus,
    Subscriber,
    SubscriberStatus,
)


class MockRequest:
    pass


class NewsletterAdminTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.site = AdminSite()

    def get_mock_request(self):
        request = self.factory.get("/")
        setattr(request, "session", "session")
        messages = FallbackStorage(request)
        setattr(request, "_messages", messages)
        return request

    def test_subscriber_admin_mark_unsubscribed(self):
        subscriber = Subscriber.objects.create(
            email="test@example.com", status=SubscriberStatus.ACTIVE
        )
        admin = SubscriberAdmin(Subscriber, self.site)
        request = self.get_mock_request()

        queryset = Subscriber.objects.all()
        mark_unsubscribed(admin, request, queryset)

        subscriber.refresh_from_db()
        self.assertEqual(subscriber.status, SubscriberStatus.UNSUBSCRIBED)
        self.assertIsNotNone(subscriber.unsubscribed_at)

        messages = list(get_messages(request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), "1 abonelik iptal edildi.")

    @patch("newsletter.admin.send_announcement")
    def test_announcement_admin_send_selected_announcements(self, mock_send):
        announcement_draft = Announcement.objects.create(
            subject="Draft", body="Body", status=AnnouncementStatus.DRAFT
        )
        announcement_sent = Announcement.objects.create(
            subject="Sent", body="Body", status=AnnouncementStatus.SENT
        )
        mock_send.return_value = 5

        admin = AnnouncementAdmin(Announcement, self.site)
        request = self.get_mock_request()
        queryset = Announcement.objects.all()

        # Queryset returns in an order we should control or just sort it explicitly
        queryset = Announcement.objects.all().order_by("subject")  # Draft then Sent
        send_selected_announcements(admin, request, queryset)

        mock_send.assert_called_once_with(announcement_draft)

        messages = list(get_messages(request))
        self.assertEqual(len(messages), 2)

        # Check messages correctly
        message_strings = [str(m) for m in messages]
        self.assertIn("Sent zaten gönderildi.", message_strings)
        self.assertIn("Draft duyurusu 5 aboneye gönderildi.", message_strings)

    def test_email_queue_admin_requeue_emails(self):
        email_queue = EmailQueue.objects.create(
            subject="Test",
            from_email="from@example.com",
            to_email="to@example.com",
            text_body="body",
            status=EmailQueueStatus.FAILED,
            error_message="Some error",
        )
        admin = EmailQueueAdmin(EmailQueue, self.site)
        request = self.get_mock_request()
        queryset = EmailQueue.objects.all()

        requeue_emails(admin, request, queryset)

        email_queue.refresh_from_db()
        self.assertEqual(email_queue.status, EmailQueueStatus.PENDING)
        self.assertIsNone(email_queue.error_message)

        messages = list(get_messages(request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), "1 e-posta tekrar kuyruğa alındı.")

    @patch("newsletter.admin.send_direct_email")
    def test_direct_email_admin_send_emails_success(self, mock_send):
        direct_email = DirectEmail.objects.create(
            subject="Test", to_email="to@example.com", body="Body"
        )
        mock_send.return_value = True

        admin = DirectEmailAdmin(DirectEmail, self.site)
        request = self.get_mock_request()
        queryset = DirectEmail.objects.all()

        admin.send_emails(request, queryset)

        mock_send.assert_called_once_with(direct_email)
        messages = list(get_messages(request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), "1 e-posta başarıyla gönderildi.")

    @patch("newsletter.admin.send_direct_email")
    def test_direct_email_admin_send_emails_failure(self, mock_send):
        DirectEmail.objects.create(
            subject="Test", to_email="to@example.com", body="Body"
        )
        mock_send.return_value = False

        admin = DirectEmailAdmin(DirectEmail, self.site)
        request = self.get_mock_request()
        queryset = DirectEmail.objects.all()

        admin.send_emails(request, queryset)

        messages = list(get_messages(request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), "E-postalar gönderilemedi.")

    def test_direct_email_admin_rendered_body_preview(self):
        direct_email = DirectEmail(body="**Bold** text")
        admin = DirectEmailAdmin(DirectEmail, self.site)
        preview = admin.rendered_body_preview(direct_email)

        self.assertIn("<strong>Bold</strong>", preview)
        self.assertIn("text", preview)

        # Empty body
        empty_email = DirectEmail(body="")
        preview_empty = admin.rendered_body_preview(empty_email)
        self.assertEqual(preview_empty, "")
