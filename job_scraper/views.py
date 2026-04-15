import logging

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpRequest
from django.shortcuts import get_object_or_404, redirect, render

from .scrapers import EnhancedJobScraper
from .models import CustomWebsite

logger = logging.getLogger(__name__)

DEFAULT_WEBSITES = ["indeed", "linkedin"]
RESULTS_PER_PAGE = 10


def _build_job_list(scraped_jobs: list[dict]) -> list[dict]:
    jobs_data = []
    for i, job in enumerate(scraped_jobs, start=1):
        jobs_data.append(
            {
                "id": i,
                "title": job.get("title", ""),
                "company": job.get("company", ""),
                "location": job.get("location", ""),
                "source_website": job.get("source_website", ""),
                "salary": job.get("salary", ""),
                "posted_date": job.get("posted_date", ""),
                "job_url": job.get("job_url", ""),
                "source_url": job.get("source_url", ""),
                "description": job.get("description", ""),
                "requirements": job.get("requirements", ""),
                "application_link": job.get("application_link", ""),
                "job_type": job.get("job_type", ""),
                "experience_level": job.get("experience_level", ""),
                "industry": job.get("industry", ""),
            }
        )
    return jobs_data


def _job_search_context(
    *,
    results=None,
    pagination=None,
    params=None,
    error=None,
) -> dict:
    context = {
        "custom_websites": CustomWebsite.objects.filter(is_active=True),
    }
    if results is not None:
        context["results"] = results
    if pagination is not None:
        context["pagination"] = pagination
    if params is not None:
        context["params"] = params
    if error:
        context["error"] = error
    return context


def job_search(request: HttpRequest):
    if request.method == "POST":
        keywords = request.POST.get("keywords", "")
        location = request.POST.get("location", "")
        websites = request.POST.getlist("websites") or DEFAULT_WEBSITES

        params = {
            "keywords": keywords,
            "location": location,
            "websites": websites,
        }

        try:
            country = str(location).strip() or "us"
            search_keywords = str(keywords).strip() or None
            enhanced_scraper = EnhancedJobScraper()
            scraped_jobs = enhanced_scraper.get_recent_jobs(
                websites, country, search_keywords, max_pages=15
            )
            jobs_data = _build_job_list(scraped_jobs)

            request.session["scraped_jobs"] = jobs_data
            request.session["search_params"] = params

            paginator = Paginator(jobs_data, RESULTS_PER_PAGE)
            page_number = request.GET.get("page", 1)
            page_obj = paginator.get_page(page_number)

            context = _job_search_context(
                results=page_obj, pagination=page_obj, params=params
            )
        except Exception as e:
            logger.error(f"Error during job scraping: {e}")
            context = _job_search_context(
                results=[],
                params=params,
                error="An error occurred while scraping jobs. Please try again.",
            )

        return render(request, "job_scraper/job_search.html", context)

    if request.method == "GET" and request.GET.get("page"):
        search_params = request.session.get("search_params", {})
        scraped_jobs = request.session.get("scraped_jobs", [])

        if scraped_jobs:
            paginator = Paginator(scraped_jobs, RESULTS_PER_PAGE)
            page_number = request.GET.get("page", 1)
            page_obj = paginator.get_page(page_number)
            context = _job_search_context(
                results=page_obj,
                pagination=page_obj,
                params=search_params,
            )
            return render(request, "job_scraper/job_search.html", context)

    return render(request, "job_scraper/job_search.html", _job_search_context())


def job_detail(request: HttpRequest, job_id: int):
    try:
        scraped_jobs = request.session.get("scraped_jobs", [])
        job_data = next(
            (job for job in scraped_jobs if str(job.get("id")) == str(job_id)),
            None,
        )

        if job_data is None:
            return render(
                request,
                "job_scraper/job_detail.html",
                {
                    "job": None,
                    "error": "Job details are unavailable. Please run a new search.",
                },
            )

        job_detail = {
            "id": job_data.get("id"),
            "title": job_data.get("title", "") or "Not available",
            "company": job_data.get("company", "") or "Not available",
            "industry": job_data.get("industry", "") or "Not available",
            "location": job_data.get("location", "") or "Not available",
            "description": job_data.get("description", "")
            or "Description unavailable.",
            "requirements": job_data.get("requirements", ""),
            "salary": job_data.get("salary", "") or "Not available",
            "job_type": job_data.get("job_type", "") or "Not available",
            "experience_level": job_data.get("experience_level", "") or "Not available",
            "posted_date": job_data.get("posted_date", "") or "Not available",
            "application_instructions": "Apply through the original job posting link.",
            "application_link": job_data.get(
                "application_link", job_data.get("job_url", "")
            ),
            "source_website": job_data.get("source_website", "") or "Unknown",
            "source_url": job_data.get("source_url", "") or "",
        }

        return render(request, "job_scraper/job_detail.html", {"job": job_detail})

    except Exception as e:
        logger.error(f"Error fetching job details: {e}")
        return render(
            request,
            "job_scraper/job_detail.html",
            {"job": None, "error": "Unable to load job details."},
        )


def manage_websites(request: HttpRequest):
    """View to manage custom websites"""
    if request.method == "POST":
        name = request.POST.get("name")
        base_url = request.POST.get("base_url")
        search_url = request.POST.get("search_url")
        job_list_selector = request.POST.get("job_list_selector")
        title_selector = request.POST.get("title_selector")
        company_selector = request.POST.get("company_selector")
        location_selector = request.POST.get("location_selector")
        job_link_selector = request.POST.get("job_link_selector")

        if all(
            [
                name,
                base_url,
                search_url,
                job_list_selector,
                title_selector,
                company_selector,
                location_selector,
                job_link_selector,
            ]
        ):
            CustomWebsite.objects.create(
                name=name,
                base_url=base_url,
                search_url=search_url,
                job_list_selector=job_list_selector,
                title_selector=title_selector,
                company_selector=company_selector,
                location_selector=location_selector,
                job_link_selector=job_link_selector,
                salary_selector=request.POST.get("salary_selector", ""),
                date_selector=request.POST.get("date_selector", ""),
                apply_link_selector=request.POST.get("apply_link_selector", ""),
                description_selector=request.POST.get("description_selector", ""),
                requirements_selector=request.POST.get("requirements_selector", ""),
            )
            messages.success(request, f'Website "{name}" added successfully!')
            return redirect("manage_websites")
        else:
            messages.error(request, "Please fill in all required fields.")

    custom_websites = CustomWebsite.objects.filter(is_active=True)
    return render(
        request,
        "job_scraper/manage_websites.html",
        {"custom_websites": custom_websites},
    )


def delete_website(request: HttpRequest, website_id: int):
    """Delete a custom website"""
    website = get_object_or_404(CustomWebsite, id=website_id)
    website.is_active = False
    website.save()
    messages.success(request, f'Website "{website.name}" deleted successfully!')
    return redirect("manage_websites")
