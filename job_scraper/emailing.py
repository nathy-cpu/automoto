from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone

from .models import Job, ScheduledScrape, ScheduledScrapeRun


def send_scheduled_scrape_summary(
    schedule: ScheduledScrape,
    run: ScheduledScrapeRun,
    new_jobs: list[Job],
    site_domain: str = "localhost:8000",
) -> int:
    recipients = [
        user.email.strip()
        for user in schedule.subscribers.all()
        if getattr(user, "email", "").strip()
    ]
    if not recipients:
        return 0

    subject = f"[{getattr(settings, 'EMAIL_SUBJECT_PREFIX', 'AutoMoto')}] {schedule.name} summary"
    body = build_scheduled_scrape_summary(
        schedule, run, new_jobs, site_domain=site_domain
    )
    delivered = send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipients,
        fail_silently=False,
    )
    return len(recipients) if delivered else 0


def build_scheduled_scrape_summary(
    schedule: ScheduledScrape,
    run: ScheduledScrapeRun,
    new_jobs: list[Job],
    site_domain: str = "localhost:8000",
) -> str:
    top_jobs = list(new_jobs[:10])
    location_summary = schedule.countries or schedule.continents or schedule.location
    lines = [
        f"Scheduled scrape: {schedule.name}",
        f"Run time: {timezone.localtime(run.started_at).strftime('%Y-%m-%d %H:%M %Z')}",
        f"Keywords: {schedule.keywords or '(none)'}",
        f"Search region: {location_summary or 'us'}",
        f"New jobs found: {run.jobs_new}",
        "",
        "Top new leads:",
    ]

    if not top_jobs:
        lines.append("- No new jobs found in this run.")
    else:
        for job in top_jobs:
            detail_path = reverse("job_detail", args=[job.id])
            lines.extend(
                [
                    f"- {job.title} at {job.company}",
                    f"  Location: {job.location}",
                    f"  Source: {job.source_website}",
                    f"  Details: http://{site_domain}{detail_path}",
                ]
            )

    if run.jobs_new > len(top_jobs):
        lines.extend(
            ["", f"Additional new jobs not listed: {run.jobs_new - len(top_jobs)}"]
        )

    lines.extend(["", f"Dashboard: http://{site_domain}{reverse('dashboard')}"])
    return "\n".join(lines)
