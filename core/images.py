from pathlib import Path

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
