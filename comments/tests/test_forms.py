from django.test import TestCase

from comments.forms import CommentForm
from comments.models import MAX_COMMENT_LENGTH


class CommentFormTests(TestCase):
    def test_valid_body(self):
        form = CommentForm(data={"body": "This is a valid comment."})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["body"], "This is a valid comment.")

    def test_body_stripped(self):
        form = CommentForm(
            data={"body": "  This comment has leading and trailing spaces.  "}
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(
            form.cleaned_data["body"], "This comment has leading and trailing spaces."
        )

    def test_body_max_length(self):
        body = "a" * MAX_COMMENT_LENGTH
        form = CommentForm(data={"body": body})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["body"], body)

    def test_body_exceeds_max_length(self):
        body = "a" * (MAX_COMMENT_LENGTH + 1)
        form = CommentForm(data={"body": body})
        self.assertFalse(form.is_valid())
        self.assertIn("body", form.errors)
        self.assertEqual(
            form.errors["body"][0],
            f"Yorum en fazla {MAX_COMMENT_LENGTH} karakter olabilir.",
        )

    def test_empty_body(self):
        form = CommentForm(data={"body": ""})
        self.assertFalse(form.is_valid())
        self.assertIn("body", form.errors)

    def test_whitespace_only_body(self):
        form = CommentForm(data={"body": "   "})
        self.assertFalse(form.is_valid())
        self.assertIn("body", form.errors)
