from zoneinfo import available_timezones

from django.conf import settings
from django.db import models

from apscheduler.triggers.cron import CronTrigger

# Create your models here.


class Job(models.Model):
    title = models.CharField(max_length=200)
    company = models.CharField(max_length=200)
    industry = models.CharField(max_length=100, blank=True)
    location = models.CharField(max_length=200)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    description = models.TextField()
    requirements = models.TextField(blank=True)
    salary = models.CharField(max_length=100, blank=True)
    job_type = models.CharField(
        max_length=50, blank=True
    )  # Full-time, Part-time, Contract, etc.
    experience_level = models.CharField(max_length=50, blank=True)
    deadline = models.DateField(null=True, blank=True)
    posted_date = models.DateField(null=True, blank=True)
    application_instructions = models.TextField(blank=True)
    application_link = models.URLField(blank=True)
    source_website = models.CharField(
        max_length=100
    )  # indeed, linkedin, custom website, etc.
    source_url = models.URLField(blank=True)
    continent = models.CharField(max_length=100, blank=True)
    expertise_tags = models.TextField(
        blank=True, help_text="Comma-separated expertise/skills"
    )
    needs_summary = models.TextField(
        blank=True, help_text="AI-generated summary of client needs"
    )
    is_rfp = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} at {self.company}"


class CustomWebsite(models.Model):
    """Model to store custom websites added by users"""

    name = models.CharField(max_length=100)
    base_url = models.URLField()
    search_url = models.URLField()
    job_list_selector = models.CharField(
        max_length=200
    )  # CSS selector for job listings
    title_selector = models.CharField(max_length=200)  # CSS selector for job title
    company_selector = models.CharField(max_length=200)  # CSS selector for company name
    location_selector = models.CharField(max_length=200)  # CSS selector for location
    salary_selector = models.CharField(
        max_length=200, blank=True
    )  # CSS selector for salary
    date_selector = models.CharField(
        max_length=200, blank=True
    )  # CSS selector for posted date
    job_link_selector = models.CharField(
        max_length=200
    )  # CSS selector for job detail link
    apply_link_selector = models.CharField(
        max_length=200, blank=True
    )  # CSS selector for apply link
    description_selector = models.CharField(
        max_length=200, blank=True
    )  # CSS selector for job description
    requirements_selector = models.CharField(
        max_length=200, blank=True
    )  # CSS selector for requirements
    use_stealth = models.BooleanField(
        default=False,
        help_text="Use high-protection stealth browser (SeleniumBase UC mode) for this site",
    )
    # API Support
    is_api = models.BooleanField(
        default=False, help_text="Set to true if this is a JSON API endpoint"
    )
    api_jobs_path = models.CharField(
        max_length=255,
        blank=True,
        help_text="Key path to the list of jobs (e.g. 'data')",
    )
    api_title_key = models.CharField(
        max_length=100, blank=True, help_text="JSON key for job title"
    )
    api_company_key = models.CharField(
        max_length=100, blank=True, help_text="JSON key for company"
    )
    api_location_key = models.CharField(
        max_length=100, blank=True, help_text="JSON key for location"
    )
    api_description_key = models.CharField(
        max_length=100, blank=True, help_text="JSON key for description"
    )
    api_url_key = models.CharField(
        max_length=100, blank=True, help_text="JSON key for job URL"
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Contact(models.Model):
    """Model to store enriched contact information for leads"""

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="contacts")
    name = models.CharField(max_length=200)
    title = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True)
    linkedin_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["job", "name"], name="unique_job_contact_name"
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.title}) at {self.job.company}"


class ScraperExecutionLog(models.Model):
    """Logs the execution of the scraper, including success, errors, and debug artifacts"""

    SCRAPER_CHOICES = [
        ("requests", "Standard (Requests)"),
        ("seleniumbase", "Stealth (SeleniumBase)"),
        ("api", "JSON API"),
    ]

    website = models.ForeignKey(
        CustomWebsite, on_delete=models.CASCADE, related_name="execution_logs"
    )
    scraper_type = models.CharField(
        max_length=20, choices=SCRAPER_CHOICES, default="requests"
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    jobs_found = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)

    # Debug telemetry
    screenshot = models.FileField(
        upload_to="artifacts/screenshots/", blank=True, null=True
    )
    html_dump = models.FileField(
        upload_to="artifacts/html_dumps/", blank=True, null=True
    )

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        status = "Error" if self.error_message else "Success"
        return f"{self.website.name} - {self.timestamp.strftime('%Y-%m-%d %H:%M')} [{status}]"


class ScheduledScrape(models.Model):
    name = models.CharField(max_length=120, unique=True)
    websites = models.ManyToManyField(CustomWebsite, related_name="scheduled_scrapes")
    subscribers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="scheduled_scrape_subscriptions",
    )
    keywords = models.CharField(max_length=255, blank=True)
    countries = models.CharField(
        max_length=255,
        blank=True,
        help_text="Comma-separated countries, same as manual scrape input.",
    )
    continents = models.CharField(
        max_length=255,
        blank=True,
        help_text="Comma-separated continents, same as manual scrape input.",
    )
    location = models.CharField(
        max_length=100,
        default="us",
        help_text="Fallback location if countries and continents are blank.",
    )
    cron_expression = models.CharField(
        max_length=100,
        help_text="Standard 5-field cron expression, e.g. '*/30 * * * *'",
    )
    timezone = models.CharField(max_length=64, default="UTC")
    max_pages = models.PositiveSmallIntegerField(default=1)
    enrichment_limit = models.PositiveSmallIntegerField(default=10)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.timezone not in available_timezones():
            from django.core.exceptions import ValidationError

            raise ValidationError({"timezone": "Enter a valid IANA timezone."})

        try:
            CronTrigger.from_crontab(self.cron_expression, timezone=self.timezone)
        except ValueError as exc:
            from django.core.exceptions import ValidationError

            raise ValidationError(
                {"cron_expression": f"Invalid cron expression: {exc}"}
            )


class ScheduledScrapeRun(models.Model):
    schedule = models.ForeignKey(
        ScheduledScrape, on_delete=models.CASCADE, related_name="runs"
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    jobs_new = models.PositiveIntegerField(default=0)
    contacts_found = models.PositiveIntegerField(default=0)
    emails_sent = models.PositiveIntegerField(default=0)
    email_error = models.TextField(blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.schedule.name} @ {self.started_at:%Y-%m-%d %H:%M}"
