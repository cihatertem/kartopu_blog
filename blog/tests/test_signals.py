from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from blog.cache_keys import NAV_KEYS
from blog.models import BlogPost, BlogPostImage, Category, Tag
from blog.signals import (
    _delete_local_dir_if_exists,
    _delete_storage_dir_if_exists,
    _delete_storage_file,
    _post_cache_dir,
    _post_cache_storage_dir,
    _post_media_dir,
    invalidate_nav_cache,
)

User = get_user_model()


class BlogSignalsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="signal_author@example.com", password="password"
        )
        self.category = Category.objects.create(name="Tech Signals")
        self.post = BlogPost.objects.create(
            title="Signal Post",
            author=self.user,
            category=self.category,
            content="Testing signals",
        )

    def test_post_media_dir(self):
        with self.settings(MEDIA_ROOT="/tmp/media"):
            self.assertEqual(
                _post_media_dir(self.post), f"/tmp/media/blog/{self.post.slug}"
            )

    def test_post_cache_dir(self):
        with self.settings(
            MEDIA_ROOT="/tmp/media", IMAGEKIT_CACHEFILE_DIR="image_cache"
        ):
            self.assertEqual(
                _post_cache_dir(self.post),
                f"/tmp/media/image_cache/blog/{self.post.slug}",
            )

    def test_post_cache_storage_dir(self):
        with self.settings(IMAGEKIT_CACHEFILE_DIR="image_cache"):
            self.assertEqual(
                _post_cache_storage_dir(self.post), f"image_cache/blog/{self.post.slug}"
            )

    @patch("blog.signals.shutil.rmtree")
    @patch("blog.signals.os.path.isdir")
    def test_delete_local_dir_if_exists(self, mock_isdir, mock_rmtree):
        mock_isdir.return_value = True
        _delete_local_dir_if_exists("/fake/path")
        mock_rmtree.assert_called_once_with("/fake/path", ignore_errors=True)

        mock_rmtree.reset_mock()
        mock_isdir.return_value = False
        _delete_local_dir_if_exists("/fake/path2")
        mock_rmtree.assert_not_called()

    @patch("blog.signals.default_storage")
    def test_delete_storage_dir_if_exists(self, mock_storage):
        mock_storage.listdir.return_value = (["subdir"], ["file.jpg", "file2.jpg"])

        mock_storage.listdir.side_effect = [
            (["subdir"], ["file.jpg"]),
            ([], ["subfile.jpg"]),
        ]

        _delete_storage_dir_if_exists("my_dir")

        mock_storage.delete.assert_any_call("my_dir/file.jpg")
        mock_storage.delete.assert_any_call("my_dir/subdir/subfile.jpg")

    def test_delete_storage_dir_if_exists_empty(self):
        self.assertIsNone(_delete_storage_dir_if_exists(""))
        self.assertIsNone(_delete_storage_dir_if_exists(None))

    def test_post_media_dir_empty_settings(self):
        with self.settings(MEDIA_ROOT=""):
            self.assertEqual(_post_media_dir(self.post), "")

    def test_post_cache_dir_empty_settings(self):
        with self.settings(MEDIA_ROOT=""):
            self.assertEqual(_post_cache_dir(self.post), "")

    def test_delete_storage_file_none(self):
        self.assertIsNone(_delete_storage_file(None))

    def test_delete_storage_file(self):
        mock_field = MagicMock()
        mock_field.name = "test.jpg"
        _delete_storage_file(mock_field)
        mock_field.storage.delete.assert_called_once_with("test.jpg")

        mock_field_empty = MagicMock()
        mock_field_empty.name = ""
        _delete_storage_file(mock_field_empty)
        mock_field_empty.storage.delete.assert_not_called()

    @patch("blog.signals._delete_storage_file")
    def test_blogpostimage_delete_signal(self, mock_delete_file):
        import io

        from PIL import Image

        file = io.BytesIO()
        image = Image.new("RGB", (100, 100), "white")
        image.save(file, "JPEG")
        file.seek(0)
        image_file = SimpleUploadedFile(
            "pic.jpg", file.read(), content_type="image/jpeg"
        )

        img = BlogPostImage.objects.create(post=self.post, image=image_file)

        img.delete()

        mock_delete_file.assert_called_once()
        self.assertEqual(mock_delete_file.call_args[0][0].name, img.image.name)

    @patch("blog.signals._delete_local_dir_if_exists")
    @patch("blog.signals._delete_storage_dir_if_exists")
    def test_blogpost_delete_signal_local(self, mock_storage_del, mock_local_del):
        with self.settings(USE_S3=False):
            self.post.delete()
            self.assertEqual(mock_local_del.call_count, 2)  # cache and media
            mock_storage_del.assert_not_called()

    @patch("blog.signals._delete_local_dir_if_exists")
    @patch("blog.signals._delete_storage_dir_if_exists")
    def test_blogpost_delete_signal_s3(self, mock_storage_del, mock_local_del):
        post = BlogPost.objects.create(title="T2", author=self.user)
        with self.settings(USE_S3=True):
            post.delete()
            mock_storage_del.assert_called_once()
            mock_local_del.assert_called_once()

    @patch("blog.signals.cache.delete_many")
    def test_invalidate_nav_cache(self, mock_delete_many):
        invalidate_nav_cache()
        mock_delete_many.assert_called_once_with(NAV_KEYS)

    @patch("blog.signals.invalidate_nav_cache")
    def test_category_changed_signal(self, mock_invalidate):
        Category.objects.create(name="New Cat")
        mock_invalidate.assert_called()

    @patch("blog.signals.invalidate_nav_cache")
    def test_tag_changed_signal(self, mock_invalidate):
        Tag.objects.create(name="New Tag")
        mock_invalidate.assert_called()

    @patch("blog.signals.invalidate_nav_cache")
    def test_post_changed_signal(self, mock_invalidate):
        self.post.title = "Updated Title"
        self.post.save()
        mock_invalidate.assert_called()

    @patch("blog.signals.invalidate_nav_cache")
    def test_post_tags_changed_signal(self, mock_invalidate):
        tag = Tag.objects.create(name="T1")
        mock_invalidate.reset_mock()

        self.post.tags.add(tag)
        mock_invalidate.assert_called()

        mock_invalidate.reset_mock()
        self.post.tags.remove(tag)
        mock_invalidate.assert_called()

        self.post.tags.add(tag)
        mock_invalidate.reset_mock()
        self.post.tags.clear()
        mock_invalidate.assert_called()
