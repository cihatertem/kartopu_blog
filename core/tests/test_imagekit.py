from collections import namedtuple
from unittest.mock import MagicMock

from django.test import TestCase

from core.imagekit import (
    _file_url,
    _safe_spec_dimensions,
    _safe_spec_url,
    build_responsive_rendition,
    safe_file_url,
)

MockFile = namedtuple("MockFile", ["url"])


class MockStorage:
    pass


class S3MockStorage:
    __module__ = "storages.backends.s3"


class MockSpec:
    def __init__(self, url, width, height, storage=None):
        self.url = url
        self.width = width
        self.height = height
        if storage:
            self.storage = storage
        else:
            self.storage = MockStorage()


class ImagekitTests(TestCase):
    # --- safe_file_url ---
    def test_safe_file_url_with_none(self):
        self.assertIsNone(safe_file_url(None))

    def test_safe_file_url_with_valid_field(self):
        field = MockFile(url="http://test.com/img.jpg")
        self.assertEqual(safe_file_url(field), "http://test.com/img.jpg")

    def test_safe_file_url_exception_handling(self):
        # Arrange
        class BrokenField:
            @property
            def url(self):
                raise ValueError("Boom")

        # Act
        result = safe_file_url(BrokenField())

        # Assert
        self.assertIsNone(result)

    # --- _safe_spec_url ---
    def test_safe_spec_url_valid(self):
        spec = MockSpec(url="/rendition.jpg", width=100, height=100)
        self.assertEqual(_safe_spec_url(spec, "fallback.jpg"), "/rendition.jpg")

    def test_safe_spec_url_exception(self):
        class BrokenSpec:
            @property
            def url(self):
                raise ValueError("Boom")

        self.assertEqual(_safe_spec_url(BrokenSpec(), "fallback.jpg"), "fallback.jpg")

    # --- _safe_spec_dimensions ---
    def test_safe_spec_dimensions_valid(self):
        spec = MockSpec(url="", width=800, height=600)
        self.assertEqual(_safe_spec_dimensions(spec, (100, 100)), (800, 600))

    def test_safe_spec_dimensions_s3_storage_fallback(self):
        spec = MockSpec(url="", width=800, height=600, storage=S3MockStorage())
        self.assertEqual(_safe_spec_dimensions(spec, (100, 100)), (100, 100))

    def test_safe_spec_dimensions_invalid_dimensions(self):
        spec = MockSpec(url="", width=0, height=0)
        self.assertEqual(_safe_spec_dimensions(spec, (100, 100)), (100, 100))

        spec_negative = MockSpec(url="", width=-10, height=-10)
        self.assertEqual(_safe_spec_dimensions(spec_negative, (100, 100)), (100, 100))

    def test_safe_spec_dimensions_exception(self):
        class BrokenSpec:
            @property
            def width(self):
                raise ValueError("Boom")

            @property
            def storage(self):
                return MockStorage()

        self.assertEqual(_safe_spec_dimensions(BrokenSpec(), (100, 100)), (100, 100))

    # --- build_responsive_rendition ---
    def test_build_responsive_rendition_no_original(self):
        result = build_responsive_rendition(
            original_field=None, spec_map={}, largest_size=100
        )
        self.assertIsNone(result)

    def test_build_responsive_rendition_success(self):
        # Arrange
        original = MockFile(url="/original.jpg")
        spec_map = {
            100: MockSpec(url="/100.jpg", width=100, height=100),
            200: MockSpec(url="/200.jpg", width=200, height=200),
        }

        # Act
        result = build_responsive_rendition(
            original_field=original, spec_map=spec_map, largest_size=200
        )

        # Assert
        self.assertIsNotNone(result)
        self.assertEqual(result["src"], "/200.jpg")
        self.assertEqual(result["width"], 200)
        self.assertEqual(result["height"], 200)
        self.assertIn("/100.jpg 100w", result["srcset"])
        self.assertIn("/200.jpg 200w", result["srcset"])
        self.assertEqual(result["urls"][100], "/100.jpg")

    def test_build_responsive_rendition_with_exceptions(self):
        # Arrange
        original = MockFile(url="/original.jpg")

        class BrokenSpec:
            def __init__(self, *args, **kwargs):
                pass

            @property
            def url(self):
                raise ValueError("Boom")

            @property
            def width(self):
                raise ValueError("Boom")

            @property
            def storage(self):
                return MockStorage()

        spec_map = {
            100: BrokenSpec(),
            200: BrokenSpec(),
        }

        # Act
        result = build_responsive_rendition(
            original_field=original, spec_map=spec_map, largest_size=200
        )

        # Assert
        self.assertIsNotNone(result)
        # Should fallback to original URL
        self.assertEqual(result["src"], "/original.jpg")
        # Should use fallback dimensions (largest_size, largest_size if not in DEFAULT_RENDITION_DIMENSIONS)
        self.assertEqual(result["width"], 200)
        self.assertEqual(result["height"], 200)
        self.assertEqual(result["urls"][100], "/original.jpg")
