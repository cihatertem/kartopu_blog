from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from blog.models import BlogPost, Category
from newsletter.models import (
    Announcement,
    BlogPostNotification,
    DirectEmail,
    DirectEmailAttachment,
    EmailQueue,
    Subscriber,
    SubscriberStatus,
)


class SubscriberModelTest(TestCase):
    def test_subscriber_str(self):
        subscriber = Subscriber.objects.create(email="test@example.com")
        self.assertEqual(str(subscriber), "test@example.com")

    def test_mark_pending(self):
        subscriber = Subscriber.objects.create(
            email="test@example.com",
            status=SubscriberStatus.ACTIVE,
            unsubscribed_at=timezone.now(),
        )
        subscriber.mark_pending()

        subscriber.refresh_from_db()
        self.assertEqual(subscriber.status, SubscriberStatus.PENDING)
        self.assertIsNotNone(subscriber.subscribed_at)
        self.assertIsNone(subscriber.unsubscribed_at)

    def test_activate_without_prior_subscribed_at(self):
        subscriber = Subscriber.objects.create(
            email="test@example.com",
            status=SubscriberStatus.PENDING,
        )
        subscriber.activate()

        subscriber.refresh_from_db()
        self.assertEqual(subscriber.status, SubscriberStatus.ACTIVE)
        self.assertIsNotNone(subscriber.subscribed_at)
        self.assertIsNotNone(subscriber.confirmed_at)
        self.assertIsNone(subscriber.unsubscribed_at)

    def test_activate_with_prior_subscribed_at(self):
        now = timezone.now()
        subscriber = Subscriber.objects.create(
            email="test@example.com",
            status=SubscriberStatus.PENDING,
            subscribed_at=now,
        )
        subscriber.activate()

        subscriber.refresh_from_db()
        self.assertEqual(subscriber.status, SubscriberStatus.ACTIVE)
        self.assertEqual(subscriber.subscribed_at, now)
        self.assertIsNotNone(subscriber.confirmed_at)
        self.assertIsNone(subscriber.unsubscribed_at)

    def test_unsubscribe(self):
        subscriber = Subscriber.objects.create(
            email="test@example.com",
            status=SubscriberStatus.ACTIVE,
        )
        subscriber.unsubscribe()

        subscriber.refresh_from_db()
        self.assertEqual(subscriber.status, SubscriberStatus.UNSUBSCRIBED)
        self.assertIsNotNone(subscriber.unsubscribed_at)


class BlogPostNotificationModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="author@example.com", password="password"
        )
        self.category = Category.objects.create(
            name="Test Category", slug="test-category"
        )
        self.post = BlogPost.objects.create(
            author=self.user,
            category=self.category,
            title="My Awesome Post",
            slug="my-awesome-post",
            content="Content",
        )

    def test_blog_post_notification_str(self):
        with patch("newsletter.signals.send_post_published_email"):
            notification = BlogPostNotification.objects.create(
                post=self.post, sent_at=timezone.now()
            )
            self.assertEqual(str(notification), "My Awesome Post")


class AnnouncementModelTest(TestCase):
    def test_announcement_str(self):
        announcement = Announcement.objects.create(
            subject="Important Update",
            body="We have some news.",
        )
        self.assertEqual(str(announcement), "Important Update")


class EmailQueueModelTest(TestCase):
    def test_email_queue_str(self):
        email_queue = EmailQueue.objects.create(
            subject="Hello",
            from_email="from@example.com",
            to_email="to@example.com",
            text_body="Body",
        )
        self.assertEqual(str(email_queue), "Hello -> to@example.com")


class DirectEmailModelTest(TestCase):
    def test_direct_email_str(self):
        direct_email = DirectEmail.objects.create(
            subject="Direct Subject",
            to_email="to@example.com",
            body="Body",
        )
        self.assertEqual(str(direct_email), "Direct Subject -> to@example.com")


class DirectEmailAttachmentModelTest(TestCase):
    def test_direct_email_attachment_str(self):
        direct_email = DirectEmail.objects.create(
            subject="Direct Subject",
            to_email="to@example.com",
            body="Body",
        )
        attachment = DirectEmailAttachment(direct_email=direct_email)
        attachment.file.name = "test_file.txt"

        self.assertEqual(str(attachment), "test_file.txt")
