from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("job_scraper", "0012_scheduledscrape_regions"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="scheduledscrape",
            name="subscribers",
            field=models.ManyToManyField(
                blank=True,
                related_name="scheduled_scrape_subscriptions",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.CreateModel(
            name="ScheduledScrapeRun",
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
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("jobs_new", models.PositiveIntegerField(default=0)),
                ("contacts_found", models.PositiveIntegerField(default=0)),
                ("emails_sent", models.PositiveIntegerField(default=0)),
                ("email_error", models.TextField(blank=True)),
                (
                    "schedule",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="runs",
                        to="job_scraper.scheduledscrape",
                    ),
                ),
            ],
            options={"ordering": ["-started_at"]},
        ),
    ]
