import logging
import threading
from urllib.parse import urlencode

from django.conf import settings
from django.core.cache import cache
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import connection
from django.db.models import Q
from django.http import HttpRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import CustomWebsite, Job
from .request_scraper import JobScraper

logger = logging.getLogger(__name__)

RESULTS_PER_PAGE = 10

COUNTRY_ALIASES = {
    "us": "United States",
    "usa": "United States",
    "united states": "United States",
    "uk": "United Kingdom",
    "gb": "United Kingdom",
    "united kingdom": "United Kingdom",
    "uae": "United Arab Emirates",
}


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

    def apply_case_insensitive_in_filter(qs, field, values):
        query = Q()
        for value in values:
            query |= Q(**{f"{field}__iexact": value})
        return qs.filter(query)

    def normalize_country_filters(values):
        normalized = []
        for value in values:
            lowered = value.strip().lower()
            canonical = COUNTRY_ALIASES.get(lowered)
            if canonical:
                normalized.append(canonical)
            normalized.append(value.strip())
        return [value for value in normalized if value]

    continents = parse_filter(request.GET.get("continents"))
    countries = parse_filter(request.GET.get("countries"))
    industries = parse_filter(request.GET.get("industries"))
    expertise = request.GET.get("expertise")
    is_rfp = request.GET.get("is_rfp")
    source_id = request.GET.get("source_id", "")

    if source_id and source_id != "all":
        try:
            source_website = CustomWebsite.objects.only("name").get(
                id=int(source_id), is_active=True
            )
            queryset = queryset.filter(source_website=source_website.name)
        except (ValueError, CustomWebsite.DoesNotExist):
            source_id = ""

    if continents:
        queryset = apply_case_insensitive_in_filter(queryset, "continent", continents)
    if countries:
        country_filters = normalize_country_filters(countries)
        queryset = apply_case_insensitive_in_filter(
            queryset, "country", country_filters
        )
    if industries:
        queryset = apply_case_insensitive_in_filter(queryset, "industry", industries)
    if expertise:
        queryset = queryset.filter(expertise_tags__icontains=expertise)
    if is_rfp:
        queryset = queryset.filter(is_rfp=True)

    # Search
    q = request.GET.get("q")
    if q:
        query = Q()
        for word in q.split():
            query &= (
                Q(title__icontains=word)
                | Q(company__icontains=word)
                | Q(description__icontains=word)
            )
        queryset = queryset.filter(query)

    # Sort
    queryset = queryset.order_by("-updated_at")

    paginator = Paginator(queryset, RESULTS_PER_PAGE)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    # Clean query string for pagination
    query_dict = request.GET.copy()
    if "page" in query_dict:
        del query_dict["page"]
    query_string = query_dict.urlencode()

    # Meta data for filters
    all_continents = Job.objects.values_list("continent", flat=True).distinct()
    all_countries = Job.objects.values_list("country", flat=True).distinct()
    all_industries = Job.objects.values_list("industry", flat=True).distinct()

    context = {
        "jobs": page_obj,
        "all_continents": [c for c in all_continents if c],
        "all_countries": [c for c in all_countries if c],
        "all_industries": [i for i in all_industries if i],
        "active_websites": CustomWebsite.objects.filter(is_active=True),
        "filters": {
            "continents": continents,
            "countries": countries,
            "industries": industries,
            "expertise": expertise,
            "is_rfp": is_rfp,
            "q": q,
            "source_id": source_id,
        },
        "query_string": query_string,
    }

    return render(request, "job_scraper/dashboard.html", context)


