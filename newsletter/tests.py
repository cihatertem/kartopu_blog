import uuid

from django.core import mail
from django.core.management import call_command
from django.test import TestCase

from accounts.models import User
from blog.models import BlogPost, Category
from newsletter.models import (
    Announcement,
    DirectEmail,
    EmailQueue,
    EmailQueueStatus,
    Subscriber,
    SubscriberStatus,
)
from newsletter.services import (
    send_announcement,
    send_direct_email,
    send_post_published_email,
)


class EmailQueueTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com", password="password"
        )
        self.category = Category.objects.create(name="Finance", slug="finance")
        self.subscriber1 = Subscriber.objects.create(
            email="sub1@example.com", status=SubscriberStatus.ACTIVE
        )
        self.subscriber2 = Subscriber.objects.create(
            email="sub2@example.com", status=SubscriberStatus.ACTIVE
        )
        self.post = BlogPost.objects.create(
            author=self.user,
            category=self.category,
            title="Test Post",
            content="Test Content",
            status=BlogPost.Status.PUBLISHED,
            slug="test-post",
        )

    def test_send_post_published_queues_emails(self):
        send_post_published_email(self.post)
        self.assertEqual(EmailQueue.objects.count(), 2)
        self.assertEqual(
            EmailQueue.objects.filter(status=EmailQueueStatus.PENDING).count(), 2
        )
        # Verify no emails sent yet
        self.assertEqual(len(mail.outbox), 0)

    def test_send_announcement_queues_emails(self):
        announcement = Announcement.objects.create(subject="Hello", body="World")
        send_announcement(announcement)
        self.assertEqual(EmailQueue.objects.count(), 2)
        self.assertEqual(
            EmailQueue.objects.filter(status=EmailQueueStatus.PENDING).count(), 2
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_process_email_queue_command(self):
        EmailQueue.objects.create(
            subject="Test",
            from_email="from@example.com",
            to_email="to@example.com",
            text_body="Hello",
        )
        self.assertEqual(
            EmailQueue.objects.filter(status=EmailQueueStatus.PENDING).count(), 1
        )

        call_command("process_email_queue", rate=100)  # Use high rate for tests

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            EmailQueue.objects.filter(status=EmailQueueStatus.SENT).count(), 1
        )
        self.assertEqual(mail.outbox[0].subject, "Test")


class DirectEmailTest(TestCase):
    def test_send_direct_email(self):
        direct_email = DirectEmail.objects.create(
            to_email="recipient@example.com",
            subject="Direct Subject",
            body="Direct **Markdown** Body",
        )
        send_direct_email(direct_email)

        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        self.assertEqual(sent_email.subject, "Direct Subject")
        self.assertEqual(sent_email.to, ["recipient@example.com"])
        self.assertEqual(sent_email.from_email, '"Kartopu Money" <info@kartopu.money>')
        self.assertIn("Direct **Markdown** Body", sent_email.body)
        self.assertTrue(hasattr(sent_email, "alternatives"))
        self.assertEqual(len(sent_email.alternatives), 1)
        html_body, mimetype = sent_email.alternatives[0]
        self.assertEqual(mimetype, "text/html")
        self.assertIn("<strong>Markdown</strong>", html_body)

        direct_email.refresh_from_db()
        self.assertIsNotNone(direct_email.sent_at)
