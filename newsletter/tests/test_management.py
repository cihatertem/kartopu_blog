import os
from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from newsletter.models import EmailQueue, EmailQueueStatus


class ProcessEmailQueueCommandTest(TestCase):
    def setUp(self):
        self.lock_file = "/tmp/process_email_queue.lock"
        if os.path.exists(self.lock_file):
            os.remove(self.lock_file)

        EmailQueue.objects.all().delete()

    def tearDown(self):
        if os.path.exists(self.lock_file):
            os.remove(self.lock_file)

    def test_command_creates_lock_file_and_prevents_multiple_instances(self):
        # Create an artificial lock file
        with open(self.lock_file, "w") as f:
            f.write("1234")

        # Command should exit immediately due to the lock file
        with patch("sys.stdout.write") as mock_stdout:
            call_command("process_email_queue", rate=100)

        self.assertTrue(os.path.exists(self.lock_file))
        # The warning should be printed
        self.assertTrue(
            any(
                "Processor already running or lock file exists." in call.args[0]
                for call in mock_stdout.call_args_list
            )
        )

    def test_stale_processing_rows_reverted_to_pending(self):
        stale_time = timezone.now() - timedelta(minutes=20)

        # We need to set the updated_at field, which is auto-updated on save by TimeStampedModelMixin
        # So we update it using queryset update to bypass auto_now=True
        email = EmailQueue.objects.create(
            subject="Test Stale",
            from_email="from@example.com",
            to_email="to@example.com",
            text_body="body",
            status=EmailQueueStatus.PROCESSING,
        )
        EmailQueue.objects.filter(id=email.id).update(updated_at=stale_time)

        # Run command
        call_command("process_email_queue", rate=100)

        # It should have been reverted to PENDING and then processed to SENT
        email.refresh_from_db()
        self.assertEqual(email.status, EmailQueueStatus.SENT)
        self.assertEqual(len(mail.outbox), 1)

    def test_batch_processing_multiple_emails(self):
        EmailQueue.objects.create(
            subject="Test 1", from_email="f@e.com", to_email="t1@e.com", text_body="1"
        )
        EmailQueue.objects.create(
            subject="Test 2", from_email="f@e.com", to_email="t2@e.com", text_body="2"
        )
        EmailQueue.objects.create(
            subject="Test 3", from_email="f@e.com", to_email="t3@e.com", text_body="3"
        )

        call_command("process_email_queue", rate=100, limit=2)

        # Only 2 should be processed due to the limit
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(
            EmailQueue.objects.filter(status=EmailQueueStatus.SENT).count(), 2
        )
        self.assertEqual(
            EmailQueue.objects.filter(status=EmailQueueStatus.PENDING).count(), 1
        )

    @patch("sys.stderr.write")
    @patch("sys.stdout.write")
    @patch("django.core.mail.EmailMultiAlternatives.send")
    def test_failing_email_handling(self, mock_send, mock_stdout, mock_stderr):
        mock_send.side_effect = Exception("SMTP Connection Error")

        email = EmailQueue.objects.create(
            subject="Test Error",
            from_email="from@example.com",
            to_email="to@example.com",
            text_body="body",
            status=EmailQueueStatus.PENDING,
        )

        call_command("process_email_queue", rate=100)

        email.refresh_from_db()
        self.assertEqual(email.status, EmailQueueStatus.FAILED)
        self.assertEqual(email.error_message, "SMTP Connection Error")
        self.assertEqual(len(mail.outbox), 0)
