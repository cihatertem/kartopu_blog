import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("blog", "0020_alter_blogpost_content"),
    ]

    operations = [
        migrations.CreateModel(
            name="Announcement",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        help_text="A unique identifier for the record.",
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("subject", models.CharField(max_length=200)),
                ("body", models.TextField()),
                (
                    "status",
                    models.CharField(
                        choices=[("draft", "Taslak"), ("sent", "Gönderildi")],
                        default="draft",
                        max_length=20,
                    ),
                ),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "verbose_name": "Özel Duyuru",
                "verbose_name_plural": "Özel Duyurular",
            },
        ),
        migrations.CreateModel(
            name="Subscriber",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        help_text="A unique identifier for the record.",
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("email", models.EmailField(max_length=254, unique=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Onay Bekliyor"),
                            ("active", "Aktif"),
                            ("unsubscribed", "İptal Edildi"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("subscribed_at", models.DateTimeField(blank=True, null=True)),
                ("confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("unsubscribed_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "verbose_name": "Newsletter Abonesi",
                "verbose_name_plural": "Newsletter Aboneleri",
                "ordering": ("-created_at",),
            },
        ),
        migrations.CreateModel(
            name="BlogPostNotification",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        help_text="A unique identifier for the record.",
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("sent_at", models.DateTimeField()),
                (
                    "post",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="newsletter_notification",
                        to="blog.blogpost",
                    ),
                ),
            ],
            options={
                "verbose_name": "Yazı Bildirimi",
                "verbose_name_plural": "Yazı Bildirimleri",
            },
        ),
    ]
