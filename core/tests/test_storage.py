from unittest.mock import patch

from django.test import TestCase

from core.storage import S3CompressedManifestStaticStorage


class StorageTest(TestCase):
    @patch(
        "django.contrib.staticfiles.storage.ManifestFilesMixin.load_manifest",
        return_value=({}, ""),
    )
    @patch("storages.backends.s3.S3Storage.__init__", return_value=None)
    def test_instantiation(self, mock_s3_init, mock_load_manifest):
        storage = S3CompressedManifestStaticStorage()
        self.assertIsInstance(storage, S3CompressedManifestStaticStorage)
