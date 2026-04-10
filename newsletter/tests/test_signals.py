from unittest.mock import patch

from django.test import TransactionTestCase
from django.utils import timezone

from accounts.models import User
from blog.models import BlogPost, Category
from newsletter.models import BlogPostNotification


class NewsletterSignalsTest(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com", password="password"
        )
        self.category = Category.objects.create(name="Finance", slug="finance")

    @patch("newsletter.signals.send_post_published_email")
    def test_notify_subscribers_on_publish(self, mock_send_email):
        post = BlogPost.objects.create(
            author=self.user,
            category=self.category,
            title="Test Post",
            content="Test Content",
            status=BlogPost.Status.DRAFT,
            slug="test-post",
        )
        mock_send_email.assert_not_called()
        self.assertEqual(BlogPostNotification.objects.count(), 0)

        post.status = BlogPost.Status.PUBLISHED
        post.published_at = timezone.now()
        post.save()

        mock_send_email.assert_called_once_with(post)
        self.assertEqual(BlogPostNotification.objects.count(), 1)
        notification = BlogPostNotification.objects.first()
        self.assertEqual(notification.post, post)

    @patch("newsletter.signals.send_post_published_email")
    def test_do_not_notify_if_already_notified(self, mock_send_email):
        post = BlogPost.objects.create(
            author=self.user,
            category=self.category,
            title="Test Post 2",
            content="Test Content",
            status=BlogPost.Status.PUBLISHED,
            slug="test-post-2",
            published_at=timezone.now(),
        )
        mock_send_email.assert_called_once_with(post)
        self.assertEqual(BlogPostNotification.objects.count(), 1)

        mock_send_email.reset_mock()

        post.title = "Updated Title"
        post.save()

        mock_send_email.assert_not_called()
        self.assertEqual(BlogPostNotification.objects.count(), 1)

    @patch("newsletter.signals.send_post_published_email")
    @patch("blog.models.BlogPost.save")
    def test_do_not_notify_if_published_but_no_date(self, mock_save, mock_send_email):
        # We need to simulate the instance saving without the custom save method
        # adding the published_at date, to purely test the signal logic

        post = BlogPost(
            author=self.user,
            category=self.category,
            title="Test Post 3",
            content="Test Content",
            status=BlogPost.Status.PUBLISHED,
            slug="test-post-3",
            published_at=None,
        )

        # Manually call the receiver method directly to avoid other signals failing
        from newsletter.signals import notify_subscribers_on_publish

        notify_subscribers_on_publish(sender=BlogPost, instance=post)

        mock_send_email.assert_not_called()
        self.assertEqual(BlogPostNotification.objects.count(), 0)

    @patch("newsletter.signals.send_post_published_email")
    def test_notification_not_created_if_email_fails(self, mock_send_email):
        mock_send_email.side_effect = Exception("Email sending failed")

        with self.assertRaises(Exception):
            BlogPost.objects.create(
                author=self.user,
                category=self.category,
                title="Test Post 4",
                content="Test Content",
                status=BlogPost.Status.PUBLISHED,
                slug="test-post-4",
                published_at=timezone.now(),
            )

        self.assertEqual(BlogPostNotification.objects.count(), 0)
