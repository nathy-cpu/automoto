from django.contrib import admin

from .models import Contact, CustomWebsite, Job, ScraperExecutionLog


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "company",
        "location",
        "source_website",
        "is_rfp",
        "created_at",
    )
    list_filter = ("source_website", "is_rfp", "continent")
    search_fields = ("title", "company", "location", "description")
    readonly_fields = ("created_at", "updated_at")


@admin.register(CustomWebsite)
class CustomWebsiteAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "base_url",
        "is_api",
        "use_stealth",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active", "is_api", "use_stealth")
    search_fields = ("name", "base_url")
    fieldsets = (
        (None, {"fields": ("name", "base_url", "search_url", "is_active")}),
        (
            "CSS Selector Mode",
            {
                "fields": (
                    "use_stealth",
                    "job_list_selector",
                    "title_selector",
                    "company_selector",
                    "location_selector",
                    "salary_selector",
                    "date_selector",
                    "job_link_selector",
                    "apply_link_selector",
                    "description_selector",
                    "requirements_selector",
                ),
                "classes": ("collapse",),
                "description": "Configure these if using standard web scraping",
            },
        ),
        (
            "JSON API Mode",
            {
                "fields": (
                    "is_api",
                    "api_jobs_path",
                    "api_title_key",
                    "api_company_key",
                    "api_location_key",
                    "api_description_key",
                    "api_url_key",
                ),
                "description": "Configure these if the search URL returns JSON",
            },
        ),
        (
            "Metadata",
            {
                "fields": ("created_at",),
            },
        ),
    )
    readonly_fields = ("created_at",)


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("name", "title", "company_name", "email", "created_at")
    search_fields = ("name", "title", "email", "job__company")

    def company_name(self, obj):
        return obj.job.company

    company_name.short_description = "Company"


@admin.register(ScraperExecutionLog)
class ScraperExecutionLogAdmin(admin.ModelAdmin):
    list_display = ("website", "scraper_type", "timestamp", "jobs_found", "has_error")
    list_filter = ("website", "scraper_type", "timestamp")
    readonly_fields = (
        "website",
        "scraper_type",
        "timestamp",
        "jobs_found",
        "error_message",
        "screenshot",
        "html_dump",
    )

    def has_error(self, obj):
        return bool(obj.error_message)

    has_error.boolean = True
    has_error.short_description = "Error"
