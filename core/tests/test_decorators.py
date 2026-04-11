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

    def test_raises_value_error_if_both_default_and_default_factory_provided(self):
        with self.assertRaises(ValueError):

            @log_exceptions(default=1, default_factory=lambda: 2)
            def some_func():
                pass

    def test_uses_default_factory(self):
        @log_exceptions(default_factory=lambda *args, **kwargs: args[0] + 1)
        def broken(x):
            raise ValueError("boom")

        with self.assertLogs("core.tests.test_decorators", level="ERROR"):
            result = broken(5)

        self.assertEqual(result, 6)

    def test_filters_by_exception_types(self):
        @log_exceptions(exception_types=(TypeError,))
        def broken():
            raise ValueError("not caught")

        with self.assertRaises(ValueError):
            broken()

    def test_uses_custom_logger_name(self):
        @log_exceptions(logger_name="custom_logger")
        def broken():
            raise ValueError("boom")

        with self.assertLogs("custom_logger", level="ERROR") as logs:
            broken()

        self.assertEqual(logs.records[0].name, "custom_logger")

    def test_default_message_when_none_provided(self):
        @log_exceptions()
        def some_broken_func():
            raise ValueError("boom")

        with self.assertLogs("core.tests.test_decorators", level="ERROR") as logs:
            some_broken_func()

        self.assertIn("Unhandled error in some_broken_func", logs.output[0])
