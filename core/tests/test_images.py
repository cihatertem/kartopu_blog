import io
import os
import tempfile
from unittest.mock import MagicMock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image

from core.images import optimize_uploaded_image, optimize_uploaded_image_field


class ImageOptimizationTests(TestCase):
    def setUp(self):
        self.image_size = (3000, 2000)
        img = Image.new("RGB", self.image_size, color="blue")

        self.temp_file = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        img.save(self.temp_file.name)

    def tearDown(self):
        if os.path.exists(self.temp_file.name):
            os.remove(self.temp_file.name)

    def test_optimize_uploaded_image_resizes(self):
        max_size = 1000

        optimize_uploaded_image(self.temp_file.name, max_size=max_size)

        with Image.open(self.temp_file.name) as img:
            self.assertTrue(max(img.size) <= max_size)

    def test_optimize_uploaded_image_invalid_path(self):
        invalid_path = "/path/to/nonexistent/image.jpg"

        with self.assertLogs("core.images", level="ERROR"):
            result = optimize_uploaded_image(invalid_path)

        self.assertIsNone(result)

    def test_optimize_uploaded_image_field_none(self):
        self.assertIsNone(optimize_uploaded_image_field(None))

    def test_optimize_uploaded_image_field_resizes(self):
        img_buffer = io.BytesIO()
        img = Image.new("RGB", (3000, 2000), color="red")
        img.save(img_buffer, format="JPEG")

        uploaded_file = SimpleUploadedFile(
            "test_upload.jpg", img_buffer.getvalue(), content_type="image/jpeg"
        )

        storage_mock = MagicMock()
        storage_mock.exists.return_value = False
        uploaded_file.storage = storage_mock

        max_size = 1500

        optimize_uploaded_image_field(uploaded_file, max_size=max_size)

        storage_mock.save.assert_called_once()
        name, content_file = storage_mock.save.call_args[0]

        with Image.open(content_file) as optimized_img:
            self.assertTrue(max(optimized_img.size) <= max_size)

    def test_optimize_uploaded_image_field_non_rgb(self):
        img_buffer = io.BytesIO()
        img = Image.new("RGBA", (1000, 1000), color="blue")
        img.save(img_buffer, format="PNG")

        uploaded_file = SimpleUploadedFile(
            "test_upload.png", img_buffer.getvalue(), content_type="image/png"
        )

        storage_mock = MagicMock()
        storage_mock.exists.return_value = True
        uploaded_file.storage = storage_mock

        optimize_uploaded_image_field(uploaded_file, max_size=500)

        storage_mock.delete.assert_called_once()
        storage_mock.save.assert_called_once()
        name, content_file = storage_mock.save.call_args[0]

        with Image.open(content_file) as optimized_img:
            self.assertTrue(max(optimized_img.size) <= 500)
            self.assertEqual(optimized_img.mode, "RGB")
