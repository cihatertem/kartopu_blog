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
        user._resize_avatar_in_memory()

    def test_resize_avatar_small_image(self):
        small_image = create_image(400, 400)
        user = User(email="small@example.com", password="password", first_name="Small")
        user.avatar = small_image
        user.save()

        user.refresh_from_db()
        with Image.open(user.avatar) as img:
            self.assertEqual(img.size, (400, 400))

    def test_resize_avatar_large_image(self):
        large_image = create_image(1000, 1000)
        user = User(email="large@example.com", password="password", first_name="Large")
        user.avatar = large_image
        user.save()

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
            self.assertEqual(img.size, (800, 400))

    def test_resize_avatar_transposes_exif(self):
        file = io.BytesIO()
        image = Image.new("RGB", (1000, 800), "white")

        image.save(file, "JPEG")
        test_uploaded_file = SimpleUploadedFile(
            "exif_test_image.jpg", file.getvalue(), content_type="image/jpeg"
        )

        user = User(email="exif@example.com", password="password", first_name="Exif")

        with patch("accounts.models.ImageOps.exif_transpose") as mock_transpose:
            mock_transpose.return_value = image.copy()
            user.avatar = test_uploaded_file
            user.save()

            mock_transpose.assert_called_once()

        user.refresh_from_db()
        with Image.open(user.avatar) as img:
            self.assertEqual(img.size, (800, 640))  # 1000x800 scales down to 800x640

    @patch("accounts.models.Image.open")
    def test_resize_avatar_error_handling(self, mock_image_open):
        user = User(email="error@example.com", password="password", first_name="Error")
        user.save()  # Save cleanly first

        from django.core.files.base import ContentFile

        user.avatar.save("dummy.png", ContentFile(b"not an image"), save=False)

        from PIL import UnidentifiedImageError

        mock_image_open.side_effect = UnidentifiedImageError("Mocked error")

        with self.assertLogs("accounts.models", level="ERROR"):
            try:
                user._resize_avatar_in_memory()
            except Exception as e:
                self.fail(
                    f"_resize_avatar_in_memory raised {type(e).__name__} unexpectedly!"
                )


class UserManagerTests(TestCase):
    def test_create_user(self):
        email = "testuser@example.com"
        password = "testpassword"

        user = User.objects.create_user(email=email, password=password)

        self.assertEqual(user.email, email)
        self.assertTrue(user.check_password(password))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_superuser(self):
        email = "admin@example.com"
        password = "adminpassword"

        superuser = User.objects.create_superuser(email=email, password=password)

        self.assertEqual(superuser.email, email)
        self.assertTrue(superuser.check_password(password))
        self.assertTrue(superuser.is_staff)
        self.assertTrue(superuser.is_superuser)

    def test_create_superuser_missing_email(self):
        password = "adminpassword"

        with self.assertRaisesMessage(
            ValueError, "Süper kullanıcıların bir email adresi olmalı"
        ):
            User.objects.create_superuser(email="", password=password)

    def test_create_superuser_is_staff_false(self):
        email = "admin2@example.com"
        password = "adminpassword"

        with self.assertRaisesMessage(
            ValueError, "Süper kullanıcı 'is_staff=True' olmalı."
        ):
            User.objects.create_superuser(
                email=email, password=password, is_staff=False
            )

    def test_create_superuser_is_superuser_false(self):
        email = "admin3@example.com"
        password = "adminpassword"

        with self.assertRaisesMessage(
            ValueError, "Süper kullanıcı 'is_superuser=True' olmalı."
        ):
            User.objects.create_superuser(
                email=email, password=password, is_superuser=False
            )


class UserModelTests(TestCase):
    def test_str_with_full_name(self):
        user = User.objects.create_user(
            email="test@example.com", first_name="John", last_name="Doe", password="pwd"
        )

        result = str(user)

        self.assertEqual(result, "John Doe")

    def test_str_with_only_email(self):
        user = User.objects.create_user(email="test2@example.com", password="pwd")

        result = str(user)

        self.assertEqual(result, "test2@example.com")

    def test_full_name_property(self):
        user = User.objects.create_user(
            email="test3@example.com",
            first_name="Jane",
            last_name="Smith",
            password="pwd",
        )

        result = user.full_name

        self.assertEqual(result, "Jane Smith")

    def test_avatar_rendition_no_avatar(self):
        user = User.objects.create_user(email="noavatar@example.com", password="pwd")

        result = user.avatar_rendition

        self.assertIsNone(result)

    def test_avatar_rendition_with_avatar(self):
        user = User.objects.create_user(email="avatar@example.com", password="pwd")
        user.avatar = create_image(100, 100)
        user.save()

        result = user.avatar_rendition

        self.assertIsNotNone(result)
        self.assertIn("src", result)
        self.assertIn("srcset", result)
