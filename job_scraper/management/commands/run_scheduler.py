import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from django_apscheduler import util
from django_apscheduler.jobstores import DjangoJobStore
from django_apscheduler.models import DjangoJobExecution

from job_scraper.emailing import send_scheduled_scrape_summary
from job_scraper.management.commands.run_scraper import execute_scrape_run
from job_scraper.models import ScheduledScrape, ScheduledScrapeRun
from job_scraper.utils import resolve_scrape_location

logger = logging.getLogger(__name__)


def run_scheduled_scrape(schedule_id):
    run = None
    try:
        schedule = ScheduledScrape.objects.prefetch_related("websites", "subscribers").get(
            id=schedule_id, is_active=True
        )
        run = ScheduledScrapeRun.objects.create(schedule=schedule)
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
        new_jobs, contacts_found = execute_scrape_run(
            keywords=schedule.keywords,
            location=location,
            limit=schedule.enrichment_limit,
            max_pages=schedule.max_pages,
            website_ids=website_ids,
        )
        run.jobs_new = len(new_jobs)
        run.contacts_found = contacts_found
        try:
            run.emails_sent = send_scheduled_scrape_summary(
                schedule,
                run,
                new_jobs,
                site_domain=settings.SITE_DOMAIN,
            )
        except Exception as exc:
            run.email_error = str(exc)
            logger.exception(
                "scheduled_scrape_email_failed schedule_id=%s run_id=%s",
                schedule.id,
                run.id,
            )

        run.completed_at = timezone.now()
        run.save(
            update_fields=[
                "jobs_new",
                "contacts_found",
                "emails_sent",
                "email_error",
                "completed_at",
            ]
        )
    except Exception:
        if run is not None:
            run.email_error = "Scheduled scrape run failed before email delivery completed."
            run.completed_at = timezone.now()
            run.save(update_fields=["email_error", "completed_at"])
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
def delete_old_job_executions(max_age=None):
    max_age = settings.SCHEDULER_CLEANUP_MAX_AGE_SECONDS if max_age is None else max_age
    DjangoJobExecution.objects.delete_old_job_executions(max_age)


class Command(BaseCommand):
    help = "Starts the APScheduler to run scrapers autonomously."

    def handle(self, *args, **options):
        scheduler = BlockingScheduler(timezone=settings.TIME_ZONE)
        scheduler.add_jobstore(DjangoJobStore(), "default")
        register_scheduled_scrapes(scheduler)

        scheduler.add_job(
            delete_old_job_executions,
            trigger=CronTrigger.from_crontab(settings.SCHEDULER_CLEANUP_CRON),
            kwargs={"max_age": settings.SCHEDULER_CLEANUP_MAX_AGE_SECONDS},
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
