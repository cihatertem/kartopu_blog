from django.contrib.postgres.search import SearchVectorField
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("blog", "0033_alter_blogpost_content")]

    operations = [
        migrations.AddField(
            model_name="blogpost",
            name="search_vector_exact",
            field=SearchVectorField(blank=True, null=True),
        ),
    ]