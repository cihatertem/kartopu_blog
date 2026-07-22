from unittest.mock import patch

from django.core import mail
from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from blog.models import BlogPost, Category
from newsletter.models import (
    Announcement,
    AnnouncementStatus,
    BlogPostNotification,
    DirectEmail,
    EmailQueue,
    Subscriber,
    SubscriberStatus,
)
from newsletter.services import (
    build_subscribe_confirm_url,
    build_unsubscribe_url,
    prepare_templated_email,
    queue_post_published_notification,
    send_announcement,
    send_announcements_bulk,
    send_direct_emails_bulk,
    send_subscribe_confirmation,
    send_templated_email,
    send_unsubscribe_confirmation,
)
from newsletter.tokens import parse_token


class ServicesTest(TestCase):
    @patch("newsletter.services.send_templated_email")
    @patch("newsletter.services.build_unsubscribe_url")
    @patch("newsletter.services.build_subscribe_confirm_url")
    def test_send_subscribe_confirmation(
        self, mock_build_confirm, mock_build_unsub, mock_send
    ):
        mock_build_confirm.return_value = "http://testserver/confirm"
        mock_build_unsub.return_value = "http://testserver/unsubscribe"

        email = "test@example.com"
        send_subscribe_confirmation(email)

        mock_build_confirm.assert_called_once_with(email)
        mock_build_unsub.assert_called_once_with(email)

        expected_context = {
            "confirm_url": "http://testserver/confirm",
            "unsubscribe_url": "http://testserver/unsubscribe",
            "site_name": "Kartopu Money",
        }

        mock_send.assert_called_once_with(
            subject="Newsletter aboneliğinizi onaylayın",
            to_email=email,
            template_prefix="subscribe_confirm",
            context=expected_context,
        )

    @patch("newsletter.services.send_templated_email")
    @patch("newsletter.services.build_unsubscribe_url")
    def test_send_unsubscribe_confirmation(self, mock_build_unsub, mock_send):
        mock_build_unsub.return_value = "http://testserver/unsubscribe"

        email = "test@example.com"
        send_unsubscribe_confirmation(email)

        mock_build_unsub.assert_called_once_with(email)

        expected_context = {
            "unsubscribe_url": "http://testserver/unsubscribe",
            "site_name": "Kartopu Money",
        }

        mock_send.assert_called_once_with(
            subject="Newsletter abonelik iptal isteği",
            to_email=email,
            template_prefix="unsubscribe_confirm",
            context=expected_context,
        )

    def test_build_subscribe_confirm_url(self):
        email = "test@example.com"
        url = build_subscribe_confirm_url(email)

        self.assertTrue(url.startswith("http://") or url.startswith("https://"))

        from urllib.parse import urlparse

        parsed_url = urlparse(url)
        path = parsed_url.path

        self.assertTrue(path.startswith("/newsletter/confirm/"))

        parts = path.strip("/").split("/")
        self.assertEqual(len(parts), 3)
        self.assertEqual(parts[0], "newsletter")
        self.assertEqual(parts[1], "confirm")

        token = parts[2]

        payload = parse_token(token, max_age=86400)
        self.assertEqual(payload["email"], email)
        self.assertEqual(payload["action"], "subscribe")

    def test_build_unsubscribe_url(self):
        email = "test@example.com"
        url = build_unsubscribe_url(email)

        self.assertTrue(url.startswith("http://") or url.startswith("https://"))

        from urllib.parse import urlparse

        parsed_url = urlparse(url)
        path = parsed_url.path

        self.assertTrue(path.startswith("/newsletter/confirm/"))

        parts = path.strip("/").split("/")
        self.assertEqual(len(parts), 3)
        self.assertEqual(parts[0], "newsletter")
        self.assertEqual(parts[1], "confirm")

        token = parts[2]

        payload = parse_token(token, max_age=86400)
        self.assertEqual(payload["email"], email)
        self.assertEqual(payload["action"], "unsubscribe")

    @patch("newsletter.services.render_to_string")
    def test_prepare_templated_email(self, mock_render):
        def render_side_effect(template_name, context):
            if template_name.endswith(".txt"):
                return "Mock text body"
            elif template_name.endswith(".html"):
                return "Mock html body"
            return "Unknown"

        mock_render.side_effect = render_side_effect

        context = {"key": "value"}
        result = prepare_templated_email(
            subject="Test Subject",
            to_email="test@example.com",
            template_prefix="test_template",
            context=context,
        )

        self.assertEqual(result["subject"], "Test Subject")
        self.assertEqual(result["to_email"], "test@example.com")
        self.assertIn("Kartopu.Money Blog", result["from_email"])
        self.assertEqual(result["text_body"], "Mock text body")
        self.assertEqual(result["html_body"], "Mock html body")

        self.assertEqual(mock_render.call_count, 2)
        mock_render.assert_any_call("newsletter/email/test_template.txt", context)
        mock_render.assert_any_call("newsletter/email/test_template.html", context)

    @patch("newsletter.services.prepare_templated_email")
    def test_send_templated_email(self, mock_prepare):
        mock_prepare.return_value = {
            "subject": "Test Subject",
            "text_body": "Text body content",
            "html_body": "<html>Html body content</html>",
            "from_email": '"Kartopu" <test@kartopu.money>',
            "to_email": "recipient@example.com",
        }

        mail.outbox = []

        send_templated_email(
            subject="Ignored by mock",
            to_email="ignored@example.com",
            template_prefix="ignored",
            context={},
        )

        self.assertEqual(len(mail.outbox), 1)

        sent_email = mail.outbox[0]
        self.assertEqual(sent_email.subject, "Test Subject")
        self.assertEqual(sent_email.body, "Text body content")
        self.assertEqual(sent_email.from_email, '"Kartopu" <test@kartopu.money>')
        self.assertEqual(sent_email.to, ["recipient@example.com"])

        self.assertEqual(len(sent_email.alternatives), 1)
        self.assertEqual(
            sent_email.alternatives[0], ("<html>Html body content</html>", "text/html")
        )


