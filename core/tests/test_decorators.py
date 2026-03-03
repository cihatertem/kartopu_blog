from django.test import SimpleTestCase

from core.decorators import log_exceptions


class LogExceptionsDecoratorTests(SimpleTestCase):
    def test_logs_message_without_format_placeholders(self):
        @log_exceptions(default=None, message="Error getting cover image size")
        def broken():
            raise ValueError("boom")

        with self.assertLogs("core.tests.test_decorators", level="ERROR") as logs:
            result = broken()

        self.assertIsNone(result)
        self.assertEqual(len(logs.records), 1)
        self.assertIn("Error getting cover image size", logs.output[0])

    def test_logs_message_with_function_name_placeholder(self):
        @log_exceptions(default=None, message="Avatar resizing failed: %s")
        def resize_avatar():
            raise ValueError("boom")

        with self.assertLogs("core.tests.test_decorators", level="ERROR") as logs:
            result = resize_avatar()

        self.assertIsNone(result)
        self.assertEqual(len(logs.records), 1)
        self.assertIn("Avatar resizing failed: resize_avatar", logs.output[0])

    def test_does_not_include_traceback_by_default(self):
        @log_exceptions(default=None, message="Plain log")
        def broken():
            raise ValueError("boom")

        with self.assertLogs("core.tests.test_decorators", level="ERROR") as logs:
            broken()

        self.assertIsNone(logs.records[0].exc_info)

    def test_can_include_traceback_when_requested(self):
        @log_exceptions(default=None, message="With traceback", include_traceback=True)
        def broken():
            raise ValueError("boom")

        with self.assertLogs("core.tests.test_decorators", level="ERROR") as logs:
            broken()

        self.assertIsNotNone(logs.records[0].exc_info)
