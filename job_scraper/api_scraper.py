import logging
from datetime import datetime
from typing import List

import requests

from django.core.files.base import ContentFile

from .models import Job, CustomWebsite, ScraperExecutionLog

logger = logging.getLogger(__name__)

class ApiScraper:
    """
    A scraper for websites that provide a JSON API endpoint.
    Bypasses Playwright/Stealth entirely for faster, reliable data fetching.
    """

    def scrape(self, website: CustomWebsite, keywords: str, location: str) -> List[Job]:
        """
        Fetch jobs from a JSON API endpoint and map keys to Job model.
        """
        all_new_jobs = []
        saved_jobs = []
        error_msg = ""
        json_dump = ""
        keywords = (keywords or "").strip()
        location = (location or "").strip()

        try:
            # Build URL - APIs often use simple query params
            url = website.search_url.format(keywords=keywords, location=location, page=1)

            logger.info(f"Fetching API data from {url}")
            response = requests.get(url, timeout=30)

            try:
                response.raise_for_status()
                data = response.json()
                if hasattr(response, "text"):
                    json_dump = response.text
            except Exception as e:
                error_msg = f"API Request Failed: {e}"
                if hasattr(response, "text"):
                    json_dump = response.text
                data = None

            if not error_msg:
                # Extract list of jobs using path
                job_list = self._get_nested_data(data, website.api_jobs_path)

                if not job_list or not isinstance(job_list, list):
                    error_msg = f"No job list found at path '{website.api_jobs_path}'"
                else:
                    keywords_lower = keywords.lower()
                    for item in job_list:
                        try:
                            # Generic mapping from JSON to Job fields
                            job_data = {
                                "title": self._get_val(item, website.api_title_key),
                                "company": self._get_val(item, website.api_company_key),
                                "location": self._get_val(item, website.api_location_key),
                                "description": self._get_val(item, website.api_description_key),
                                "source_url": self._get_val(item, website.api_url_key),
                            }

                            # Basic validation
                            if not job_data["title"] or not job_data["source_url"]:
                                continue

                            # Filter by keywords in memory if necessary
                            if keywords_lower and keywords_lower not in (
                                job_data["title"] + job_data["description"]
                            ).lower():
                                continue

                            all_new_jobs.append(
                                {
                                    "source_url": job_data["source_url"],
                                    "defaults": {
                                        "title": job_data["title"].strip(),
                                        "company": job_data["company"].strip(),
                                        "location": job_data["location"].strip(),
                                        "source_website": website.name,
                                        "description": job_data["description"],
                                        "is_rfp": (
                                            "contract" in keywords_lower
                                            or "rfp" in keywords_lower
                                        ),
                                    },
                                }
                            )

                        except Exception as e:
                            logger.error(f"Error parsing API item: {e}")

        except Exception as e:
            error_msg = f"Unexpected API error: {e}"
            logger.error(error_msg)

        # Save results and log
        for j_data in all_new_jobs:
            job, created = Job.objects.update_or_create(
                source_url=j_data["source_url"],
                defaults=j_data["defaults"],
            )
            if created:
                saved_jobs.append(job)

        # Check for silent failures
        if len(all_new_jobs) == 0 and not error_msg:
            error_msg = "No jobs found. JSON paths may be broken or the API returned empty results."

        # Log execution
        log = ScraperExecutionLog.objects.create(
            website=website,
            scraper_type="api",
            jobs_found=len(all_new_jobs),
            error_message=error_msg,
        )

        if json_dump:
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            log.html_dump.save(
                f"{website.name}_api_{timestamp_str}.json",
                ContentFile(json_dump.encode("utf-8")),
                save=True,
            )

        return saved_jobs

    def _get_nested_data(self, data, path):
        if not path:
            return data
        keys = path.split(".")
        for key in keys:
            if isinstance(data, dict):
                data = data.get(key)
            else:
                return None
        return data

    def _get_val(self, item, key):
        if not key:
            return ""
        return str(self._get_nested_data(item, key) or "")