class SendAnnouncementsBulkTest(TestCase):
    def setUp(self):
        self.sub1 = Subscriber.objects.create(
            email="sub1@example.com", status=SubscriberStatus.ACTIVE
        )
        self.sub2 = Subscriber.objects.create(
            email="sub2@example.com", status=SubscriberStatus.ACTIVE
        )
        self.sub_inactive = Subscriber.objects.create(
            email="inactive@example.com", status=SubscriberStatus.PENDING
        )

        self.ann1 = Announcement.objects.create(
            subject="Test Announcement 1",
            body="Body 1",
            status=AnnouncementStatus.DRAFT,
        )
        self.ann2 = Announcement.objects.create(
            subject="Test Announcement 2",
            body="Body 2",
            status=AnnouncementStatus.DRAFT,
        )

    def test_empty_announcements(self):
        result = send_announcements_bulk([])
        self.assertEqual(result, 0)
        self.assertEqual(EmailQueue.objects.count(), 0)

    def test_sends_to_active_subscribers(self):
        announcements = [self.ann1, self.ann2]

        initial_queue_count = EmailQueue.objects.count()

        result = send_announcements_bulk(announcements)

        # 2 active subscribers * 2 announcements = 4 queue items / 2 announcements = 2
        self.assertEqual(result, 2)
        self.assertEqual(EmailQueue.objects.count(), initial_queue_count + 4)

        self.ann1.refresh_from_db()
        self.ann2.refresh_from_db()

        self.assertEqual(self.ann1.status, AnnouncementStatus.SENT)
        self.assertIsNotNone(self.ann1.sent_at)
        self.assertEqual(self.ann2.status, AnnouncementStatus.SENT)
        self.assertIsNotNone(self.ann2.sent_at)

        emails = EmailQueue.objects.all()
        to_emails = set(e.to_email for e in emails)
        self.assertIn("sub1@example.com", to_emails)
        self.assertIn("sub2@example.com", to_emails)
        self.assertNotIn("inactive@example.com", to_emails)


