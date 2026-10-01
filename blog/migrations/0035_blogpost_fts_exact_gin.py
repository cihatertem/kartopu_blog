from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations


class Migration(migrations.Migration):
    atomic = False

    dependencies = [("blog", "0034_blogpost_search_vector_exact")]

    operations = [
        AddIndexConcurrently(
            model_name="blogpost",
            index=GinIndex(fields=["search_vector_exact"], name="blogpost_fts_exact_gin"),
        ),
    ]