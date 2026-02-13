import uuid

from django.core import mail
from django.core.management import call_command
from django.test import TestCase

from accounts.models import User
from blog.models import BlogPost, Category
from newsletter.models import (
    Announcement,
    EmailQueue,
    EmailQueueStatus,
    Subscriber,
    SubscriberStatus,
)
from newsletter.services import send_announcement, send_post_published_email


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
