from unittest.mock import MagicMock, patch

from django.test import TestCase

from core.storage import S3CompressedManifestStaticStorage_Old


class StorageTest(TestCase):
    @patch(
        "django.contrib.staticfiles.storage.ManifestFilesMixin.load_manifest",
        return_value=({}, ""),
    )
    @patch("storages.backends.s3.S3Storage.__init__", return_value=None)
    def test_is_compressible(self, mock_s3_init, mock_load_manifest):
        storage = S3CompressedManifestStaticStorage_Old()
        self.assertTrue(storage._is_compressible("styles.css"))
        self.assertTrue(storage._is_compressible("main.js"))
        self.assertFalse(storage._is_compressible("image.png"))
        self.assertFalse(storage._is_compressible("styles.css.gz"))
        self.assertFalse(storage._is_compressible("main.js.br"))

    @patch(
        "django.contrib.staticfiles.storage.ManifestFilesMixin.load_manifest",
        return_value=({}, ""),
    )
    @patch("storages.backends.s3.S3Storage.__init__", return_value=None)
    @patch("storages.backends.s3.S3Storage.bucket")
    def test_post_process(self, mock_bucket, mock_s3_init, mock_load_manifest):
        storage = S3CompressedManifestStaticStorage_Old()
        storage.open = MagicMock()

        file_mock = MagicMock()
        file_mock.read.return_value = b"body { color: red; }"
        storage.open.return_value.__enter__.return_value = file_mock

        storage._save_compressed = MagicMock()

        with patch(
            "django.contrib.staticfiles.storage.ManifestFilesMixin.post_process"
        ) as mock_super:
            mock_super.return_value = [("styles.css", "styles.css", True)]

            paths = {"styles.css": (MagicMock(), "styles.css")}
            results = list(storage.post_process(paths))

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0][0], "styles.css")

            self.assertTrue(storage._save_compressed.called)

    @patch(
        "django.contrib.staticfiles.storage.ManifestFilesMixin.load_manifest",
        return_value=({}, ""),
    )
    @patch("storages.backends.s3.S3Storage.__init__", return_value=None)
    @patch("storages.backends.s3.S3Storage.bucket", new_callable=MagicMock)
    def test_save_compressed(self, mock_bucket, mock_s3_init, mock_load_manifest):
        storage = S3CompressedManifestStaticStorage_Old()
        storage.clean_name = MagicMock(return_value="test.css.gz")
        storage._normalize_name = MagicMock(return_value="test.css.gz")
        storage.get_object_parameters = MagicMock(return_value={})

        storage._save_compressed("test.css.gz", b"content", "text/css", "gzip")

        mock_bucket.Object.assert_called_with("test.css.gz")
        mock_bucket.Object().put.assert_called_with(
            Body=b"content", ContentType="text/css", ContentEncoding="gzip"
        )
