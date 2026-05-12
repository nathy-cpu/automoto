import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("job_scraper", "0010_alter_customwebsite_use_stealth_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="ScheduledScrape",
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
                ("name", models.CharField(max_length=120, unique=True)),
                ("keywords", models.CharField(blank=True, max_length=255)),
                ("location", models.CharField(default="us", max_length=100)),
                (
                    "cron_expression",
                    models.CharField(
                        help_text="Standard 5-field cron expression, e.g. '*/30 * * * *'",
                        max_length=100,
                    ),
                ),
                ("timezone", models.CharField(default="UTC", max_length=64)),
                ("max_pages", models.PositiveSmallIntegerField(default=1)),
                ("enrichment_limit", models.PositiveSmallIntegerField(default=10)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "websites",
                    models.ManyToManyField(
                        related_name="scheduled_scrapes", to="job_scraper.customwebsite"
                    ),
                ),
            ],
            options={"ordering": ["name"]},
        ),
    ]
