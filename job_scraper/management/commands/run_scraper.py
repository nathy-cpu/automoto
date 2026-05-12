import logging
import time

from django.conf import settings
from django.core.management.base import BaseCommand

from job_scraper.apollo_client import ApolloClient
from job_scraper.request_scraper import JobScraper

logger = logging.getLogger(__name__)


def execute_scrape_run(
    *, keywords: str, location: str, limit: int = None, max_pages: int = None, website_ids=None
):
    started_at = time.monotonic()
    scraper = JobScraper()
    all_new_jobs = []
    website_ids = website_ids or [None]
    limit = settings.DEFAULT_ENRICHMENT_LIMIT if limit is None else limit
    max_pages = settings.DEFAULT_SCRAPE_MAX_PAGES if max_pages is None else max_pages

    logger.info(
        "run_scraper_start keywords=%s location=%s limit=%s max_pages=%s website_ids=%s",
        keywords,
        location,
        limit,
        max_pages,
        website_ids,
    )

    for website_id in website_ids:
        all_new_jobs.extend(
            scraper.get_recent_jobs(
                location,
                keywords,
                max_pages=max_pages,
                website_id=website_id,
            )
        )

    apollo = ApolloClient()
    enriched_count = 0
    for job in all_new_jobs[:limit]:
        try:
            enriched_count += apollo.enrich_job_contacts(job)
        except Exception:
            logger.exception(
                "apollo_enrichment_failed job_id=%s company=%s", job.id, job.company
            )

    logger.info(
        "run_scraper_done jobs_new=%s contacts_found=%s duration_ms=%s",
        len(all_new_jobs),
        enriched_count,
        int((time.monotonic() - started_at) * 1000),
    )
    return all_new_jobs, enriched_count


class Command(BaseCommand):
    help = "Runs the Indeed scraper and enriches found leads with Apollo data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--keywords", type=str, default=settings.DEFAULT_SCRAPE_KEYWORDS
        )
        parser.add_argument(
            "--location", type=str, default=settings.DEFAULT_SCRAPE_LOCATION
        )
        parser.add_argument(
            "--limit", type=int, default=settings.DEFAULT_ENRICHMENT_LIMIT
        )
        parser.add_argument(
            "--max-pages", type=int, default=settings.DEFAULT_SCRAPE_MAX_PAGES
        )
        parser.add_argument("--website-id", action="append", type=int, default=[])

    def handle(self, *args, **options):
        keywords = options["keywords"]
        location = options["location"]
        limit = options["limit"]
        max_pages = options["max_pages"]
        website_ids = options["website_id"]

        self.stdout.write(
            self.style.SUCCESS(f"Starting scraper for '{keywords}' in '{location}'...")
        )

        new_jobs, enriched_count = execute_scrape_run(
            keywords=keywords,
            location=location,
            limit=limit,
            max_pages=max_pages,
            website_ids=website_ids,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Found {len(new_jobs)} new jobs. Starting enrichment..."
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Run complete. {len(new_jobs)} jobs processed, {enriched_count} contacts found."
            )
        )
