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
                "job_list_selector": "[data-jk]",
                "title_selector": "h2.jobTitle span[title]",
                "company_selector": '[data-testid="company-name"]',
                "location_selector": '[data-testid="text-location"]',
                "job_link_selector": "h2.jobTitle a",
                "description_selector": "#jobDescriptionText",
                "use_stealth": True,
            },
            {
                "name": "LinkedIn",
                "base_url": "https://www.linkedin.com",
                "search_url": "https://www.linkedin.com/jobs/search?keywords={keywords}&location={location}&f_TPR=r86400",
                "job_list_selector": ".base-card",
                "title_selector": ".base-search-card__title",
                "company_selector": ".base-search-card__subtitle",
                "location_selector": ".job-search-card__location",
                "job_link_selector": ".base-card__full-link",
                "description_selector": ".show-more-less-html",
                "use_stealth": False,  # LinkedIn sometimes works with requests if not too frequent
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