class SendAnnouncementTest(TestCase):
    def setUp(self):
        self.sub1 = Subscriber.objects.create(
            email="sub1@example.com", status=SubscriberStatus.ACTIVE
        )
        self.sub2 = Subscriber.objects.create(
            email="sub2@example.com", status=SubscriberStatus.ACTIVE
        )
        self.sub_inactive = Subscriber.objects.create(
            email="inactive@example.com", status=SubscriberStatus.PENDING
        )

        self.ann1 = Announcement.objects.create(
            subject="Test Single Announcement",
            body="Single Body",
            status=AnnouncementStatus.DRAFT,
        )

    def test_sends_to_active_subscribers(self):
        initial_queue_count = EmailQueue.objects.count()

        result = send_announcement(self.ann1)

        self.assertEqual(result, 2)
        self.assertEqual(EmailQueue.objects.count(), initial_queue_count + 2)

        self.ann1.refresh_from_db()

        self.assertEqual(self.ann1.status, AnnouncementStatus.SENT)
        self.assertIsNotNone(self.ann1.sent_at)

        emails = EmailQueue.objects.all()
        to_emails = set(e.to_email for e in emails)
        self.assertIn("sub1@example.com", to_emails)
        self.assertIn("sub2@example.com", to_emails)
        self.assertNotIn("inactive@example.com", to_emails)


class QueuePostPublishedNotificationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="author@example.com", password="password"
        )
        self.category = Category.objects.create(name="Finance", slug="finance")
        self.post = BlogPost.objects.create(
            author=self.user,
            category=self.category,
            title="Queued Post",
            content="Test Content",
            status=BlogPost.Status.DRAFT,
            slug="queued-post",
        )

    @patch("newsletter.services.send_post_published_email")
    def test_creates_notification_and_queues_once(self, mock_send_email):
        self.post.status = BlogPost.Status.PUBLISHED
        self.post.published_at = timezone.now()
        self.post.save()
        BlogPostNotification.objects.filter(post=self.post).delete()
        mock_send_email.reset_mock()

        self.assertTrue(queue_post_published_notification(self.post))
        self.assertFalse(queue_post_published_notification(self.post))

        mock_send_email.assert_called_once_with(self.post)
        self.assertEqual(BlogPostNotification.objects.filter(post=self.post).count(), 1)

    @patch("newsletter.services.send_post_published_email")
    def test_rolls_back_notification_if_queueing_fails(self, mock_send_email):
        mock_send_email.side_effect = Exception("queue failed")
        self.post.status = BlogPost.Status.PUBLISHED
        self.post.published_at = timezone.now()

        with self.assertRaises(Exception):
            queue_post_published_notification(self.post)

        self.assertFalse(BlogPostNotification.objects.filter(post=self.post).exists())


class SendDirectEmailsBulkTest(TestCase):
    def setUp(self):
        self.email1 = DirectEmail.objects.create(
            to_email="test1@example.com",
            subject="Subject 1",
            body="**Bold text** and *italic text*.",
        )
        self.email2 = DirectEmail.objects.create(
            to_email="test2@example.com",
            subject="Subject 2",
            body="# Heading 1\nSome text.",
        )
        self.from_email = '"Kartopu Money" <info@kartopu.money>'

    def test_send_direct_emails_bulk_with_queryset(self):
        """Test sending bulk emails using a QuerySet (with chunked iteration)."""
        queryset = DirectEmail.objects.all().order_by("id")
        created_count = send_direct_emails_bulk(queryset)

        self.assertEqual(created_count, 2)

        queues = EmailQueue.objects.all().order_by("id")
        self.assertEqual(queues.count(), 2)

        q1 = queues[0]
        # Depending on database state before test, we should extract the exact items we want.
        q1 = next(q for q in queues if q.to_email == "test1@example.com")
        self.assertEqual(q1.subject, "Subject 1")
        self.assertEqual(q1.from_email, self.from_email)
        self.assertEqual(q1.text_body, "**Bold text** and *italic text*.")
        self.assertIn("<strong>Bold text</strong>", q1.html_body)
        self.assertIn("<em>italic text</em>", q1.html_body)
        self.assertEqual(q1.direct_email, self.email1)

        q2 = next(q for q in queues if q.to_email == "test2@example.com")
        self.assertEqual(q2.subject, "Subject 2")
        self.assertIn("Heading 1</h1>", q2.html_body)
        self.assertEqual(q2.direct_email, self.email2)

    def test_send_direct_emails_bulk_with_list(self):
        """Test sending bulk emails using a list (fallback iteration)."""
        email_list = [self.email1, self.email2]
        created_count = send_direct_emails_bulk(email_list)

        self.assertEqual(created_count, 2)

        queues = EmailQueue.objects.all().order_by("id")
        self.assertEqual(queues.count(), 2)
        # Because we bulk create over a list, order might be preserved by creation time,
        # but just to be safe, check the set of emails
        emails = {q.to_email for q in queues}
        self.assertSetEqual(emails, {"test1@example.com", "test2@example.com"})
