from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("blog", "0020_alter_blogpost_content"),
    ]

    operations = [
        migrations.CreateModel(
            name="BlogPostReaction",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "reaction",
                    models.CharField(
                        choices=[
                            ("alkis", "Alkış"),
                            ("ilham", "İlham"),
                            ("merak", "Merak"),
                            ("kalp", "Sevgi"),
                            ("roket", "Gaz"),
                            ("surpriz", "Şaşkın"),
                            ("mutlu", "Mutlu"),
                            ("duygulandim", "Duygulandım"),
                            ("dusunceli", "Düşünceli"),
                            ("huzunlu", "Hüzünlü"),
                            ("rahatsiz", "Rahatsız"),
                            ("korku", "Endişe"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "post",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reactions",
                        to="blog.blogpost",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="blog_post_reactions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Blog Tepkisi",
                "verbose_name_plural": "Blog Tepkileri",
            },
        ),
        migrations.AddConstraint(
            model_name="blogpostreaction",
            constraint=models.UniqueConstraint(
                fields=("post", "user"), name="unique_blog_post_reaction"
            ),
        ),
        migrations.AddIndex(
            model_name="blogpostreaction",
            index=models.Index(fields=["post", "reaction"], name="blog_post_r_post_id_26e4b1_idx"),
        ),
    ]
