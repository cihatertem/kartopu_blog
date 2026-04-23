
from django.test import TransactionTestCase

from newsletter.management.commands.process_email_queue import Command
from newsletter.models import EmailQueue, EmailQueueStatus


class EmailQueueConcurrencyTest(TransactionTestCase):
    def setUp(self):
        EmailQueue.objects.all().delete()
        for i in range(10):
            EmailQueue.objects.create(
                subject=f"Test {i}",
                from_email="f@e.com",
                to_email=f"t{i}@e.com",
                text_body="body",
            )

    def test_get_pending_emails_skips_locked(self):
        command = Command()

        # In a real scenario, we'd need two different connections.
        # But we can simulate it by manually setting some to PROCESSING.

        # Instance 1 gets 5 emails
        batch1 = command._get_pending_emails(processing_timeout=15, limit=5)
        self.assertEqual(len(batch1), 5)

        # Instance 2 should get the remaining 5 emails
        batch2 = command._get_pending_emails(processing_timeout=15, limit=5)
        self.assertEqual(len(batch2), 5)

        # Check no overlap
        batch1_ids = set(e.id for e in batch1)
        batch2_ids = set(e.id for e in batch2)
        self.assertEqual(len(batch1_ids.intersection(batch2_ids)), 0)

        # Verify all are in PROCESSING
        self.assertEqual(
            EmailQueue.objects.filter(status=EmailQueueStatus.PROCESSING).count(), 10
        )
