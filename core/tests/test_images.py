import io
import os
import tempfile
from unittest.mock import MagicMock

from django.core.files.uploadedfile import InMemoryUploadedFile, SimpleUploadedFile
from django.test import TestCase
from PIL import Image

from core.images import optimize_uploaded_image, optimize_uploaded_image_field


class ImageOptimizationTests(TestCase):
    def setUp(self):
        # Create a temporary image file
        self.image_size = (3000, 2000)
        img = Image.new("RGB", self.image_size, color="blue")

        self.temp_file = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        img.save(self.temp_file.name)

    def tearDown(self):
        if os.path.exists(self.temp_file.name):
            os.remove(self.temp_file.name)

    # --- optimize_uploaded_image ---
    def test_optimize_uploaded_image_resizes(self):
        # Arrange
        max_size = 1000

        # Act
        optimize_uploaded_image(self.temp_file.name, max_size=max_size)

        # Assert
        with Image.open(self.temp_file.name) as img:
            self.assertTrue(max(img.size) <= max_size)

    def test_optimize_uploaded_image_invalid_path(self):
        # Arrange
        invalid_path = "/path/to/nonexistent/image.jpg"

        # Act - should catch exception and not raise
        result = optimize_uploaded_image(invalid_path)

        # Assert
        self.assertIsNone(result)

    # --- optimize_uploaded_image_field ---
    def test_optimize_uploaded_image_field_none(self):
        # Act & Assert
        # Should not crash if field is empty or None
        self.assertIsNone(optimize_uploaded_image_field(None))

    def test_optimize_uploaded_image_field_resizes(self):
        # Arrange
        img_buffer = io.BytesIO()
        img = Image.new("RGB", (3000, 2000), color="red")
        img.save(img_buffer, format="JPEG")

        uploaded_file = SimpleUploadedFile(
            "test_upload.jpg", img_buffer.getvalue(), content_type="image/jpeg"
        )

        # Mocking the storage object which the file field normally has
        storage_mock = MagicMock()
        storage_mock.exists.return_value = False
        uploaded_file.storage = storage_mock

        max_size = 1500

        # Act
        optimize_uploaded_image_field(uploaded_file, max_size=max_size)

        # Assert
        # Check storage mock calls to verify saving mechanism
        storage_mock.save.assert_called_once()
        name, content_file = storage_mock.save.call_args[0]

        # Check if the content was resized
        with Image.open(content_file) as optimized_img:
            self.assertTrue(max(optimized_img.size) <= max_size)

    def test_optimize_uploaded_image_field_non_rgb(self):
        # Arrange: RGBA image
        img_buffer = io.BytesIO()
        img = Image.new("RGBA", (1000, 1000), color="blue")
        img.save(img_buffer, format="PNG")

        uploaded_file = SimpleUploadedFile(
            "test_upload.png", img_buffer.getvalue(), content_type="image/png"
        )

        storage_mock = MagicMock()
        storage_mock.exists.return_value = True
        uploaded_file.storage = storage_mock

        # Act
        optimize_uploaded_image_field(uploaded_file, max_size=500)

        # Assert
        # Check that it deleted the old one and saved new one
        storage_mock.delete.assert_called_once()
        storage_mock.save.assert_called_once()
        name, content_file = storage_mock.save.call_args[0]

        with Image.open(content_file) as optimized_img:
            # Check size
            self.assertTrue(max(optimized_img.size) <= 500)
            # Check it was converted to RGB
            self.assertEqual(optimized_img.mode, "RGB")
