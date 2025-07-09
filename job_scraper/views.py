import json
import logging

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpRequest
from django.shortcuts import get_object_or_404, redirect, render

from .enhanced_scrapers import EnhancedJobScraper
from .models import CustomWebsite, Job
from .scrapers import get_scraper, scrape_jobs

logger = logging.getLogger(__name__)

# Create your views here.


def job_search(request: HttpRequest):
    if request.method == "POST":
        keywords = request.POST.get("keywords", "")
        location = request.POST.get("location", "")
        websites = request.POST.getlist("websites")

        if not websites:
            websites = ["indeed", "linkedin"]  # Default websites

        try:
            # Use location as country for scraping
            country = (
                str(location) if location else "us"
            )  # Default to US if no location specified

            # Handle keywords - make them optional
            search_keywords = str(keywords).strip() if keywords else None

            # Add a small delay to show loading animation
            import time

            time.sleep(0.5)

            # Use enhanced scraper for better results
            enhanced_scraper = EnhancedJobScraper()
            scraped_jobs = enhanced_scraper.get_recent_jobs(
                websites, country, search_keywords, max_pages=15
            )

            # Convert scraped data to format expected by template
            jobs_data = []
            for i, job in enumerate(scraped_jobs):
                # Ensure we have a unique, numeric ID for each job
                job_id = job.get("id")
                if not job_id or not str(job_id).isdigit():
                    job_id = i + 1

                jobs_data.append(
                    {
                        "id": job_id,
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

            # Store jobs data in session for detail view
            request.session["scraped_jobs"] = jobs_data

            # Store search parameters in session for pagination
            request.session["search_params"] = {
                "keywords": keywords,
                "location": location,
                "websites": websites,
            }

            # Pagination
            paginator = Paginator(jobs_data, 10)  # 10 jobs per page
            page_number = request.GET.get("page", 1)
            page_obj = paginator.get_page(page_number)

            context = {
                "results": page_obj,
                "pagination": page_obj,
                "params": {
                    "keywords": keywords,
                    "location": location,
                    "websites": websites,
                },
            }

        except Exception as e:
            logger.error(f"Error during job scraping: {e}")
            context = {
                "results": [],
                "pagination": None,
                "params": {
                    "keywords": keywords,
                    "location": location,
                    "websites": websites,
                },
                "error": "An error occurred while scraping jobs. Please try again.",
            }

        return render(request, "job_scraper/job_search.html", context)

    # Handle GET requests for pagination
    if request.method == "GET" and request.GET.get("page"):
        # Get stored search parameters and jobs from session
        search_params = request.session.get("search_params", {})
        scraped_jobs = request.session.get("scraped_jobs", [])

        if scraped_jobs:
            # Pagination for stored results
            paginator = Paginator(scraped_jobs, 10)
            page_number = request.GET.get("page", 1)
            page_obj = paginator.get_page(page_number)

            context = {
                "results": page_obj,
                "pagination": page_obj,
                "params": search_params,
            }
            return render(request, "job_scraper/job_search.html", context)

    # Get custom websites for the template
    custom_websites = CustomWebsite.objects.filter(is_active=True)
    return render(
        request, "job_scraper/job_search.html", {"custom_websites": custom_websites}
    )


def job_detail(request: HttpRequest, job_id: int):
    try:
        # Get jobs data from session
        scraped_jobs = request.session.get("scraped_jobs", [])

        # Find the job with matching ID
        job_data = None
        for job in scraped_jobs:
            if str(job.get("id")) == str(job_id):
                job_data = job
                break

        # Debug logging
        logger.info(f"Looking for job ID: {job_id}")
        logger.info(f"Available jobs: {[job.get('id') for job in scraped_jobs]}")
        logger.info(f"Found job data: {job_data is not None}")

        if not job_data:
            # Fallback to mock data if job not found
            job_data = {
                "id": job_id,
                "title": "Job Not Found",
                "company": "Unknown",
                "location": "Unknown",
                "source_website": "Unknown",
                "salary": "",
                "posted_date": "",
                "job_url": "",
                "source_url": "",
            }

        # Create detailed job object for template
        job_detail = {
            "id": job_data.get("id"),
            "title": job_data.get("title", "Job Title Not Available"),
            "company": job_data.get("company", "Company Not Available"),
            "industry": job_data.get("industry", "Technology"),
            "location": job_data.get("location", "Location Not Available"),
            "city": (
                job_data.get("location", "").split(",")[0]
                if job_data.get("location")
                else ""
            ),
            "country": "United States",
            "description": job_data.get(
                "description",
                f"This is a {job_data.get('title', 'job')} position at {job_data.get('company', 'a company')}. For more details, please visit the original job posting.",
            ),
            "requirements": job_data.get(
                "requirements",
                "• Experience in the relevant field\n• Strong communication skills\n• Ability to work in a team environment\n• Relevant education or certifications",
            ),
            "salary": job_data.get("salary", "Salary information not available"),
            "job_type": job_data.get("job_type", "Full-time"),
            "experience_level": job_data.get("experience_level", "Mid-level"),
            "deadline": "2024-12-31",
            "posted_date": job_data.get("posted_date", "Recently posted"),
            "application_instructions": "Please apply through the original job posting website.",
            "application_link": job_data.get(
                "application_link", job_data.get("job_url", "")
            ),
            "source_website": job_data.get("source_website", "Unknown"),
            "source_url": job_data.get("source_url", ""),
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
