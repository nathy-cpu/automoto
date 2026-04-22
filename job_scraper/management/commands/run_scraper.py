import logging

from django.core.management.base import BaseCommand

from job_scraper.apollo_client import ApolloClient

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Runs the Indeed scraper and enriches found leads with Apollo data."

    def add_arguments(self, parser):
        parser.add_argument("--keywords", type=str, default="software contract")
        parser.add_argument("--location", type=str, default="us")
        parser.add_argument("--limit", type=int, default=10)

    def handle(self, *args, **options):
        keywords = options["keywords"]
        location = options["location"]
        limit = options["limit"]

        self.stdout.write(
            self.style.SUCCESS(f"Starting scraper for '{keywords}' in '{location}'...")
        )

        from job_scraper.request_scraper import JobScraper
        scraper = JobScraper()
        new_jobs = scraper.get_recent_jobs(location, keywords, max_pages=1)

        self.stdout.write(
            self.style.SUCCESS(
                f"Found {len(new_jobs)} new jobs. Starting enrichment..."
            )
        )

        apollo = ApolloClient()
        enriched_count = 0

        # Enrich only a subset to save credits/time if needed
        for job in new_jobs[:limit]:
            try:
                count = apollo.enrich_job_contacts(job)
                enriched_count += count
                self.stdout.write(f"Enriched {job.company} with {count} contacts.")
            except Exception as e:
                self.stderr.write(
                    self.style.ERROR(f"Failed to enrich {job.company}: {e}")
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Run complete. {len(new_jobs)} jobs processed, {enriched_count} contacts found."
            )
        )
