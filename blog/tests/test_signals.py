from unittest import skipUnless
from unittest.mock import MagicMock, call, patch

from django.contrib.auth import get_user_model
from django.contrib.postgres.search import SearchVector
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, transaction
from django.db.models import Value
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from blog.cache_keys import BLOG_POST_REACTIONS_KEY_PREFIX, NAV_ARCHIVES_KEY, NAV_KEYS
from blog.models import BlogPost, BlogPostImage, BlogPostReaction, Category, Tag
from blog.signals import (
    _delete_local_dir_if_exists,
    _delete_storage_dir_if_exists,
    _delete_storage_file,
    _post_cache_dir,
    _post_cache_storage_dir,
    _post_media_dir,
    _should_rebuild_search_vector,
    blogpost_delete_files,
    category_changed,
    invalidate_nav_cache,
    update_search_vector,
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

        with self.assertLogs("blog.signals", level="ERROR") as cm:
            _delete_storage_dir_if_exists("my_dir")

        self.assertEqual(len(cm.records), 1)
        self.assertEqual(cm.records[0].getMessage(), "Error deleting storage file")

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


class SearchVectorTriggerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="search_author@example.com", password="password"
        )

    def test_should_rebuild_with_update_fields_relevant(self):
        post = BlogPost(title="X", author=self.user)
        self.assertTrue(
            _should_rebuild_search_vector(
                post, created=False, update_fields={"content"}
            )
        )

    def test_should_rebuild_with_update_fields_irrelevant(self):
        post = BlogPost(title="X", author=self.user)
        self.assertFalse(
            _should_rebuild_search_vector(
                post, created=False, update_fields={"view_count"}
            )
        )

    def test_should_rebuild_on_create(self):
        post = BlogPost(title="X", author=self.user)
        self.assertTrue(
            _should_rebuild_search_vector(post, created=True, update_fields=None)
        )

    def test_search_vector_fields_changed_detects_relevant_change(self):
        BlogPost.objects.create(
            title="Original", author=self.user, slug="orig", content="body"
        )
        post = BlogPost.objects.get(slug="orig")
        self.assertEqual(
            post._loaded_search_values,
            {
                "title": "Original",
                "excerpt": "",
                "content": "body",
                "status": BlogPost.Status.DRAFT,
            },
        )
        # İlgisiz alan değişimi -> yeniden üretim gerekmez
        post.is_featured = True
        self.assertFalse(post.search_vector_fields_changed())
        # İlgili alan değişimi -> yeniden üretim gerekir
        post.content = "new body"
        self.assertTrue(post.search_vector_fields_changed())

    def test_search_vector_fields_changed_detects_status_change(self):
        BlogPost.objects.create(
            title="Draft", author=self.user, slug="draft-post"
        )
        post = BlogPost.objects.get(slug="draft-post")
        post.status = BlogPost.Status.PUBLISHED
        self.assertTrue(post.search_vector_fields_changed())

    @patch("blog.signals.connection")
    def test_update_search_vector_skips_non_published(self, mock_connection) -> None:
        # postgresql gibi davranıp yine de taslakta DB'ye dokunmadığını doğrula
        mock_connection.vendor = "postgresql"
        draft = BlogPost.objects.create(
            title="Draft", author=self.user, slug="draft-skip"
        )
        # Erken dönüş sayesinde sqlite üzerinde SearchVector UPDATE'i denenmez.
        with self.assertNumQueries(0):
            self.assertEqual(update_search_vector(draft), 0)
        draft.refresh_from_db()
        self.assertIsNone(draft.search_vector)
        self.assertIsNone(draft.search_vector_exact)

    @patch("blog.signals.BlogPost.objects.filter")
    @patch("blog.signals.connection")
    def test_update_search_vector_builds_both_vectors_in_one_update(
        self, mock_connection: MagicMock, mock_filter: MagicMock
    ) -> None:
        from blog.search import normalize_search_expression

        mock_connection.vendor = "postgresql"
        post = MagicMock(pk=123, status=BlogPost.Status.PUBLISHED)
        post.tags.values_list.return_value.iterator.return_value = iter(
            ["İŞ BANKASI", "MİGROS"]
        )
        mock_filter.return_value.update.return_value = 1

        with patch(
            "blog.signals.normalize_search_expression",
            wraps=normalize_search_expression,
        ) as mock_normalize:
            self.assertEqual(update_search_vector(post), 1)

        mock_normalize.assert_has_calls(
            [
                call(Value("İŞ BANKASI MİGROS")),
                call("title"),
                call("excerpt"),
                call("content"),
            ]
        )
        self.assertEqual(mock_normalize.call_count, 4)
        post.tags.values_list.assert_called_once_with("name", flat=True)
        post.tags.values_list.return_value.iterator.assert_called_once_with()
        mock_filter.assert_called_once_with(
            pk=post.pk, status=BlogPost.Status.PUBLISHED
        )
        mock_filter.return_value.update.assert_called_once()
        vectors = mock_filter.return_value.update.call_args.kwargs
        self.assertEqual(set(vectors), {"search_vector", "search_vector_exact"})
        for field, config in (
            ("search_vector", "turkish"),
            ("search_vector_exact", "simple"),
        ):
            with self.subTest(field=field):
                expected = (
                    SearchVector(
                        normalize_search_expression(Value("İŞ BANKASI MİGROS")),
                        weight="A", config=config,
                    )
                    + SearchVector(
                        normalize_search_expression("title"), weight="B", config=config
                    )
                    + SearchVector(
                        normalize_search_expression("excerpt"), weight="C", config=config
                    )
                    + SearchVector(
                        normalize_search_expression("content"), weight="D", config=config
                    )
                )
                self.assertEqual(vectors[field], expected)

    @patch("blog.signals.BlogPost.objects.filter")
    @patch("blog.signals.connection")
    def test_update_search_vector_returns_zero_when_update_matches_no_rows(
        self, mock_connection: MagicMock, mock_filter: MagicMock
    ) -> None:
        mock_connection.vendor = "postgresql"
        post = MagicMock(pk=123, status=BlogPost.Status.PUBLISHED)
        post.tags.values_list.return_value.iterator.return_value = iter([])
        mock_filter.return_value.update.return_value = 0

        self.assertEqual(update_search_vector(post), 0)
        mock_filter.return_value.update.assert_called_once()

    @patch("blog.signals.connection")
    def test_update_search_vector_skips_non_postgresql(
        self, mock_connection: MagicMock
    ) -> None:
        mock_connection.vendor = "sqlite"
        post = MagicMock(pk=123, status=BlogPost.Status.PUBLISHED)

        with self.assertNumQueries(0):
            self.assertEqual(update_search_vector(post), 0)
        post.tags.values_list.assert_not_called()

    @skipUnless(connection.vendor == "postgresql", "PostgreSQL search vectors required")
    def test_update_search_vector_real_rowcounts_and_single_update(self) -> None:
        post = BlogPost.objects.create(
            title="MİGROS", author=self.user, status=BlogPost.Status.PUBLISHED
        )
        post.tags.add(Tag.objects.create(name="İŞ BANKASI"))

        with CaptureQueriesContext(connection) as queries:
            self.assertEqual(update_search_vector(post), 1)
        self.assertEqual(len(queries), 2)
        updates = [query["sql"] for query in queries if query["sql"].startswith("UPDATE")]
        self.assertEqual(len(updates), 1)
        self.assertIn('"search_vector" =', updates[0])
        self.assertIn('"search_vector_exact" =', updates[0])
        post.refresh_from_db()
        self.assertTrue(post.search_vector)
        self.assertTrue(post.search_vector_exact)

        BlogPost.objects.filter(pk=post.pk).update(status=BlogPost.Status.DRAFT)
        self.assertEqual(update_search_vector(post), 0)
        BlogPost.objects.filter(pk=post.pk).delete()
        self.assertEqual(update_search_vector(post), 0)

    @patch("blog.signals.invalidate_search_cache")
    @patch("blog.signals.update_search_vector")
    def test_post_save_skips_rebuild_when_irrelevant_field_changes(
        self, mock_update_search_vector, mock_invalidate_search_cache
    ):
        BlogPost.objects.create(
            title="Pub",
            author=self.user,
            slug="pub-post",
            status=BlogPost.Status.PUBLISHED,
        )
        post = BlogPost.objects.get(slug="pub-post")
        mock_update_search_vector.reset_mock()
        mock_invalidate_search_cache.reset_mock()
        post.is_featured = True
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            post.save()
        mock_update_search_vector.assert_not_called()
        mock_invalidate_search_cache.assert_not_called()
        self.assertEqual(len(callbacks), 1)
        self.assertEqual(
            callbacks[0].__qualname__,
            "notify_subscribers_on_publish.<locals>.<lambda>",
        )

    @patch("blog.signals.invalidate_search_cache")
    @patch("blog.signals.update_search_vector")
    def test_post_save_rebuilds_when_relevant_field_changes(
        self, mock_update_search_vector, mock_invalidate_search_cache
    ):
        BlogPost.objects.create(
            title="Pub2",
            author=self.user,
            slug="pub-post-2",
            status=BlogPost.Status.PUBLISHED,
        )
        post = BlogPost.objects.get(slug="pub-post-2")
        mock_update_search_vector.reset_mock()
        mock_invalidate_search_cache.reset_mock()
        post.title = "Pub2 Updated"
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            post.save()
            mock_invalidate_search_cache.assert_not_called()
        mock_update_search_vector.assert_called_once_with(post)
        mock_invalidate_search_cache.assert_called_once()
        self.assertEqual(len(callbacks), 2)
        self.assertEqual(callbacks.count(mock_invalidate_search_cache), 1)

    @patch("blog.signals.invalidate_search_cache")
    def test_draft_changes_do_not_invalidate_search_cache(
        self, mock_invalidate_search_cache
    ):
        post = BlogPost.objects.create(
            title="Draft", author=self.user, slug="draft-cache"
        )
        mock_invalidate_search_cache.reset_mock()

        post.title = "Updated Draft"
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            post.save()

        mock_invalidate_search_cache.assert_not_called()
        self.assertEqual(callbacks, [])


class SearchInvalidationCommitTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email="search_commit@example.com", password="password"
        )
        self.post = BlogPost.objects.create(
            title="Published", author=self.user, status=BlogPost.Status.PUBLISHED
        )
        self.draft = BlogPost.objects.create(title="Draft", author=self.user)
        self.tag = Tag.objects.create(name="Search commit tag")

    @patch("blog.signals.invalidate_search_cache")
    def test_create_invalidates_only_published_on_commit(
        self, mock_invalidate: MagicMock
    ) -> None:
        for status in (BlogPost.Status.DRAFT, BlogPost.Status.PUBLISHED):
            with self.subTest(status=status):
                mock_invalidate.reset_mock()
                with self.captureOnCommitCallbacks(execute=True) as callbacks:
                    BlogPost.objects.create(
                        title=f"Create {status}", author=self.user, status=status
                    )
                    mock_invalidate.assert_not_called()
                expected = int(status == BlogPost.Status.PUBLISHED)
                self.assertEqual(len(callbacks), expected * 2)
                self.assertEqual(callbacks.count(mock_invalidate), expected)
                self.assertEqual(mock_invalidate.call_count, expected)

    @patch("blog.signals.invalidate_search_cache")
    def test_publish_and_unpublish_invalidate_on_commit(
        self, mock_invalidate: MagicMock
    ) -> None:
        for update_fields in (None, {"status"}):
            for status in (BlogPost.Status.PUBLISHED, BlogPost.Status.DRAFT):
                with self.subTest(update_fields=update_fields, status=status):
                    post = BlogPost.objects.get(pk=self.draft.pk)
                    post.status = status
                    mock_invalidate.reset_mock()
                    with self.captureOnCommitCallbacks(execute=True) as callbacks:
                        post.save(update_fields=update_fields)
                        mock_invalidate.assert_not_called()
                    expected = 2 if status == BlogPost.Status.PUBLISHED else 1
                    self.assertEqual(len(callbacks), expected)
                    self.assertEqual(callbacks.count(mock_invalidate), 1)
                    mock_invalidate.assert_called_once_with()

    @patch("blog.signals.invalidate_search_cache")
    def test_relevant_changes_invalidate_on_commit(
        self, mock_invalidate: MagicMock
    ) -> None:
        for field in ("title", "excerpt", "content"):
            for targeted in (False, True):
                with self.subTest(field=field, targeted=targeted):
                    post = BlogPost.objects.get(pk=self.post.pk)
                    setattr(post, field, f"Changed {field} {targeted}")
                    mock_invalidate.reset_mock()
                    with self.captureOnCommitCallbacks(execute=True) as callbacks:
                        post.save(update_fields={field} if targeted else None)
                        mock_invalidate.assert_not_called()
                    self.assertEqual(len(callbacks), 2)
                    self.assertEqual(callbacks.count(mock_invalidate), 1)
                    mock_invalidate.assert_called_once_with()

    @patch("blog.signals.invalidate_search_cache")
    @patch("blog.signals.update_search_vector")
    def test_unrelated_changes_do_not_register_callbacks(
        self, mock_update: MagicMock, mock_invalidate: MagicMock
    ) -> None:
        for update_fields in (None, {"is_featured"}):
            with self.subTest(update_fields=update_fields):
                post = BlogPost.objects.get(pk=self.post.pk)
                post.is_featured = not post.is_featured
                with self.captureOnCommitCallbacks(execute=True) as callbacks:
                    post.save(update_fields=update_fields)
                self.assertEqual(len(callbacks), 1)
                self.assertEqual(
                    callbacks[0].__qualname__,
                    "notify_subscribers_on_publish.<locals>.<lambda>",
                )
        mock_update.assert_not_called()
        mock_invalidate.assert_not_called()

    @patch("blog.signals.invalidate_search_cache")
    def test_tag_add_remove_clear_invalidate_on_commit(
        self, mock_invalidate: MagicMock
    ) -> None:
        for action in ("add", "remove", "clear"):
            with self.subTest(action=action):
                if action != "add":
                    self.post.tags.add(self.tag)
                mock_invalidate.reset_mock()
                with self.captureOnCommitCallbacks(execute=True) as callbacks:
                    if action == "clear":
                        self.post.tags.clear()
                    else:
                        getattr(self.post.tags, action)(self.tag)
                    mock_invalidate.assert_not_called()
                self.assertEqual(len(callbacks), 1)
                mock_invalidate.assert_called_once_with()

    @patch("blog.signals.invalidate_search_cache")
    def test_delete_invalidates_only_published_on_commit(
        self, mock_invalidate: MagicMock
    ) -> None:
        for post in (self.draft, self.post):
            with self.subTest(status=post.status):
                mock_invalidate.reset_mock()
                with self.captureOnCommitCallbacks(execute=True) as callbacks:
                    post.delete()
                    mock_invalidate.assert_not_called()
                expected = int(post.status == BlogPost.Status.PUBLISHED)
                self.assertEqual(len(callbacks), expected)
                self.assertEqual(mock_invalidate.call_count, expected)

    @patch("blog.signals.invalidate_search_cache")
    def test_draft_save_and_tags_do_not_register_callbacks(
        self, mock_invalidate: MagicMock
    ) -> None:
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            self.draft.title = "Draft changed"
            self.draft.save(update_fields={"title"})
            self.draft.tags.add(self.tag)
            self.draft.tags.remove(self.tag)
            self.draft.tags.add(self.tag)
            self.draft.tags.clear()
        self.assertEqual(callbacks, [])
        mock_invalidate.assert_not_called()

    @patch("blog.signals.invalidate_search_cache")
    def test_rollback_discards_search_invalidation(
        self, mock_invalidate: MagicMock
    ) -> None:
        self.post.tags.add(self.tag)
        for action in (
            "create", "publish", "unpublish", "content", "add", "remove", "clear", "delete"
        ):
            with self.subTest(action=action):
                post = BlogPost.objects.get(
                    pk=self.draft.pk if action == "publish" else self.post.pk
                )
                mock_invalidate.reset_mock()
                with self.captureOnCommitCallbacks(execute=True) as callbacks:
                    with self.assertRaisesMessage(RuntimeError, "rollback"):
                        with transaction.atomic():
                            if action == "create":
                                BlogPost.objects.create(
                                    title="Rollback", author=self.user,
                                    status=BlogPost.Status.PUBLISHED,
                                )
                            elif action in ("publish", "unpublish"):
                                post.status = (
                                    BlogPost.Status.PUBLISHED if action == "publish"
                                    else BlogPost.Status.DRAFT
                                )
                                post.save(update_fields={"status"})
                            elif action == "content":
                                post.content = "Rolled back content"
                                post.save(update_fields={"content"})
                            elif action == "add":
                                post.tags.add(Tag.objects.create(name="Rollback tag"))
                            elif action == "remove":
                                post.tags.remove(self.tag)
                            elif action == "clear":
                                post.tags.clear()
                            else:
                                post.delete()
                            mock_invalidate.assert_not_called()
                            raise RuntimeError("rollback")
                self.assertEqual(callbacks, [])
                mock_invalidate.assert_not_called()


class BlogPostReactionSignalTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com", password="password"
        )
        self.post = BlogPost.objects.create(
            title="Test Post", author=self.user, slug="test-post"
        )

    @patch("blog.signals.cache.delete")
    def test_reaction_cache_invalidation(self, mock_delete):
        reaction = BlogPostReaction.objects.create(
            post=self.post,
            user=self.user,
            reaction=BlogPostReaction.Reaction.KALP.value,
        )
        # invalidate_nav_cache() de cache.delete'i tetikleyebildiğinden
        # son çağrı yerine herhangi bir çağrıyı kontrol ediyoruz.
        mock_delete.assert_any_call(
            f"{BLOG_POST_REACTIONS_KEY_PREFIX}{self.post.pk}"
        )

        mock_delete.reset_mock()
        reaction.delete()
        mock_delete.assert_any_call(
            f"{BLOG_POST_REACTIONS_KEY_PREFIX}{self.post.pk}"
        )
