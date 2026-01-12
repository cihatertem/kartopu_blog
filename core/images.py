from io import BytesIO
from pathlib import Path

from django.core.files.base import ContentFile
from PIL import Image, ImageOps


def optimize_uploaded_image(
    image_path: str,
    max_size: int = 2000,
    quality: int = 85,
) -> None:
    """
    - EXIF orientation düzeltir
    - Uzun kenarı max_size olacak şekilde resize eder
    - Metadata temizler
    - Aynı dosyanın üzerine yazar
    """

    path = Path(image_path)

    with Image.open(path) as img:
        # EXIF orientation düzelt
        img = ImageOps.exif_transpose(img)

        # RGB'ye normalize et
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")

        # Uzun kenarı sınırla
        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

        # Aynı dosyanın üzerine yaz
        img.save(
            path,
            optimize=True,
            quality=quality,
        )


def optimize_uploaded_image_field(
    file_field,
    max_size: int = 2000,
    quality: int = 85,
) -> None:
    if not file_field:
        return

    file_field.open("rb")
    try:
        with Image.open(file_field) as img:
            original_format = img.format or "JPEG"
            img = ImageOps.exif_transpose(img)

            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")

            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

            buffer = BytesIO()
            save_kwargs = {"optimize": True}
            if original_format.upper() in ("JPEG", "JPG", "WEBP"):
                save_kwargs["quality"] = quality  # pyright: ignore[reportArgumentType]
            img.save(buffer, format=original_format, **save_kwargs)
    finally:
        file_field.close()

    content = ContentFile(buffer.getvalue())
    storage = file_field.storage
    name = file_field.name
    if storage.exists(name):
        storage.delete(name)
    storage.save(name, content)
