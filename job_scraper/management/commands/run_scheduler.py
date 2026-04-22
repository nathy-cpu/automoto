import logging

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from django_apscheduler import util
from django_apscheduler.jobstores import DjangoJobStore
from django_apscheduler.models import DjangoJobExecution

logger = logging.getLogger(__name__)


def run_scraper_task():
    logger.info("Running scheduled scraper task...")
    try:
        # Default run with some common keywords
        call_command(
            "run_scraper", keywords="software contract", location="us", limit=20
        )
        call_command("run_scraper", keywords="it rfp", location="uk", limit=20)
    except Exception:
        logger.exception("scheduled_scraper_task_failed")


@util.close_old_connections
def delete_old_job_executions(max_age=604_800):
    DjangoJobExecution.objects.delete_old_job_executions(max_age)


class Command(BaseCommand):
    help = "Starts the APScheduler to run scrapers autonomously."

    def handle(self, *args, **options):
        scheduler = BlockingScheduler(timezone=settings.TIME_ZONE)
        scheduler.add_jobstore(DjangoJobStore(), "default")

        # Run twice daily: at 08:00 and 20:00
        scheduler.add_job(
            run_scraper_task,
            trigger=CronTrigger(hour="8,20", minute="0"),
            id="run_scraper_task",
            max_instances=1,
            replace_existing=True,
        )
        logger.info("Added twice-daily job: run_scraper_task.")

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
