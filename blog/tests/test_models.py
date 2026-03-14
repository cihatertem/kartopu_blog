from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from blog.models import BlogPost, BlogPostImage, Category, Tag

User = get_user_model()


class BlogModelsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="models@example.com", password="password"
        )
        self.category = Category.objects.create(name="Tech Models", slug="tech-models")

    def test_category_str_and_url(self):
        self.assertEqual(str(self.category), "Tech Models")
        self.assertEqual(
            self.category.get_absolute_url(), "/blog/category/tech-models/"
        )

    def test_category_save_slug(self):
        cat = Category(name="New Cat")
        cat.save()
        self.assertEqual(cat.slug, "new-cat")

    def test_tag_str_and_url(self):
        tag = Tag.objects.create(name="Python Models")
        self.assertEqual(str(tag), "Python Models")
        self.assertEqual(tag.get_absolute_url(), "/blog/tag/python-models/")

        tag2 = Tag(name="Go Models")
        tag2.save()
        self.assertEqual(tag2.slug, "go-models")

    def test_blogpost_str_and_url(self):
        post = BlogPost.objects.create(title="My Post", author=self.user)
        self.assertEqual(str(post), "My Post")
        self.assertEqual(post.get_absolute_url(), "/blog/my-post/")

    def test_blogpost_canonical_and_slug(self):
        post = BlogPost(title="Canonical Post", author=self.user)
        post.save()
        self.assertEqual(post.slug, "canonical-post")
        self.assertEqual(
            post.canonical_url, "https://kartopu.money/blog/canonical-post/"
        )

        post2 = BlogPost(
            title="T2", slug="t2", canonical_url="http://x.com", author=self.user
        )
        post2.save()
        self.assertEqual(post2.slug, "t2")
        self.assertEqual(post2.canonical_url, "http://x.com")

    def test_blogpost_published_at_auto(self):
        post = BlogPost.objects.create(
            title="Auto Pub", author=self.user, status=BlogPost.Status.DRAFT
        )
        self.assertIsNone(post.published_at)

        post.status = BlogPost.Status.PUBLISHED
        post.save()
        self.assertIsNotNone(post.published_at)

    def test_blogpost_effective_meta(self):
        post = BlogPost(title="My Title", author=self.user)
        self.assertEqual(post.effective_meta_title, "My Title | Kartopu Money")

        post.meta_title = "SEO Title"
        self.assertEqual(post.effective_meta_title, "SEO Title | Kartopu Money")

        self.assertEqual(post.effective_meta_description, "")
        post.excerpt = "Short"
        self.assertEqual(post.effective_meta_description, "Short")
        post.meta_description = "SEO Desc"
        self.assertEqual(post.effective_meta_description, "SEO Desc")

    @patch("blog.models.optimize_uploaded_image_field")
    def test_blogpost_cover_optimize(self, mock_opt):
        import io

        from PIL import Image

        file = io.BytesIO()
        image = Image.new("RGB", (100, 100), "white")
        image.save(file, "JPEG")
        file.seek(0)

        cover = SimpleUploadedFile("cover.jpg", file.read(), content_type="image/jpeg")
        post = BlogPost.objects.create(
            title="Img Post", author=self.user, cover_image=cover
        )

        mock_opt.assert_called_once()
        self.assertEqual(mock_opt.call_args[0][0].name, post.cover_image.name)

        mock_opt.reset_mock()
        post.title = "Img Post Updated"
        post.save()
        mock_opt.assert_not_called()

    @patch("blog.models.build_responsive_rendition")
    def test_blogpost_renditions(self, mock_build):
        mock_build.return_value = {"src": "x"}
        post = BlogPost(title="Render", author=self.user)

        self.assertIsNone(post.cover_rendition)
        self.assertIsNone(post.cover_thumb_rendition)

        post.cover_image = "dummy.jpg"

        if "cover_rendition" in post.__dict__:
            del post.__dict__["cover_rendition"]
        if "cover_thumb_rendition" in post.__dict__:
            del post.__dict__["cover_thumb_rendition"]

        self.assertEqual(post.cover_rendition, {"src": "x"})
        self.assertEqual(post.cover_thumb_rendition, {"src": "x"})

    @patch("blog.models.optimize_uploaded_image_field")
    def test_blogpostimage_optimize(self, mock_opt):
        post = BlogPost.objects.create(title="Host", author=self.user)
        import io

        from PIL import Image

        file = io.BytesIO()
        image = Image.new("RGB", (100, 100), "white")
        image.save(file, "JPEG")
        file.seek(0)

        img_file = SimpleUploadedFile("img.jpg", file.read(), content_type="image/jpeg")
        bpi = BlogPostImage.objects.create(post=post, image=img_file)

        mock_opt.assert_called_once()
        self.assertEqual(str(bpi), "Host - Görsel")

        mock_opt.reset_mock()
        bpi.alt_text = "alt"
        bpi.save()
        mock_opt.assert_not_called()

    @patch("blog.models.build_responsive_rendition")
    def test_blogpostimage_rendition(self, mock_build):
        mock_build.return_value = {"src": "y"}
        post = BlogPost.objects.create(title="Host", author=self.user)
        bpi = BlogPostImage(post=post)

        self.assertIsNone(bpi.rendition)

        bpi.image = "dummy.jpg"

        if "rendition" in bpi.__dict__:
            del bpi.__dict__["rendition"]

        self.assertEqual(bpi.rendition, {"src": "y"})

    def test_upload_paths(self):
        from blog.models import post_cover_upload_path, post_image_upload_path

        post = BlogPost(title="Path Test", slug="path-test")
        post._state.adding = True
        path = post_cover_upload_path(post, "file.jpg")
        self.assertTrue(path.startswith("blog/path-test/cover"))

        post._state.adding = False
        path2 = post_cover_upload_path(post, "file.jpg")
        self.assertTrue(path2.startswith("blog/path-test/cover_guncel"))

        bpi = BlogPostImage(post=post)
        path3 = post_image_upload_path(bpi, "FILE NAME.png")
        self.assertTrue(path3.startswith("blog/path-test/images/file-name_"))
        self.assertTrue(path3.endswith(".png"))
