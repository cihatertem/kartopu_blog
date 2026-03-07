import os
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TransactionTestCase

from newsletter.models import (
    DirectEmail,
    DirectEmailAttachment,
    EmailQueue,
    EmailQueueStatus,
)


class ProcessEmailQueuePerformanceTest(TransactionTestCase):
    def setUp(self):
        self.lock_file = "/tmp/process_email_queue.lock"
        if os.path.exists(self.lock_file):
            os.remove(self.lock_file)

        EmailQueue.objects.all().delete()
        DirectEmail.objects.all().delete()
        DirectEmailAttachment.objects.all().delete()

        # Create 50 distinct direct emails, each with 5 attachments
        for d in range(50):
            direct_email = DirectEmail.objects.create(
                subject=f"Benchmark Email {d}",
                to_email=f"test{d}@example.com",
                body="This is a test body.",
            )
            for i in range(5):
                file_content = f"file_content_{i}".encode("utf-8")
                file = SimpleUploadedFile(f"test_file_{i}.txt", file_content)
                DirectEmailAttachment.objects.create(
                    direct_email=direct_email, file=file
                )

            # Create 1 email queue item for each direct email
            EmailQueue.objects.create(
                subject=f"Queue Item {d}",
                from_email="from@example.com",
                to_email=f"to{d}@example.com",
                text_body="Queue item body",
                status=EmailQueueStatus.PENDING,
                direct_email=direct_email,
            )

    def tearDown(self):
        if os.path.exists(self.lock_file):
            os.remove(self.lock_file)

    @patch("sys.stdout.write")
    def test_no_n_plus_one_queries(self, mock_stdout):
        # Without prefetch_related, this would result in ~62 queries (1 for base, 1 to update, 50 to fetch attachments, plus a few others).
        # With prefetch_related, it should be heavily optimized and not scale with the number of emails.
        # We allow up to 15 queries (1 select pending, 1 update pending to processing, 1 select pending_emails + 1 prefetch attachments,
        # 1 update statuses, 1 direct emails update, plus some possible internal save queries).
        with self.assertNumQueries(13):
            call_command("process_email_queue", rate=1000, limit=100)

        # Verify that all emails were processed correctly
        self.assertEqual(
            EmailQueue.objects.filter(status=EmailQueueStatus.SENT).count(), 50
        )
