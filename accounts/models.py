import os
from functools import cached_property
from io import BytesIO

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.deconstruct import deconstructible
from django.utils.text import slugify
from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFill, Transpose
from PIL import Image, ImageOps

from core.imagekit import build_responsive_rendition, invalidate_imagekit_cache
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
    avatar_updated_at = models.DateTimeField(blank=True, null=True)
    avatar_42 = ImageSpecField(
        source="avatar",
        processors=[Transpose(), ResizeToFill(42, 42)],
        format="WEBP",
        options={"quality": 82},
    )
    avatar_64 = ImageSpecField(
        source="avatar",
        processors=[Transpose(), ResizeToFill(64, 64)],
        format="WEBP",
        options={"quality": 82},
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()  # pyright: ignore[reportAssignmentType]

    MAX_AVATAR_SIZE = (800, 800)

    class Meta:  # type: ignore
        verbose_name = "Kullanıcı"
        verbose_name_plural = "Kullanıcılar"

    def save(self, *args: object, **kwargs: object) -> None:
        avatar_uploaded = bool(self.avatar and not self.avatar._committed)
        if avatar_uploaded:
            self.avatar_updated_at = timezone.now()
        super().save(*args, **kwargs)  # pyright: ignore[reportArgumentType]
        if self.avatar:
            try:
                self._resize_avatar()
                if avatar_uploaded:
                    self._invalidate_avatar_cache()
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

    def _invalidate_avatar_cache(self) -> None:
        if not self.avatar or not self.avatar.name:
            return

        cache_dir = getattr(settings, "IMAGEKIT_CACHEFILE_DIR", "cache")
        cache_path = os.path.join(cache_dir, os.path.dirname(self.avatar.name))

        def delete_storage_dir(path: str) -> None:
            try:
                directories, files = default_storage.listdir(path)
                for file_name in files:
                    default_storage.delete(os.path.join(path, file_name))
                for directory in directories:
                    delete_storage_dir(os.path.join(path, directory))
            except Exception:
                pass

        for spec in (self.avatar_42, self.avatar_64):
            invalidate_imagekit_cache(spec)
            try:
                cachefile = getattr(spec, "cachefile", None)
                storage = getattr(cachefile, "storage", None)
                name = getattr(cachefile, "name", "")
                if storage and name and storage.exists(name):
                    storage.delete(name)
            except Exception:
                pass

        delete_storage_dir(cache_path)

    @cached_property
    def avatar_rendition(self) -> dict | None:
        if not self.avatar:
            return None
        rendition = build_responsive_rendition(
            original_field=self.avatar,
            spec_map={
                42: self.avatar_42,
                64: self.avatar_64,
            },
            largest_size=64,
        )
        if not rendition:
            return None
        if self.avatar_updated_at:
            version = int(self.avatar_updated_at.timestamp())
            rendition["src"] = f"{rendition['src']}?v={version}"
            rendition["srcset"] = ", ".join(
                f"{url}?v={version} {size}w"
                for size, url in rendition["urls"].items()
            )
        return rendition
