from django.test import TestCase

from core.forms import ContactForm
from core.models import ContactMessage


class ContactFormTests(TestCase):
    def test_clean_name_strips_whitespace(self):
        data = {
            "name": "  John Doe  ",
            "subject": "Test Subject",
            "email": "test@test.com",
            "message": "Hello",
        }
        form = ContactForm(data=data)

        self.assertTrue(form.is_valid())

        self.assertEqual(form.cleaned_data["name"], "John Doe")

    def test_clean_subject_strips_whitespace(self):
        data = {
            "name": "John",
            "subject": "  Important   ",
            "email": "test@test.com",
            "message": "Hello",
        }
        form = ContactForm(data=data)

        self.assertTrue(form.is_valid())

        self.assertEqual(form.cleaned_data["subject"], "Important")

    def test_clean_website_strips_whitespace(self):
        data = {
            "name": "John",
            "subject": "Test",
            "email": "test@test.com",
            "message": "Hello",
            "website": "  https://test.com  ",
        }
        form = ContactForm(data=data)

        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["website"], "https://test.com")

    def test_clean_message_valid(self):
        # Arrange
        data = {
            "name": "John",
            "subject": "Test",
            "email": "test@test.com",
            "message": "  Hello world  ",
        }
        form = ContactForm(data=data)

        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["message"], "Hello world")

    def test_clean_message_too_long(self):
        # Arrange
        long_message = "A" * (ContactMessage.MAX_MESSAGE_LENGTH + 1)
        data = {
            "name": "John",
            "subject": "Test",
            "email": "test@test.com",
            "message": long_message,
        }
        form = ContactForm(data=data)

        self.assertFalse(form.is_valid())
        self.assertIn("message", form.errors)
        self.assertTrue(
            any(
                f"en fazla {ContactMessage.MAX_MESSAGE_LENGTH} karakter" in error
                for error in form.errors["message"]
            )
        )

    def test_none_values_handled_gracefully(self):
        form = ContactForm()
        form.cleaned_data = {
            "name": None,
            "subject": None,
            "message": None,
            "website": None,
        }

        self.assertEqual(form.clean_name(), "")
        self.assertEqual(form.clean_subject(), "")
        self.assertEqual(form.clean_message(), "")
        self.assertEqual(form.clean_website(), "")
