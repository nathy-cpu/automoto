from django.core.management.base import BaseCommand

from job_scraper.models import CustomWebsite


class Command(BaseCommand):
    help = "Seed the database with initial custom website configurations"

    def handle(self, *args, **kwargs):
        websites = [
            {
                "name": "Indeed",
                "base_url": "https://www.indeed.com",
                "search_url": "https://www.indeed.com/jobs?q={keywords}&l={location}&fromage=1",
                "job_list_selector": ".job_seen_beacon",
                "title_selector": 'h2.jobTitle span[id^="jobTitle-"]',
                "company_selector": '[data-testid="company-name"]',
                "location_selector": '[data-testid="text-location"]',
                "salary_selector": '[data-testid="attribute_snippet_salary"], .salary-snippet-container, .salary-snippet, .salaryOnly',
                "date_selector": '[data-testid="timing-attribute"]',
                "job_link_selector": "h2.jobTitle a",
                "description_selector": "#jobDescriptionText",
                "use_stealth": True,
            },
            {
                "name": "LinkedIn",
                "base_url": "https://www.linkedin.com",
                "search_url": "https://www.linkedin.com/jobs/search?keywords={keywords}&location={location}&f_TPR=r86400",
                "job_list_selector": ".base-search-card",
                "title_selector": ".base-search-card__title",
                "company_selector": ".base-search-card__subtitle",
                "location_selector": ".job-search-card__location",
                "salary_selector": ".job-search-card__salary-info",
                "date_selector": ".job-search-card__listdate, .job-search-card__listdate--new",
                "job_link_selector": ".base-card__full-link",
                "description_selector": ".show-more-less-html__markup, .description__text",
                "use_stealth": False,  # LinkedIn sometimes works with requests if not too frequent
            },
            {
                "name": "Arbeitnow (API)",
                "base_url": "https://www.arbeitnow.com",
                "search_url": "https://www.arbeitnow.com/api/job-board-api?search={keywords}",
                "job_list_selector": "N/A",
                "title_selector": "N/A",
                "company_selector": "N/A",
                "location_selector": "N/A",
                "job_link_selector": "N/A",
                "is_api": True,
                "api_jobs_path": "data",
                "api_title_key": "title",
                "api_company_key": "company_name",
                "api_location_key": "location",
                "api_description_key": "description",
                "api_url_key": "url",
            },
        ]

        for ws_data in websites:
            obj, created = CustomWebsite.objects.update_or_create(
                name=ws_data["name"], defaults=ws_data
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f"Successfully created {ws_data['name']}")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f"Successfully updated {ws_data['name']}")
                )
