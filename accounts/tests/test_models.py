import io
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image

from accounts.models import User


def create_image(width, height, format="JPEG"):
    file = io.BytesIO()
    image = Image.new("RGB", (width, height), "white")
    image.save(file, format)
    file.seek(0)
    return SimpleUploadedFile(
        f"test_image.{format.lower()}",
        file.read(),
        content_type=f"image/{format.lower()}",
    )


class UserAvatarResizeTests(TestCase):
    def test_no_avatar(self):
        user = User.objects.create_user(email="test@example.com", password="password")
        self.assertFalse(user.avatar)
        # Should not raise any errors
        user._resize_avatar()

    def test_resize_avatar_small_image(self):
        small_image = create_image(400, 400)
        user = User(email="small@example.com", password="password", first_name="Small")
        user.avatar = small_image
        user.save()

        # Verify it wasn't resized down further
        user.refresh_from_db()
        with Image.open(user.avatar) as img:
            self.assertEqual(img.size, (400, 400))

    def test_resize_avatar_large_image(self):
        large_image = create_image(1000, 1000)
        user = User(email="large@example.com", password="password", first_name="Large")
        user.avatar = large_image
        user.save()

        # Verify it was resized
        user.refresh_from_db()
        with Image.open(user.avatar) as img:
            self.assertTrue(img.width <= 800)
            self.assertTrue(img.height <= 800)
            self.assertEqual(img.size, (800, 800))

    def test_resize_avatar_non_square_image(self):
        rectangular_image = create_image(1200, 600)
        user = User(email="rect@example.com", password="password", first_name="Rect")
        user.avatar = rectangular_image
        user.save()

        user.refresh_from_db()
        with Image.open(user.avatar) as img:
            # Thumbnail maintains aspect ratio
            self.assertEqual(img.size, (800, 400))

    def test_resize_avatar_transposes_exif(self):
        file = io.BytesIO()
        # Mock an image with an EXIF orientation tag
        image = Image.new("RGB", (1000, 800), "white")

        # Since generating EXIF data from scratch is complex, we just mock `ImageOps.exif_transpose`
        # and see if it's called with our image when `_resize_avatar` runs

        image.save(file, "JPEG")
        test_uploaded_file = SimpleUploadedFile(
            "exif_test_image.jpg", file.getvalue(), content_type="image/jpeg"
        )

        user = User(email="exif@example.com", password="password", first_name="Exif")

        with patch("accounts.models.ImageOps.exif_transpose") as mock_transpose:
            # Tell the mock to just return the same image instead of doing work
            mock_transpose.return_value = image.copy()
            user.avatar = test_uploaded_file
            user.save()

            # The method should have been called
            mock_transpose.assert_called_once()

        # The user was saved and resized to standard bounds
        user.refresh_from_db()
        with Image.open(user.avatar) as img:
            self.assertEqual(img.size, (800, 640))  # 1000x800 scales down to 800x640

    def test_resize_avatar_error_handling(self):
        # We bypass user.save() which has signal hooks from ImageKit that crash on bad images
        # Instead, we directly test that `_resize_avatar` safely catches and logs exceptions
        user = User(email="error@example.com", password="password", first_name="Error")
        user.save()  # Save cleanly first

        from django.core.files.base import ContentFile

        user.avatar.save(
            "bad.jpg", ContentFile(b"this is not a valid image"), save=False
        )

        # Test that calling the function wrapped by @log_exceptions does not throw
        try:
            # We call the method, expecting the UnidentifiedImageError to be swallowed
            # by the @log_exceptions decorator
            user._resize_avatar()
        except Exception as e:
            self.fail(f"_resize_avatar raised {type(e).__name__} unexpectedly!")
