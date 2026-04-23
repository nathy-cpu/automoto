import logging
import time
import uuid
from datetime import datetime
from typing import List

from django.core.files.base import ContentFile

import requests

from .models import CustomWebsite, Job, ScraperExecutionLog

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
        run_id = uuid.uuid4().hex[:8]
        started_at = time.monotonic()
        all_new_jobs = []
        saved_jobs = []
        error_msg = ""
        json_dump = ""
        keywords = (keywords or "").strip()
        keyword_terms = [term for term in keywords.lower().split() if term]
        location = (location or "").strip()
        payload_jobs_count = 0
        matched_jobs_count = 0

        logger.info(
            "api_scrape_start run_id=%s website_id=%s website=%s",
            run_id,
            website.id,
            website.name,
        )

        try:
            # Build URL - APIs often use simple query params
            url = website.search_url.format(
                keywords=keywords, location=location, page=1
            )

            logger.info(
                "api_fetch_start run_id=%s website_id=%s url=%s",
                run_id,
                website.id,
                url,
            )
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
                    payload_jobs_count = len(job_list)
                    for item in job_list:
                        try:
                            # Generic mapping from JSON to Job fields
                            job_data = {
                                "title": self._get_val(item, website.api_title_key),
                                "company": self._get_val(item, website.api_company_key),
                                "location": self._get_val(
                                    item, website.api_location_key
                                ),
                                "description": self._get_val(
                                    item, website.api_description_key
                                ),
                                "source_url": self._get_val(item, website.api_url_key),
                            }

                            # Basic validation
                            if not job_data["title"] or not job_data["source_url"]:
                                continue

                            # Filter by keywords in memory if necessary
                            searchable_text = (
                                job_data["title"] + " " + job_data["description"]
                            ).lower()
                            if keyword_terms and not all(
                                term in searchable_text for term in keyword_terms
                            ):
                                continue

                            matched_jobs_count += 1
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
                                            "contract" in keyword_terms
                                            or "rfp" in keyword_terms
                                        ),
                                    },
                                }
                            )

                        except Exception:
                            logger.exception(
                                "api_item_parse_failed run_id=%s website_id=%s",
                                run_id,
                                website.id,
                            )

        except Exception as e:
            error_msg = f"Unexpected API error: {e}"
            logger.exception(
                "api_scrape_failed run_id=%s website_id=%s website=%s",
                run_id,
                website.id,
                website.name,
            )

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
            if payload_jobs_count and keyword_terms:
                error_msg = (
                    f"API returned {payload_jobs_count} jobs but 0 matched keywords '{keywords}'."
                )
            else:
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

        logger.info(
            "api_scrape_done run_id=%s website_id=%s website=%s jobs_seen=%s jobs_matched=%s jobs_new=%s duration_ms=%s has_error=%s",
            run_id,
            website.id,
            website.name,
            payload_jobs_count,
            matched_jobs_count,
            len(saved_jobs),
            int((time.monotonic() - started_at) * 1000),
            bool(error_msg),
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
