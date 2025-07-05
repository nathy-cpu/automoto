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
    job_type = models.CharField(max_length=50, blank=True)  # Full-time, Part-time, Contract, etc.
    experience_level = models.CharField(max_length=50, blank=True)
    deadline = models.DateField(null=True, blank=True)
    posted_date = models.DateField(null=True, blank=True)
    application_instructions = models.TextField(blank=True)
    application_link = models.URLField(blank=True)
    source_website = models.CharField(max_length=100)  # indeed, linkedin, glassdoor, etc.
    source_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} at {self.company}"


class CustomWebsite(models.Model):
    """Model to store custom websites added by users"""
    name = models.CharField(max_length=100)
    base_url = models.URLField()
    search_url = models.URLField()
    job_list_selector = models.CharField(max_length=200)  # CSS selector for job listings
    title_selector = models.CharField(max_length=200)  # CSS selector for job title
    company_selector = models.CharField(max_length=200)  # CSS selector for company name
    location_selector = models.CharField(max_length=200)  # CSS selector for location
    salary_selector = models.CharField(max_length=200, blank=True)  # CSS selector for salary
    date_selector = models.CharField(max_length=200, blank=True)  # CSS selector for posted date
    job_link_selector = models.CharField(max_length=200)  # CSS selector for job detail link
    apply_link_selector = models.CharField(max_length=200, blank=True)  # CSS selector for apply link
    description_selector = models.CharField(max_length=200, blank=True)  # CSS selector for job description
    requirements_selector = models.CharField(max_length=200, blank=True)  # CSS selector for requirements
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name
