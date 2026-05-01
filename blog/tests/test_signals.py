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
    blogpost_delete_files,
    category_changed,
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

    @patch("blog.signals.shutil.rmtree")
    @patch("blog.signals.os.path.isdir")
    def test_delete_local_dir_if_exists_success(self, mock_isdir, mock_rmtree):
        mock_isdir.return_value = True
        _delete_local_dir_if_exists("/tmp/valid/path")
        mock_isdir.assert_called_once_with("/tmp/valid/path")
        mock_rmtree.assert_called_once_with("/tmp/valid/path", ignore_errors=True)

    @patch("blog.signals.shutil.rmtree")
    @patch("blog.signals.os.path.isdir")
    def test_delete_local_dir_if_exists_not_dir(self, mock_isdir, mock_rmtree):
        mock_isdir.return_value = False
        _delete_local_dir_if_exists("/tmp/not/dir")
        mock_isdir.assert_called_once_with("/tmp/not/dir")
        mock_rmtree.assert_not_called()

    @patch("blog.signals.shutil.rmtree")
    @patch("blog.signals.os.path.isdir")
    def test_delete_local_dir_if_exists_empty_path(self, mock_isdir, mock_rmtree):
        _delete_local_dir_if_exists("")
        mock_isdir.assert_not_called()
        mock_rmtree.assert_not_called()

    @patch("blog.signals.shutil.rmtree")
    @patch("blog.signals.os.path.isdir")
    def test_delete_local_dir_if_exists_exception(self, mock_isdir, mock_rmtree):
        mock_isdir.side_effect = Exception("OS Error")

        import logging

        with patch.object(logging.getLogger("blog.signals"), "error") as mock_error:
            _delete_local_dir_if_exists("/tmp/error/path")

            mock_isdir.assert_called_once_with("/tmp/error/path")
            mock_rmtree.assert_not_called()
            mock_error.assert_called_once_with("Error deleting local directory")

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

    @patch("blog.signals.default_storage")
    def test_delete_storage_dir_if_exists_listdir_exception(self, mock_storage):
        def listdir_side_effect(path):
            if path == "my_dir":
                return (["subdir1", "subdir2"], [])
            elif path == "my_dir/subdir1":
                raise Exception("listdir failed")
            elif path == "my_dir/subdir2":
                return ([], ["file.jpg"])
            return ([], [])

        mock_storage.listdir.side_effect = listdir_side_effect
        _delete_storage_dir_if_exists("my_dir")

        mock_storage.delete.assert_called_once_with("my_dir/subdir2/file.jpg")

    @patch("blog.signals.default_storage")
    def test_delete_storage_dir_if_exists_delete_exception(self, mock_storage):
        mock_storage.listdir.return_value = ([], ["file1.jpg", "file2.jpg"])

        def delete_side_effect(path):
            if path == "my_dir/file1.jpg":
                raise Exception("delete failed")

        mock_storage.delete.side_effect = delete_side_effect

        _delete_storage_dir_if_exists("my_dir")

        mock_storage.delete.assert_any_call("my_dir/file1.jpg")
        mock_storage.delete.assert_any_call("my_dir/file2.jpg")
        self.assertEqual(mock_storage.delete.call_count, 2)

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
    def test_blogpostimage_delete_files_direct(self, mock_delete_file):
        from blog.signals import blogpostimage_delete_files

        mock_instance = MagicMock()
        mock_instance.image = "mocked_image_file"

        blogpostimage_delete_files(sender=BlogPostImage, instance=mock_instance)

        mock_delete_file.assert_called_once_with("mocked_image_file")

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
    @patch("blog.signals._post_cache_storage_dir")
    @patch("blog.signals._post_media_dir")
    def test_blogpost_delete_files_s3(
        self,
        mock_post_media_dir,
        mock_post_cache_storage_dir,
        mock_storage_del,
        mock_local_del,
    ):
        mock_post_cache_storage_dir.return_value = "s3_cache_dir"
        mock_post_media_dir.return_value = "local_media_dir"

        with self.settings(USE_S3=True):
            blogpost_delete_files(sender=BlogPost, instance=self.post)

        mock_post_cache_storage_dir.assert_called_once_with(self.post)
        mock_post_media_dir.assert_called_once_with(self.post)
        mock_storage_del.assert_called_once_with("s3_cache_dir")
        mock_local_del.assert_called_once_with("local_media_dir")

    @patch("blog.signals._delete_local_dir_if_exists")
    @patch("blog.signals._delete_storage_dir_if_exists")
    @patch("blog.signals._post_cache_dir")
    @patch("blog.signals._post_media_dir")
    def test_blogpost_delete_files_local(
        self, mock_post_media_dir, mock_post_cache_dir, mock_storage_del, mock_local_del
    ):
        mock_post_cache_dir.return_value = "local_cache_dir"
        mock_post_media_dir.return_value = "local_media_dir"

        with self.settings(USE_S3=False):
            blogpost_delete_files(sender=BlogPost, instance=self.post)

        mock_post_cache_dir.assert_called_once_with(self.post)
        mock_post_media_dir.assert_called_once_with(self.post)
        mock_storage_del.assert_not_called()
        mock_local_del.assert_any_call("local_cache_dir")
        mock_local_del.assert_any_call("local_media_dir")
        self.assertEqual(mock_local_del.call_count, 2)

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
        from django.conf import settings

        from blog.cache_keys import NAV_ARCHIVES_KEY

        expected_keys = list(NAV_KEYS)
        expected_keys.remove(NAV_ARCHIVES_KEY)
        for lang_code, _ in getattr(settings, "LANGUAGES", [("tr", "Turkish")]):
            expected_keys.append(f"{NAV_ARCHIVES_KEY}:{lang_code}")

        invalidate_nav_cache()
        mock_delete_many.assert_called_once_with(expected_keys)

    @patch("blog.signals.invalidate_nav_cache")
    def test_category_changed_signal(self, mock_invalidate):
        Category.objects.create(name="New Cat")
        mock_invalidate.assert_called()

    @patch("blog.signals.invalidate_nav_cache")
    def test_category_changed_exception_handling(self, mock_invalidate):
        mock_invalidate.side_effect = Exception("Cache error")
        with self.assertRaises(Exception) as context:
            category_changed(sender=Category)
        self.assertEqual(str(context.exception), "Cache error")

    @patch("blog.signals.invalidate_nav_cache")
    def test_tag_changed_signal(self, mock_invalidate):
        Tag.objects.create(name="New Tag")
        mock_invalidate.assert_called()

    @patch("blog.signals.invalidate_nav_cache")
    def test_post_changed_signal(self, mock_invalidate):
        self.post.title = "Updated Title"
        self.post.save()
        mock_invalidate.assert_called()

    @patch("blog.signals.update_search_vector")
    @patch("blog.signals.invalidate_nav_cache")
    def test_post_tags_changed_signal(self, mock_invalidate, mock_update_search_vector):
        tag = Tag.objects.create(name="T1")
        mock_invalidate.reset_mock()
        mock_update_search_vector.reset_mock()

        self.post.tags.add(tag)
        mock_invalidate.assert_called()
        mock_update_search_vector.assert_called_with(self.post)

        mock_invalidate.reset_mock()
        mock_update_search_vector.reset_mock()
        self.post.tags.remove(tag)
        mock_invalidate.assert_called()
        mock_update_search_vector.assert_called_with(self.post)

        self.post.tags.add(tag)
        mock_invalidate.reset_mock()
        mock_update_search_vector.reset_mock()
        self.post.tags.clear()
        mock_invalidate.assert_called()
        mock_update_search_vector.assert_called_with(self.post)
