import uuid

from django.db import connection, models
from django.test import TestCase

from core.mixins import SlugMixin, TimeStampedModelMixin, UUIDModelMixin


class DummyModel(UUIDModelMixin, TimeStampedModelMixin, SlugMixin):
    name = models.CharField(max_length=255)

    class Meta:
        app_label = "core"
        # Since it's a dynamic test model, we just mock the db table
        db_table = "test_dummy_model"


class MixinsTests(TestCase):
    @classmethod
    def setUpClass(cls):
        # We need to create the table without Django trying to manage transactions inside schema_editor.
        super().setUpClass()
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS test_dummy_model (
                    id char(32) NOT NULL PRIMARY KEY,
                    created_at datetime NOT NULL,
                    updated_at datetime NOT NULL,
                    slug varchar(255) UNIQUE,
                    name varchar(255) NOT NULL
                );
                """
            )

    @classmethod
    def tearDownClass(cls):
        with connection.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS test_dummy_model;")
        super().tearDownClass()

    def test_uuid_mixin(self):
        # Act
        obj = DummyModel.objects.create(name="Test UUID")

        # Assert
        self.assertIsNotNone(obj.id)
        self.assertIsInstance(obj.id, uuid.UUID)

    def test_timestamped_mixin(self):
        # Act
        obj = DummyModel.objects.create(name="Test Timestamps")

        # Assert
        self.assertIsNotNone(obj.created_at)
        self.assertIsNotNone(obj.updated_at)

        # Update and check
        old_updated_at = obj.updated_at
        obj.name = "Updated"
        obj.save()

        self.assertGreater(obj.updated_at, old_updated_at)

    def test_slug_mixin_generation(self):
        # Act
        obj = DummyModel.objects.create(name="My Super Test Name")

        # Assert
        self.assertTrue(obj.slug.startswith("my-super-test-name"))
        self.assertIn("#", obj.slug)

    def test_slug_mixin_unique_generation(self):
        # Arrange
        obj1 = DummyModel.objects.create(name="Unique Name")

        # Act
        obj2 = DummyModel.objects.create(name="Unique Name")

        # Assert
        self.assertTrue(obj1.slug.startswith("unique-name"))
        self.assertTrue(obj2.slug.startswith("unique-name"))
        self.assertNotEqual(obj1.slug, obj2.slug)

    def test_slug_mixin_does_not_override_existing(self):
        # Arrange
        obj = DummyModel(name="Test", slug="custom-slug")

        # Act
        obj.save()

        # Assert
        self.assertEqual(obj.slug, "custom-slug")
