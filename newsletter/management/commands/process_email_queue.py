import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta

from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand
from django.db import close_old_connections, reset_queries, transaction
from django.utils import timezone

from newsletter.models import EmailQueue, EmailQueueStatus


class Command(BaseCommand):
    help = "Processes the email queue with rate limiting and memory optimization."

    def add_arguments(self, parser):
        parser.add_argument(
            "--rate",
            type=int,
            default=10,
            help="Maximum number of emails per second. AWS SES limit is 14/sec (default: 10).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=50,
            help="Number of emails to process in each batch. Lower is better for t3.micro RAM (default: 50).",
        )
        parser.add_argument(
            "--daemon",
            action="store_true",
            help="Run indefinitely, checking for new emails.",
        )
        parser.add_argument(
            "--sleep",
            type=int,
            default=5,
            help="Seconds to sleep between checks when in daemon mode (default: 5).",
        )
        parser.add_argument(
            "--processing-timeout",
            type=int,
            default=15,
            help="Minutes after which stuck processing rows are moved back to pending (default: 15).",
        )

    def _acquire_lock(self, lock_file: str) -> bool:
        """Attempts to acquire a lock file. Returns True if successful."""
        if os.path.exists(lock_file):
            self.stdout.write(
                self.style.WARNING("Processor already running or lock file exists.")
            )
            return False

        with open(lock_file, "w") as f:
            f.write(str(os.getpid()))
        return True

    def _release_lock(self, lock_file: str) -> None:
        """Releases the lock file if it exists."""
        if os.path.exists(lock_file):
            try:
                os.remove(lock_file)
            except OSError:
                pass

    def _get_pending_emails(self, processing_timeout: int, limit: int):
        """Reverts stuck processing rows to pending and fetches a new batch."""
        stale_before = timezone.now() - timedelta(minutes=processing_timeout)
        EmailQueue.objects.filter(
            status=EmailQueueStatus.PROCESSING,  # pyright: ignore[reportAttributeAccessIssue]
            updated_at__lt=stale_before,
        ).update(status=EmailQueueStatus.PENDING)

        with transaction.atomic():
            pending_ids = list(
                EmailQueue.objects.select_for_update(skip_locked=True)
                .filter(status=EmailQueueStatus.PENDING)
                .order_by("created_at")
                .values_list("id", flat=True)[:limit]
            )

            if pending_ids:
                EmailQueue.objects.filter(
                    id__in=pending_ids,
                    status=EmailQueueStatus.PENDING,
                ).update(status=EmailQueueStatus.PROCESSING)  # pyright: ignore[reportAttributeAccessIssue]

        return (
            EmailQueue.objects.filter(id__in=pending_ids)
            .select_related("direct_email")
            .order_by("created_at")
        )

    def _send_email_task(self, email_item, attachment_contents=None):
        """Builds and sends an individual email with attachments. Evaluated lazily to save RAM."""
        if attachment_contents is None:
            attachment_contents = {}

        try:
            message = EmailMultiAlternatives(
                subject=email_item.subject,
                body=email_item.text_body,
                from_email=email_item.from_email,
                to=[email_item.to_email],
            )
            if email_item.html_body:
                message.attach_alternative(email_item.html_body, "text/html")

            if email_item.direct_email:
                for attachment in getattr(
                    email_item.direct_email, "_prefetched_objects_cache", {}
                ).get("attachments", []):  # pyright: ignore[reportGeneralTypeIssues]
                    if attachment.id in attachment_contents:
                        filename, content = attachment_contents[attachment.id]
                        message.attach(filename, content)
                    else:
                        with attachment.file.open("rb") as f:
                            message.attach(
                                os.path.basename(attachment.file.name), f.read()
                            )

            message.send(fail_silently=False)
            return (email_item, True, None)
        except Exception as e:
            return (email_item, False, e)

    def _handle_future_result(
        self,
        future,
        emails_to_update,
        direct_emails_to_update,
        sent_count,
        failed_count,
    ):
        email_item, success, error_msg = future.result()
        now = timezone.now()

        if success:
            email_item.status = EmailQueueStatus.SENT
            email_item.sent_at = now
            email_item.updated_at = now
            emails_to_update.append(email_item)

            if email_item.direct_email:
                email_item.direct_email.sent_at = now
                direct_emails_to_update[email_item.direct_email.id] = (
                    email_item.direct_email
                )

            sent_count += 1
        else:
            email_item.status = EmailQueueStatus.FAILED
            email_item.error_message = str(error_msg)
            email_item.updated_at = now
            emails_to_update.append(email_item)

            self.stderr.write(f"Failed to send to {email_item.to_email}: {error_msg}")
            failed_count += 1

        return sent_count, failed_count

    def _process_batch(self, pending_emails, rate: int, send_interval: float):
        """Processes a batch of emails using a thread pool."""
        sent_count = 0
        failed_count = 0
        emails_to_update = []
        direct_emails_to_update = {}

        # Deduplicate DirectEmail instances to avoid redundant object tracking
        # and prefetching duplicate instances in memory.
        direct_emails_map = {}
        for email_item in pending_emails:
            if email_item.direct_email:
                de_id = email_item.direct_email.id
                if de_id not in direct_emails_map:
                    direct_emails_map[de_id] = email_item.direct_email
                else:
                    email_item.direct_email = direct_emails_map[de_id]

        unique_direct_emails = list(direct_emails_map.values())

        if unique_direct_emails:
            from django.db.models import prefetch_related_objects

            prefetch_related_objects(unique_direct_emails, "attachments")

        attachment_contents = {}
        # t3.micro constraint: keep workers bounded to avoid CPU/RAM spikes.
        # Capping at max 14 (SES limit) ensures we don't spawn too many threads.
        max_workers = min(14, max(4, rate))

        def fetch_attachment(attachment):
            with attachment.file.open("rb") as f:
                return attachment.id, os.path.basename(attachment.file.name), f.read()

        with ThreadPoolExecutor(max_workers=max_workers) as io_executor:
            io_futures = []
            for direct_email in unique_direct_emails:
                # Bypass .all() overhead by safely accessing _prefetched_objects_cache directly
                prefetched = getattr(direct_email, "_prefetched_objects_cache", {})
                if "attachments" in prefetched:
                    attachments = prefetched["attachments"]
                else:
                    attachments = direct_email.attachments.all()

                for attachment in attachments:
                    if attachment.id not in attachment_contents:
                        attachment_contents[attachment.id] = None
                        io_futures.append(
                            io_executor.submit(fetch_attachment, attachment)
                        )

            for future in as_completed(io_futures):
                att_id, filename, content = future.result()
                attachment_contents[att_id] = (filename, content)

        futures = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for email_item in pending_emails:
                future = executor.submit(
                    self._send_email_task,
                    email_item,
                    attachment_contents,
                )
                futures.append(future)

                # Sleep in the main thread ensures an absolute cap on submission rate
                # and prevents ThreadPoolExecutor from queueing up and hoarding RAM.
                time.sleep(send_interval)

            for future in as_completed(futures):
                sent_count, failed_count = self._handle_future_result(
                    future,
                    emails_to_update,
                    direct_emails_to_update,
                    sent_count,
                    failed_count,
                )

        return sent_count, failed_count, emails_to_update, direct_emails_to_update

    def _update_results(self, emails_to_update, direct_emails_to_update):
        """Bulk updates the statuses of processed emails."""
        if emails_to_update:
            EmailQueue.objects.bulk_update(
                emails_to_update,
                ["status", "sent_at", "updated_at", "error_message"],
            )
        if direct_emails_to_update:
            from newsletter.models import DirectEmail

            DirectEmail.objects.bulk_update(
                list(direct_emails_to_update.values()), ["sent_at"]
            )

    def _run_processing_loop(
        self,
        daemon: bool,
        rate: int,
        sleep_interval: int,
        processing_timeout: int,
        limit: int,
        send_interval: float,
    ):
        """Runs the main processing loop for email queue."""
        while True:
            try:
                # Close stale database connections to prevent connection drops on t3.micro
                close_old_connections()

                pending_emails = self._get_pending_emails(processing_timeout, limit)
                count = len(pending_emails)

                if count == 0:
                    if not daemon:
                        self.stdout.write(self.style.SUCCESS("No pending emails."))
                        break
                    time.sleep(sleep_interval)
                    continue

                self.stdout.write(
                    f"Processing batch of {count} emails at {rate} emails/sec..."
                )

                sent_count, failed_count, emails_to_update, direct_emails_to_update = (
                    self._process_batch(pending_emails, rate, send_interval)
                )

                self._update_results(emails_to_update, direct_emails_to_update)

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Batch finished. Sent: {sent_count}, Failed: {failed_count}"
                    )
                )

                if not daemon:
                    break

            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Error in processing loop: {e}"))
                if not daemon:
                    raise
                time.sleep(sleep_interval)
            finally:
                # Clear Django query log to prevent memory leaks in daemon mode
                reset_queries()

    def handle(self, *args, **options):
        rate = options["rate"]
        limit = options["limit"]
        daemon = options["daemon"]
        sleep_interval = options["sleep"]
        processing_timeout = options["processing_timeout"]

        # Enforce hard limit of 14 for AWS SES
        if rate > 14:
            self.stdout.write(
                self.style.WARNING("Rate clamped to 14 to respect AWS SES limits.")
            )
            rate = 14

        send_interval = 1.0 / rate

        lock_file = "/tmp/process_email_queue.lock"
        if not self._acquire_lock(lock_file):
            return

        if daemon:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Email processor started in daemon mode (Rate: {rate}/sec)."
                )
            )

        try:
            self._run_processing_loop(
                daemon,
                rate,
                sleep_interval,
                processing_timeout,
                limit,
                send_interval,
            )
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Email processor stopped."))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Fatal error: {e}"))
        finally:
            self._release_lock(lock_file)
