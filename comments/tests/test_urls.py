from uuid import uuid4

from django.test import SimpleTestCase
from django.urls import resolve, reverse

from comments.views import moderate_comment, post_comment


class CommentUrlsTests(SimpleTestCase):
    def test_post_comment_url_resolves(self):
        post_id = uuid4()
        url = reverse("comments:post_comment", kwargs={"post_id": post_id})
        self.assertEqual(url, f"/comments/post/{post_id}/")
        self.assertEqual(resolve(url).func, post_comment)

    def test_moderate_comment_url_resolves(self):
        comment_id = uuid4()
        url = reverse("comments:moderate_comment", kwargs={"comment_id": comment_id})
        self.assertEqual(url, f"/comments/moderate/{comment_id}/")
        self.assertEqual(resolve(url).func, moderate_comment)
