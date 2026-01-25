from io import BytesIO

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.files.base import ContentFile
from django.core.files.storage import Storage, default_storage
from django.db import models
from django.utils.deconstruct import deconstructible
from django.utils.text import slugify
from PIL import Image, ImageOps

from core.mixins import TimeStampedModelMixin, UUIDModelMixin

# Create your models here.


@deconstructible
class OverWriteAvatarStorage(Storage):
    _storage = default_storage

    def _open(self, name, mode="rb"):
        return self._storage.open(name, mode)

    def _save(self, name, content):
        return self._storage.save(name, content)

    def delete(self, name):
        return self._storage.delete(name)

    def exists(self, name):
        return self._storage.exists(name)

    def url(self, name):
        return self._storage.url(name)

    def size(self, name):
        return self._storage.size(name)

    def get_available_name(self, name: str, max_length: int | None = None) -> str:
        if self._storage.exists(name):
            self._storage.delete(name)
        return name


def user_avatar_upload_path(instance: "User", filename: str) -> str:
    extension = filename.split(".")[-1].lower()
    filename = f"avatar.{extension}"

    base_name = instance.full_name or str(instance.email).split("@")[0]
    safe_name = slugify(base_name)
    return f"avatars/{safe_name}/{filename}"


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Kullanıcıların bir email adresi olmalı")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Süper kullanıcı 'is_staff=True' olmalı.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Süper kullanıcı 'is_superuser=True' olmalı.")

        return self.create_user(email, password, **extra_fields)


class User(  # pyright: ignore[reportIncompatibleVariableOverride]
    UUIDModelMixin,
    TimeStampedModelMixin,
    AbstractUser,
):
    username = None
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30, blank=True)
    email = models.EmailField(unique=True)
    bio = models.TextField(blank=True)
    website = models.URLField(blank=True)
    twitter = models.URLField(blank=True)
    github = models.URLField(blank=True)
    linkedin = models.URLField(blank=True)
    instagram = models.URLField(blank=True)
    youtube = models.URLField(blank=True)
    avatar = models.ImageField(
        upload_to=user_avatar_upload_path,  # pyright: ignore[reportArgumentType]
        storage=OverWriteAvatarStorage(),
        blank=True,
        null=True,
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()  # pyright: ignore[reportAssignmentType]

    MAX_AVATAR_SIZE = (800, 800)

    class Meta:  # type: ignore
        verbose_name = "Kullanıcı"
        verbose_name_plural = "Kullanıcılar"

    def save(self, *args: object, **kwargs: object) -> None:
        super().save(*args, **kwargs)  # pyright: ignore[reportArgumentType]
        if self.avatar:
            try:
                self._resize_avatar()
            except Exception:
                pass  # Hata durumunda avatar olduğu gibi kalır

    def __str__(self) -> str:
        first_name = str(self.first_name) or ""
        last_name = str(self.last_name) or ""
        full_name = f"{first_name} {last_name}".strip().title()

        return full_name if full_name else str(self.email)

    @property
    def full_name(self) -> str:
        return self.get_full_name().title()

    def _resize_avatar(self) -> None:
        if not self.avatar:
            return

        self.avatar.open("rb")
        try:
            with Image.open(self.avatar) as img:
                img = ImageOps.exif_transpose(img)

                if (
                    img.height <= self.MAX_AVATAR_SIZE[1]
                    and img.width <= self.MAX_AVATAR_SIZE[0]
                ):
                    return  # No need to resize

                img = img.convert("RGB")
                img.thumbnail(self.MAX_AVATAR_SIZE)
                buffer = BytesIO()
                img.save(buffer, format="JPEG", quality=85)
        finally:
            self.avatar.close()

        content = ContentFile(buffer.getvalue())
        storage = self.avatar.storage
        name = self.avatar.name
        if storage.exists(name):
            storage.delete(name)
        storage.save(name, content)
