import logging

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpRequest
from django.shortcuts import get_object_or_404, redirect, render

from .models import Contact, CustomWebsite, Job
from .scrapers import JobScraper
from .stealth_scraper import StealthScraper
from .utils import get_continent_from_country

logger = logging.getLogger(__name__)

DEFAULT_WEBSITES = ["indeed", "linkedin"]
RESULTS_PER_PAGE = 10


def dashboard(request: HttpRequest):
    """
    Premium Dashboard view for sales teams to filter and manage leads.
    """
    queryset = Job.objects.all().prefetch_related("contacts")

    # Filtering
    def parse_filter(val):
        if not val:
            return []
        if isinstance(val, list):
            return val
        return [v.strip() for v in val.split(",") if v.strip()]

    continents = parse_filter(request.GET.get("continents"))
    countries = parse_filter(request.GET.get("countries"))
    industries = parse_filter(request.GET.get("industries"))
    expertise = request.GET.get("expertise")
    is_rfp = request.GET.get("is_rfp")

    if continents:
        queryset = queryset.filter(continent__in=continents)
    if countries:
        queryset = queryset.filter(country__in=countries)
    if industries:
        queryset = queryset.filter(industry__in=industries)
    if expertise:
        queryset = queryset.filter(expertise_tags__icontains=expertise)
    if is_rfp:
        queryset = queryset.filter(is_rfp=True)

    # Search
    q = request.GET.get("q")
    if q:
        queryset = queryset.filter(title__icontains=q) | queryset.filter(
            company__icontains=q
        )

    # Sort
    queryset = queryset.order_by("-created_at")

    paginator = Paginator(queryset, RESULTS_PER_PAGE)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    # Meta data for filters
    all_continents = Job.objects.values_list("continent", flat=True).distinct()
    all_countries = Job.objects.values_list("country", flat=True).distinct()
    all_industries = Job.objects.values_list("industry", flat=True).distinct()

    context = {
        "jobs": page_obj,
        "all_continents": [c for c in all_continents if c],
        "all_countries": [c for c in all_countries if c],
        "all_industries": [i for i in all_industries if i],
        "filters": {
            "continents": continents,
            "countries": countries,
            "industries": industries,
            "expertise": expertise,
            "is_rfp": is_rfp,
            "q": q,
        },
    }

    return render(request, "job_scraper/dashboard.html", context)


def trigger_scrape(request: HttpRequest):
    """
    Manually triggers the consolidated scraper.
    """
    keywords = request.GET.get("q", "software contract")
    location = request.GET.get("countries", "us")

    scraper = JobScraper()
    new_jobs = scraper.get_recent_jobs(location, keywords, max_pages=1)

    # Lead enrichment for new jobs
    from django.conf import settings

    if settings.DEBUG_ENRICHMENT and new_jobs:
        from .apollo_client import ApolloClient

        apollo = ApolloClient()
        for job in new_jobs[:5]:
            try:
                apollo.enrich_job_contacts(job)
            except:
                pass

    return redirect("dashboard")


def job_search(request: HttpRequest):
    """
    Unified job search that uses all active custom sources.
    """
    if request.method == "POST":
        keywords = request.POST.get("keywords", "")
        location = request.POST.get("location", "")

        params = {
            "keywords": keywords,
            "location": location,
        }

        try:
            country = str(location).strip() or "us"
            search_keywords = str(keywords).strip() or None

            scraper = JobScraper()
            scraped_jobs = scraper.get_recent_jobs(
                country, search_keywords, max_pages=2
            )

            # Since get_recent_jobs now returns Job objects, we just need to provide them to context
            paginator = Paginator(scraped_jobs, RESULTS_PER_PAGE)
            page_number = request.GET.get("page", 1)
            page_obj = paginator.get_page(page_number)

            context = _job_search_context(
                results=page_obj, pagination=page_obj, params=params
            )
        except Exception as e:
            logger.error(f"Error during unified job search: {e}")
            context = _job_search_context(
                results=[],
                params=params,
                error="An error occurred while scraping. Please try again.",
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
                use_stealth=request.POST.get("use_stealth") == "on",
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


def edit_website(request: HttpRequest, website_id: int):
    """View to edit an existing custom website configuration"""
    website = get_object_or_404(CustomWebsite, id=website_id)

    if request.method == "POST":
        website.name = request.POST.get("name")
        website.base_url = request.POST.get("base_url")
        website.search_url = request.POST.get("search_url")
        website.job_list_selector = request.POST.get("job_list_selector")
        website.title_selector = request.POST.get("title_selector")
        website.company_selector = request.POST.get("company_selector")
        website.location_selector = request.POST.get("location_selector")
        website.job_link_selector = request.POST.get("job_link_selector")
        website.salary_selector = request.POST.get("salary_selector", "")
        website.date_selector = request.POST.get("date_selector", "")
        website.apply_link_selector = request.POST.get("apply_link_selector", "")
        website.description_selector = request.POST.get("description_selector", "")
        website.requirements_selector = request.POST.get("requirements_selector", "")
        website.use_stealth = request.POST.get("use_stealth") == "on"

        website.save()
        messages.success(request, f'Website "{website.name}" updated successfully!')
        return redirect("manage_websites")

    return render(
        request,
        "job_scraper/edit_website.html",
        {"website": website},
    )
