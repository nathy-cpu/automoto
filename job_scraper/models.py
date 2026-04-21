from django.db import models

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
        help_text="Use high-protection stealth browser (Playwright) for this site",
    )
    # API Support
    is_api = models.BooleanField(default=False, help_text="Set to true if this is a JSON API endpoint")
    api_jobs_path = models.CharField(max_length=255, blank=True, help_text="Key path to the list of jobs (e.g. 'data')")
    api_title_key = models.CharField(max_length=100, blank=True, help_text="JSON key for job title")
    api_company_key = models.CharField(max_length=100, blank=True, help_text="JSON key for company")
    api_location_key = models.CharField(max_length=100, blank=True, help_text="JSON key for location")
    api_description_key = models.CharField(max_length=100, blank=True, help_text="JSON key for description")
    api_url_key = models.CharField(max_length=100, blank=True, help_text="JSON key for job URL")

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

    def __str__(self):
        return f"{self.name} ({self.title}) at {self.job.company}"


class ScraperExecutionLog(models.Model):
    """Logs the execution of the scraper, including success, errors, and debug artifacts"""
    
    SCRAPER_CHOICES = [
        ('requests', 'Standard (Requests)'),
        ('playwright', 'Stealth (Playwright)'),
        ('api', 'JSON API'),
    ]
    
    website = models.ForeignKey(CustomWebsite, on_delete=models.CASCADE, related_name="execution_logs")
    scraper_type = models.CharField(max_length=20, choices=SCRAPER_CHOICES, default='requests')
    timestamp = models.DateTimeField(auto_now_add=True)
    jobs_found = models.IntegerField(default=0)
    error_message = models.TextField(blank=True)
    
    # Debug telemetry
    screenshot = models.FileField(upload_to="artifacts/screenshots/", blank=True, null=True)
    html_dump = models.FileField(upload_to="artifacts/html_dumps/", blank=True, null=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        status = "Error" if self.error_message else "Success"
        return f"{self.website.name} - {self.timestamp.strftime('%Y-%m-%d %H:%M')} [{status}]"
