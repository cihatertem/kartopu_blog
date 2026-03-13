import concurrent.futures
import os
import time
from datetime import timedelta

from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from newsletter.models import EmailQueue, EmailQueueStatus


class Command(BaseCommand):
    help = "Processes the email queue with rate limiting."

    def add_arguments(self, parser):
        parser.add_argument(
            "--rate",
            type=int,
            default=10,
            help="Maximum number of emails per second (default: 10).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Number of emails to process in each batch (default: 100).",
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

    def handle(self, *args, **options):
        rate = options["rate"]
        limit = options["limit"]
        daemon = options["daemon"]
        sleep_interval = options["sleep"]
        processing_timeout = options["processing_timeout"]
        send_interval = 1.0 / rate

        # Simple lock to prevent multiple instances
        lock_file = "/tmp/process_email_queue.lock"
        if os.path.exists(lock_file):
            # Check if process is actually running (optional but safer)
            self.stdout.write(
                self.style.WARNING("Processor already running or lock file exists.")
            )
            return

        with open(lock_file, "w") as f:
            f.write(str(os.getpid()))

        if daemon:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Email processor started in daemon mode (Rate: {rate}/sec)."
                )
            )
        try:
            while True:
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

                pending_emails = (
                    EmailQueue.objects.filter(id__in=pending_ids)
                    .select_related("direct_email")
                    .prefetch_related("direct_email__attachments")
                    .order_by("created_at")
                )
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

                sent_count = 0
                failed_count = 0
                emails_to_update = []
                direct_emails_to_update = {}
                attachment_cache = {}

                def send_email_task(email_item, attachment_cache_local):
                    try:
                        message = EmailMultiAlternatives(
                            subject=email_item.subject,
                            body=email_item.text_body,
                            from_email=email_item.from_email,
                            to=[email_item.to_email],
                        )
                        if email_item.html_body:
                            message.attach_alternative(
                                email_item.html_body, "text/html"
                            )

                        if email_item.direct_email:
                            de_id = email_item.direct_email.id
                            if de_id not in attachment_cache_local:
                                attachments_data = []
                                for (
                                    attachment
                                ) in email_item.direct_email.attachments.all():  # pyright: ignore[reportGeneralTypeIssues]
                                    with attachment.file.open("rb") as f:
                                        content = f.read()
                                        attachments_data.append(
                                            (
                                                attachment.file.name.split("/")[-1],
                                                content,
                                            )
                                        )
                                attachment_cache_local[de_id] = attachments_data

                            for filename, content in attachment_cache_local[de_id]:
                                message.attach(filename, content)

                        message.send(fail_silently=False)
                        return (email_item, True, None)
                    except Exception as e:
                        return (email_item, False, e)

                # Pre-populate attachment_cache if needed, though we can safely share it across threads since it's just a dict of lists
                # However, thread-safety of dict updates isn't guaranteed if multiple threads update it simultaneously.
                # Since multiple emails might point to the same direct_email, let's pre-cache all attachments in the main thread
                # to avoid race conditions.
                for email_item in pending_emails:
                    if email_item.direct_email:
                        de_id = email_item.direct_email.id
                        if de_id not in attachment_cache:
                            attachments_data = []
                            for attachment in email_item.direct_email.attachments.all():  # pyright: ignore[reportGeneralTypeIssues]
                                with attachment.file.open("rb") as f:
                                    attachments_data.append(
                                        (
                                            attachment.file.name.split("/")[-1],
                                            f.read(),
                                        )
                                    )
                            attachment_cache[de_id] = attachments_data

                futures = []
                # Max 100 workers, or fewer if count is smaller, but capped at something reasonable.
                # However we want to ensure we don't block the rate limiter if send takes long.
                max_workers = min(100, max(10, rate))

                with concurrent.futures.ThreadPoolExecutor(
                    max_workers=max_workers
                ) as executor:
                    for email_item in pending_emails:
                        start_time = time.time()

                        future = executor.submit(
                            send_email_task, email_item, attachment_cache
                        )
                        futures.append(future)

                        elapsed = time.time() - start_time
                        wait = send_interval - elapsed
                        if wait > 0:
                            time.sleep(wait)

                    # Wait for all futures to complete
                    for future in concurrent.futures.as_completed(futures):
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

                            self.stderr.write(
                                f"Failed to send to {email_item.to_email}: {error_msg}"
                            )
                            failed_count += 1

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

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Batch finished. Sent: {sent_count}, Failed: {failed_count}"
                    )
                )

                if not daemon:
                    break
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("Email processor stopped."))
        finally:
            if os.path.exists(lock_file):
                os.remove(lock_file)
