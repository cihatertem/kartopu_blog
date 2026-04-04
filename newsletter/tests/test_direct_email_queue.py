from unittest.mock import patch

from django.core import mail
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import TestCase

from newsletter.models import (
    DirectEmail,
    DirectEmailAttachment,
    EmailQueue,
    EmailQueueStatus,
)
from newsletter.services import send_direct_email


class DirectEmailQueueTest(TestCase):
    def setUp(self):
        mail.outbox.clear()
        EmailQueue.objects.all().delete()
        DirectEmail.objects.all().delete()

    def test_send_direct_email_queues(self):
        direct_email = DirectEmail.objects.create(
            to_email="recipient@example.com",
            subject="Direct Subject 1",
            body="Direct **Markdown** Body",
        )

        result = send_direct_email(direct_email)
        self.assertTrue(result)

        queue_item = EmailQueue.objects.get(subject="Direct Subject 1")
        self.assertEqual(queue_item.to_email, "recipient@example.com")
        self.assertEqual(queue_item.direct_email, direct_email)
        self.assertEqual(queue_item.status, EmailQueueStatus.PENDING)

        direct_email.refresh_from_db()
        self.assertIsNone(direct_email.sent_at)

    @patch(
        "newsletter.management.commands.process_email_queue.Command._acquire_lock",
        return_value=True,
    )
    @patch("newsletter.management.commands.process_email_queue.Command._release_lock")
    def test_process_queue_with_direct_email_attachments(
        self, mock_release, mock_acquire
    ):
        direct_email = DirectEmail.objects.create(
            to_email="recipient@example.com",
            subject="With Attachments Unique Subject",
            body="Body",
        )

        attachment1 = DirectEmailAttachment.objects.create(
            direct_email=direct_email,
        )
        attachment1.file.save("test1.txt", ContentFile(b"Content 1"))

        attachment2 = DirectEmailAttachment.objects.create(
            direct_email=direct_email,
        )
        attachment2.file.save("test2.txt", ContentFile(b"Content 2"))

        send_direct_email(direct_email)

        call_command("process_email_queue", rate=100)

        sent_email = None
        for out_email in mail.outbox:
            if out_email.subject == "With Attachments Unique Subject":
                sent_email = out_email
                break

        self.assertIsNotNone(sent_email, "Expected email was not in outbox")
        self.assertEqual(len(sent_email.attachments), 2)

        attachment_names = [a[0] for a in sent_email.attachments]
        self.assertTrue(any(name.startswith("test1") for name in attachment_names))
        self.assertTrue(any(name.startswith("test2") for name in attachment_names))

        attachment_contents = [a[1] for a in sent_email.attachments]
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

        expected_prefix = "mail/ucretler-ve-planlar/"
        self.assertTrue(attachment.file.name.startswith(expected_prefix))


class DirectEmailTest(TestCase):
    def setUp(self):
        mail.outbox.clear()
        EmailQueue.objects.all().delete()
        DirectEmail.objects.all().delete()

    @patch(
        "newsletter.management.commands.process_email_queue.Command._acquire_lock",
        return_value=True,
    )
    @patch("newsletter.management.commands.process_email_queue.Command._release_lock")
    def test_send_direct_email(self, mock_release, mock_acquire):
        direct_email = DirectEmail.objects.create(
            to_email="recipient@example.com",
            subject="Direct Subject Test Direct",
            body="Direct **Markdown** Body",
        )
        send_direct_email(direct_email)

        call_command("process_email_queue", rate=100)

        sent_email = None
        for out_email in mail.outbox:
            if out_email.subject == "Direct Subject Test Direct":
                sent_email = out_email
                break

        self.assertIsNotNone(sent_email, "Expected email was not in outbox")

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
