from django.core.management import call_command
from django.core.management.base import BaseCommand

from job_scraper.models import CustomWebsite, ScheduledScrape


SCHEDULE_DEFINITIONS = [
    {
        "name": "US RFP Leads",
        "keywords": "IT services RFP, software development proposal, digital transformation consulting, system integration services, technology vendor selection",
        "location": "us",
        "countries": "us",
        "cron_expression": "0 */2 * * *",
        "timezone": "UTC",
        "max_pages": 2,
        "enrichment_limit": 10,
        "website_names": ["Indeed", "LinkedIn", "We Work Remotely", "Arbeitnow (API)", "Remotive (API)", "TED EU Tenders", "UK Contracts Finder"],
    },
    {
        "name": "EU Procurement Opportunities",
        "keywords": "IT consulting, software development tender, digital transformation procurement, technology services framework",
        "location": "europe",
        "continents": "Europe",
        "cron_expression": "0 */2 * * *",
        "timezone": "UTC",
        "max_pages": 2,
        "enrichment_limit": 10,
        "website_names": ["TED EU Tenders", "UK Contracts Finder", "LinkedIn", "Arbeitnow (API)"],
    },
    {
        "name": "UK Government Contracts",
        "keywords": "software development, digital services, technology consulting, systems integration, IT procurement",
        "location": "uk",
        "countries": "uk",
        "cron_expression": "0 */2 * * *",
        "timezone": "UTC",
        "max_pages": 2,
        "enrichment_limit": 10,
        "website_names": ["UK Contracts Finder", "TED EU Tenders", "LinkedIn", "Indeed"],
    },
]


class Command(BaseCommand):
    help = "Seed the database with pre-configured scheduled scrapes for RFP/consulting lead generation"

    def handle(self, *args, **options):
        call_command("seed_websites")

        created_count = 0
        updated_count = 0

        website_lookup = {
            ws.name: ws for ws in CustomWebsite.objects.filter(is_active=True)
        }

        for schedule_data in SCHEDULE_DEFINITIONS:
            website_names = schedule_data.pop("website_names")
            websites = [
                website_lookup[name]
                for name in website_names
                if name in website_lookup
            ]

            schedule, created = ScheduledScrape.objects.update_or_create(
                name=schedule_data["name"],
                defaults=schedule_data,
            )
            schedule.websites.set(websites)

            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created scheduled scrape: '{schedule.name}' "
                        f"(cron={schedule.cron_expression}, websites={len(websites)})"
                    )
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Updated scheduled scrape: '{schedule.name}' "
                        f"(cron={schedule.cron_expression}, websites={len(websites)})"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {created_count} created, {updated_count} updated."
            )
        )
