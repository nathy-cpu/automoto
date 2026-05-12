from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("job_scraper", "0011_scheduledscrape"),
    ]

    operations = [
        migrations.AddField(
            model_name="scheduledscrape",
            name="continents",
            field=models.CharField(
                blank=True,
                help_text="Comma-separated continents, same as manual scrape input.",
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name="scheduledscrape",
            name="countries",
            field=models.CharField(
                blank=True,
                help_text="Comma-separated countries, same as manual scrape input.",
                max_length=255,
            ),
        ),
        migrations.AlterField(
            model_name="scheduledscrape",
            name="location",
            field=models.CharField(
                default="us",
                help_text="Fallback location if countries and continents are blank.",
                max_length=100,
            ),
        ),
    ]
