from django.core import mail
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from newsletter.models import (
    DirectEmail,
    DirectEmailAttachment,
    EmailQueue,
    EmailQueueStatus,
)
from newsletter.services import send_direct_email


class DirectEmailQueueTest(TestCase):
    def test_send_direct_email_queues(self):
        direct_email = DirectEmail.objects.create(
            to_email="recipient@example.com",
            subject="Direct Subject",
            body="Direct **Markdown** Body",
        )

        # Calling send_direct_email should now queue it
        result = send_direct_email(direct_email)
        self.assertTrue(result)

        # Verify it's in the queue
        self.assertEqual(EmailQueue.objects.count(), 1)
        queue_item = EmailQueue.objects.first()
        self.assertEqual(queue_item.subject, "Direct Subject")
        self.assertEqual(queue_item.to_email, "recipient@example.com")
        self.assertEqual(queue_item.direct_email, direct_email)
        self.assertEqual(queue_item.status, EmailQueueStatus.PENDING)

        # Verify no emails sent yet
        self.assertEqual(len(mail.outbox), 0)

        # Verify direct_email sent_at is NOT set yet (only set after processing)
        direct_email.refresh_from_db()
        self.assertIsNone(direct_email.sent_at)

    def test_process_queue_with_direct_email_attachments(self):
        direct_email = DirectEmail.objects.create(
            to_email="recipient@example.com",
            subject="With Attachments",
            body="Body",
        )

        # Add attachments
        attachment1 = DirectEmailAttachment.objects.create(
            direct_email=direct_email,
        )
        attachment1.file.save("test1.txt", ContentFile(b"Content 1"))

        attachment2 = DirectEmailAttachment.objects.create(
            direct_email=direct_email,
        )
        attachment2.file.save("test2.txt", ContentFile(b"Content 2"))

        # Queue it
        send_direct_email(direct_email)

        # Run worker
        call_command("process_email_queue", rate=100)

        # Verify email sent with attachments
        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        self.assertEqual(sent_email.subject, "With Attachments")
        self.assertEqual(len(sent_email.attachments), 2)

        # Check attachment names
        attachment_names = [a[0] for a in sent_email.attachments]
        self.assertTrue(any(name.startswith("test1") for name in attachment_names))
        self.assertTrue(any(name.startswith("test2") for name in attachment_names))

        # Check attachment contents
        attachment_contents = [a[1] for a in sent_email.attachments]
        # print(f"DEBUG: attachment_contents={attachment_contents}")
        # Some backends might return strings instead of bytes for simple text content
        self.assertTrue(
            any(c == b"Content 1" or c == "Content 1" for c in attachment_contents)
        )
        self.assertTrue(
            any(c == b"Content 2" or c == "Content 2" for c in attachment_contents)
        )

    def test_attachment_upload_path(self):
        direct_email = DirectEmail.objects.create(
            subject="Ücretler ve Planlar",
            to_email="test@example.com",
            body="Test",
        )
        attachment = DirectEmailAttachment.objects.create(
            direct_email=direct_email,
        )
        attachment.file.save("ucretler.pdf", ContentFile(b"PDF Content"))

        # Verify path: mail/ucretler-ve-planlar/ucretler.pdf
        # Django's default slugify for Turkish 'Ü' is 'u' if not configured otherwise,
        # but let's see what happens.
        expected_prefix = "mail/ucretler-ve-planlar/"
        self.assertTrue(attachment.file.name.startswith(expected_prefix))
