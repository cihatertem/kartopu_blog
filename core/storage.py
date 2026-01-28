from __future__ import annotations

import gzip
import importlib.util
import mimetypes
from io import BytesIO

from django.contrib.staticfiles.storage import ManifestFilesMixin
from storages.backends.s3 import S3ManifestStaticStorage, S3Storage

if importlib.util.find_spec("brotli") is not None:
    import brotli
else:
    brotli = None


COMPRESSIBLE_EXTENSIONS = {
    ".css",
    ".js",
    ".html",
    ".svg",
    ".json",
    ".xml",
    ".txt",
    ".map",
}


class S3CompressedManifestStaticStorage(S3ManifestStaticStorage):
    """
    S3 storage backend that handles hashed filenames for static files.
    Manual compression (Gzip/Brotli) has been removed to rely on CloudFront's
    automatic compression, which is more efficient and easier to maintain.
    """

    pass


class S3CompressedManifestStaticStorage_Old(ManifestFilesMixin, S3Storage):
    def post_process(self, paths, dry_run=False, **options):
        for name, processed, processed_content in super().post_process(
            paths, dry_run=dry_run, **options
        ):
            yield name, processed, processed_content

            if dry_run or not processed or not self._is_compressible(name):
                continue

            with self.open(name, "rb") as source:
                original = source.read()

            content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"

            gzip_buffer = BytesIO()
            with gzip.GzipFile(
                filename=name, mode="wb", fileobj=gzip_buffer
            ) as gzip_file:
                gzip_file.write(original)
            self._save_compressed(
                f"{name}.gz",
                gzip_buffer.getvalue(),
                content_type,
                "gzip",
            )

            if brotli is not None:
                brotli_content = brotli.compress(original)
                self._save_compressed(
                    f"{name}.br",
                    brotli_content,
                    content_type,
                    "br",
                )

    def _is_compressible(self, name: str) -> bool:
        lowered = name.lower()
        if lowered.endswith(".gz") or lowered.endswith(".br"):
            return False
        return any(lowered.endswith(ext) for ext in COMPRESSIBLE_EXTENSIONS)

    def _save_compressed(
        self,
        name: str,
        content: bytes,
        content_type: str,
        content_encoding: str,
    ) -> None:
        cleaned_name = self.clean_name(name)
        normalize = getattr(self, "_normalize_name", None) or getattr(
            self, "normalize_name", None
        )
        normalized_name = (
            normalize(cleaned_name) if callable(normalize) else cleaned_name
        )
        params = self.get_object_parameters(cleaned_name)
        params.setdefault("ContentType", content_type)
        params["ContentEncoding"] = content_encoding
        self.bucket.Object(normalized_name).put(Body=content, **params)
