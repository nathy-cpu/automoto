import logging

from django.conf import settings
from django.core.management.base import BaseCommand

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from django_apscheduler import util
from django_apscheduler.jobstores import DjangoJobStore
from django_apscheduler.models import DjangoJobExecution

from job_scraper.management.commands.run_scraper import execute_scrape_run
from job_scraper.models import ScheduledScrape
from job_scraper.utils import resolve_scrape_location

logger = logging.getLogger(__name__)


def run_scheduled_scrape(schedule_id):
    try:
        schedule = ScheduledScrape.objects.prefetch_related("websites").get(
            id=schedule_id, is_active=True
        )
        website_ids = list(schedule.websites.values_list("id", flat=True))
        logger.info(
            "scheduled_scrape_start schedule_id=%s name=%s websites=%s cron=%s",
            schedule.id,
            schedule.name,
            website_ids,
            schedule.cron_expression,
        )
        location = resolve_scrape_location(
            countries=schedule.countries,
            continents=schedule.continents,
            fallback_location=schedule.location,
        )
        execute_scrape_run(
            keywords=schedule.keywords,
            location=location,
            limit=schedule.enrichment_limit,
            max_pages=schedule.max_pages,
            website_ids=website_ids,
        )
    except Exception:
        logger.exception("scheduled_scraper_task_failed schedule_id=%s", schedule_id)


def register_scheduled_scrapes(scheduler):
    for schedule in ScheduledScrape.objects.filter(is_active=True).prefetch_related(
        "websites"
    ):
        if not schedule.websites.exists():
            logger.warning(
                "scheduled_scrape_skipped_no_websites schedule_id=%s name=%s",
                schedule.id,
                schedule.name,
            )
            continue

        scheduler.add_job(
            run_scheduled_scrape,
            trigger=CronTrigger.from_crontab(
                schedule.cron_expression, timezone=schedule.timezone
            ),
            args=[schedule.id],
            id=f"scheduled_scrape_{schedule.id}",
            max_instances=1,
            replace_existing=True,
        )
        logger.info(
            "scheduled_scrape_registered schedule_id=%s name=%s cron=%s timezone=%s",
            schedule.id,
            schedule.name,
            schedule.cron_expression,
            schedule.timezone,
        )


@util.close_old_connections
def delete_old_job_executions(max_age=604_800):
    DjangoJobExecution.objects.delete_old_job_executions(max_age)


class Command(BaseCommand):
    help = "Starts the APScheduler to run scrapers autonomously."

    def handle(self, *args, **options):
        scheduler = BlockingScheduler(timezone=settings.TIME_ZONE)
        scheduler.add_jobstore(DjangoJobStore(), "default")
        register_scheduled_scrapes(scheduler)

        scheduler.add_job(
            delete_old_job_executions,
            trigger=CronTrigger(day_of_week="mon", hour="00", minute="00"),
            id="delete_old_job_executions",
            max_instances=1,
            replace_existing=True,
        )

        try:
            logger.info("Starting scheduler...")
            scheduler.start()
        except KeyboardInterrupt:
            logger.info("Stopping scheduler...")
            scheduler.shutdown()
            logger.info("Scheduler shut down successfully!")