@require_POST
def trigger_scrape(request: HttpRequest):
    """
    Manually triggers the consolidated scraper.
    """
    keywords = request.POST.get("q", "software contract")
    country_filters = [
        item.strip()
        for item in request.POST.get("countries", "").split(",")
        if item.strip()
    ]
    continent_filters = [
        item.strip()
        for item in request.POST.get("continents", "").split(",")
        if item.strip()
    ]
    location = (
        country_filters[0]
        if country_filters
        else (continent_filters[0] if continent_filters else "us")
    )
    source_id = request.POST.get("source_id")

    website_id = None
    if source_id and source_id != "all":
        try:
            website_id = int(source_id)
        except ValueError:
            pass

    scraper = JobScraper()
    logger.info(
        "manual_scrape_start website_id=%s location=%s keywords=%s",
        website_id,
        location,
        keywords,
    )
    new_jobs = scraper.get_recent_jobs(
        location, keywords, max_pages=1, website_id=website_id
    )
    logger.info(
        "manual_scrape_done website_id=%s jobs_new=%s",
        website_id,
        len(new_jobs),
    )

    # Lead enrichment for new jobs

    if settings.DEBUG_ENRICHMENT and new_jobs:
        from .apollo_client import ApolloClient

        def run_enrichment(jobs_list):
            apollo = ApolloClient()
            for job in jobs_list[:10]:  # Enrich up to 10 jobs
                try:
                    apollo.enrich_job_contacts(job)
                except Exception:
                    logger.exception("background_enrichment_failed job_id=%s", job.id)

        # Run in background to avoid hanging the UI
        thread = threading.Thread(target=run_enrichment, args=(new_jobs,))
        thread.start()

    query_params = {}
    for key in (
        "q",
        "continents",
        "countries",
        "industries",
        "expertise",
        "is_rfp",
        "source_id",
    ):
        value = request.POST.get(key)
        if value:
            query_params[key] = value

    query_string = urlencode(query_params)
    redirect_url = reverse("dashboard")
    if query_string:
        redirect_url = f"{redirect_url}?{query_string}"
    return redirect(redirect_url)


def job_detail(request: HttpRequest, job_id: int):
    try:
        job = get_object_or_404(Job, pk=job_id)
        enrichment_state = "idle"

        if not job.contacts.exists():
            from .apollo_client import ApolloClient

            apollo = ApolloClient()
            lock_key = f"job_enrichment_lock_{job.id}"
            completed_key = f"job_enrichment_completed_{job.id}"

            if not apollo.debug_mode and not apollo.api_key:
                enrichment_state = "unavailable"
            elif connection.in_atomic_block:
                enrichment_state = "idle"
            elif cache.get(completed_key):
                enrichment_state = "idle"
            else:
                if cache.add(lock_key, True, timeout=300):
                    enrichment_state = "running"

                    def run_enrichment(target_job_id):
                        try:
                            target_job = Job.objects.get(pk=target_job_id)
                            count = ApolloClient().enrich_job_contacts(target_job)
                            logger.info(
                                "job_detail_enrichment_done job_id=%s contacts=%s",
                                target_job_id,
                                count,
                            )
                        except Exception:
                            logger.exception(
                                "job_detail_enrichment_failed job_id=%s", target_job_id
                            )
                        finally:
                            cache.set(completed_key, True, timeout=900)
                            cache.delete(lock_key)

                    thread = threading.Thread(target=run_enrichment, args=(job.id,))
                    thread.start()
                else:
                    enrichment_state = "pending"

        return render(
            request,
            "job_scraper/job_detail.html",
            {
                "job": job,
                "enrichment_state": enrichment_state,
            },
        )

    except Exception:
        logger.exception("job_detail_fetch_failed job_id=%s", job_id)
        return render(
            request,
            "job_scraper/job_detail.html",
            {"job": None, "error": "An error occurred while fetching job details."},
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
        is_api = request.POST.get("is_api") == "on"

        if name and base_url and search_url:
            CustomWebsite.objects.create(
                name=name,
                base_url=base_url,
                search_url=search_url,
                job_list_selector=job_list_selector or "N/A",
                title_selector=title_selector or "N/A",
                company_selector=company_selector or "N/A",
                location_selector=location_selector or "N/A",
                job_link_selector=job_link_selector or "N/A",
                salary_selector=request.POST.get("salary_selector", ""),
                date_selector=request.POST.get("date_selector", ""),
                apply_link_selector=request.POST.get("apply_link_selector", ""),
                description_selector=request.POST.get("description_selector", ""),
                requirements_selector=request.POST.get("requirements_selector", ""),
                use_stealth=request.POST.get("use_stealth") == "on",
                is_api=is_api,
                api_jobs_path=request.POST.get("api_jobs_path", ""),
                api_title_key=request.POST.get("api_title_key", ""),
                api_company_key=request.POST.get("api_company_key", ""),
                api_location_key=request.POST.get("api_location_key", ""),
                api_description_key=request.POST.get("api_description_key", ""),
                api_url_key=request.POST.get("api_url_key", ""),
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


@require_POST
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
