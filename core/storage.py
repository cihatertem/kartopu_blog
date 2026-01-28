from __future__ import annotations

from storages.backends.s3 import S3ManifestStaticStorage


class S3CompressedManifestStaticStorage(S3ManifestStaticStorage):
    """
    S3 storage backend that handles hashed filenames for static files.
    Manual compression (Gzip/Brotli) has been removed to rely on CloudFront's
    automatic compression, which is more efficient and easier to maintain.
    """

    pass
