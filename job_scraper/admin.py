from django.contrib import admin
from django.contrib import messages

from .management.commands.run_scheduler import run_scheduled_scrape
from .models import Contact, CustomWebsite, Job, ScheduledScrape, ScraperExecutionLog


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


@admin.register(ScheduledScrape)
class ScheduledScrapeAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "cron_expression",
        "timezone",
        "location_summary",
        "max_pages",
        "is_active",
        "updated_at",
    )
    list_filter = ("is_active", "timezone")
    search_fields = (
        "name",
        "keywords",
        "countries",
        "continents",
        "location",
        "cron_expression",
    )
    filter_horizontal = ("websites",)
    readonly_fields = ("created_at", "updated_at")
    actions = ("run_selected_schedules_now",)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "name",
                    "is_active",
                    "websites",
                    "keywords",
                    "countries",
                    "continents",
                    "location",
                )
            },
        ),
        (
            "Timing",
            {
                "fields": ("cron_expression", "timezone"),
                "description": "Use a standard 5-field cron expression such as '*/30 * * * *' for every 30 minutes.",
            },
        ),
        (
            "Run Behavior",
            {
                "fields": ("max_pages", "enrichment_limit"),
            },
        ),
        (
            "Metadata",
            {
                "fields": ("created_at", "updated_at"),
            },
        ),
    )

    @admin.action(description="Run selected schedules now")
    def run_selected_schedules_now(self, request, queryset):
        run_count = 0
        for schedule in queryset:
            run_scheduled_scrape(schedule.id)
            run_count += 1
        self.message_user(
            request,
            f"Triggered {run_count} scheduled scrape(s). Scheduler restart is still required for cron changes.",
            level=messages.SUCCESS,
        )

    def location_summary(self, obj):
        return obj.countries or obj.continents or obj.location

    location_summary.short_description = "Search Region"
