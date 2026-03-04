from django.test import TestCase

from newsletter.forms import NewsletterEmailForm


class NewsletterEmailFormTest(TestCase):
    def test_form_valid_with_only_email(self):
        form = NewsletterEmailForm(data={"email": "test@example.com"})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["email"], "test@example.com")
        self.assertEqual(form.cleaned_data["name"], "")

    def test_form_valid_with_email_and_name_honeypot(self):
        form = NewsletterEmailForm(data={"email": "test@example.com", "name": "bot"})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["email"], "test@example.com")
        self.assertEqual(form.cleaned_data["name"], "bot")

    def test_form_invalid_email(self):
        form = NewsletterEmailForm(data={"email": "not-an-email"})
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_form_empty_email(self):
        form = NewsletterEmailForm(data={"email": ""})
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)
