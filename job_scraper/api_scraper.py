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
    Bypasses browser stealth scraping entirely for faster, reliable data fetching.
    """

    def __init__(self, run_id=None):
        self._run_id = run_id

    def scrape(self, website: CustomWebsite, keywords: str, location: str) -> List[Job]:
        keywords = (keywords or "").strip()
        location = (location or "").strip()
        started_at = time.monotonic()
        saved_jobs = []
        json_dump = ""
        error_msg = ""
        payload_jobs_count = 0
        matched_jobs_count = 0
        keyword_terms = [term for term in keywords.lower().split() if term]

        self._ensure_run_id()
        self._log_scrape_start(website)

        try:
            response = self._fetch_response(website, keywords, location)
            data, json_dump, error_msg = self._parse_response(response)

            job_entries = []
            if not error_msg:
                job_entries, payload_jobs_count, matched_jobs_count, error_msg = (
                    self._collect_job_entries(website, data, keyword_terms, keywords)
                )

            saved_jobs = self._save_jobs(job_entries)
            error_msg = self._finalize_error_message(
                error_msg,
                payload_jobs_count,
                matched_jobs_count,
                keywords,
            )
            self._log_execution(
                website,
                len(saved_jobs),
                error_msg,
                json_dump,
            )
            self._log_scrape_done(
                website,
                payload_jobs_count,
                matched_jobs_count,
                len(saved_jobs),
                started_at,
                bool(error_msg),
            )
            return saved_jobs
        except Exception as exc:
            error_msg = f"Unexpected API error: {exc}"
            logger.exception(
                "api_scrape_failed run_id=%s website_id=%s website=%s",
                self._run_id,
                website.id,
                website.name,
            )
            self._log_execution(website, len(saved_jobs), error_msg, json_dump)
            self._log_scrape_done(
                website,
                payload_jobs_count,
                matched_jobs_count,
                len(saved_jobs),
                started_at,
                True,
            )
            return saved_jobs
        finally:
            self._run_id = None

    def _ensure_run_id(self):
        if not self._run_id:
            self._run_id = uuid.uuid4().hex[:8]

    def _log_scrape_start(self, website: CustomWebsite):
        logger.info(
            "api_scrape_start run_id=%s website_id=%s website=%s",
            self._run_id,
            website.id,
            website.name,
        )

    def _fetch_response(self, website: CustomWebsite, keywords: str, location: str):
        url = website.search_url.format(keywords=keywords, location=location, page=1)
        logger.info(
            "api_fetch_start run_id=%s website_id=%s url=%s",
            self._run_id,
            website.id,
            url,
        )
        return requests.get(url, timeout=30)

    def _parse_response(self, response):
        json_dump = response.text if hasattr(response, "text") else ""
        try:
            response.raise_for_status()
            return response.json(), json_dump, ""
        except Exception as exc:
            return None, json_dump, f"API Request Failed: {exc}"

    def _collect_job_entries(
        self,
        website: CustomWebsite,
        data,
        keyword_terms,
        keywords: str,
    ):
        job_list = self._get_nested_data(data, website.api_jobs_path)
        if not job_list or not isinstance(job_list, list):
            return [], 0, 0, f"No job list found at path '{website.api_jobs_path}'"

        payload_jobs_count = len(job_list)
        matched_jobs_count = 0
        job_entries = []

        for item in job_list:
            job_entry = self._build_job_entry(website, item, keyword_terms)
            if job_entry is None:
                continue
            matched_jobs_count += 1
            job_entries.append(job_entry)

        return job_entries, payload_jobs_count, matched_jobs_count, ""

    def _build_job_entry(self, website: CustomWebsite, item, keyword_terms):
        try:
            job_data = {
                "title": self._get_val(item, website.api_title_key),
                "company": self._get_val(item, website.api_company_key),
                "location": self._get_val(item, website.api_location_key),
                "description": self._get_val(item, website.api_description_key),
                "source_url": self._get_val(item, website.api_url_key),
            }

            if not job_data["title"] or not job_data["source_url"]:
                return None

            searchable_text = (
                job_data["title"] + " " + job_data["description"]
            ).lower()
            if keyword_terms and not all(term in searchable_text for term in keyword_terms):
                return None

            return {
                "source_url": job_data["source_url"],
                "defaults": {
                    "title": job_data["title"].strip(),
                    "company": job_data["company"].strip(),
                    "location": job_data["location"].strip(),
                    "source_website": website.name,
                    "description": job_data["description"],
                    "is_rfp": (
                        "contract" in keyword_terms or "rfp" in keyword_terms
                    ),
                },
            }
        except Exception:
            logger.exception(
                "api_item_parse_failed run_id=%s website_id=%s",
                self._run_id,
                website.id,
            )
            return None

    def _save_jobs(self, job_entries):
        saved_jobs = []
        for job_entry in job_entries:
            job, created = Job.objects.update_or_create(
                source_url=job_entry["source_url"],
                defaults=job_entry["defaults"],
            )
            if created:
                saved_jobs.append(job)
        return saved_jobs

    def _finalize_error_message(
        self,
        error_msg: str,
        payload_jobs_count: int,
        matched_jobs_count: int,
        keywords: str,
    ):
        if error_msg:
            return error_msg
        if matched_jobs_count:
            return ""
        if payload_jobs_count and keywords:
            return f"API returned {payload_jobs_count} jobs but 0 matched keywords '{keywords}'."
        return "No jobs found. JSON paths may be broken or the API returned empty results."

    def _log_execution(
        self,
        website: CustomWebsite,
        jobs_found: int,
        error_message: str,
        json_dump: str,
    ):
        log = ScraperExecutionLog.objects.create(
            website=website,
            scraper_type="api",
            jobs_found=jobs_found,
            error_message=error_message,
        )

        if json_dump:
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            log.html_dump.save(
                f"{website.name}_api_{timestamp_str}.json",
                ContentFile(json_dump.encode("utf-8")),
                save=True,
            )

    def _log_scrape_done(
        self,
        website: CustomWebsite,
        payload_jobs_count: int,
        matched_jobs_count: int,
        saved_jobs_count: int,
        started_at: float,
        has_error: bool,
    ):
        logger.info(
            "api_scrape_done run_id=%s website_id=%s website=%s jobs_seen=%s jobs_matched=%s jobs_new=%s duration_ms=%s has_error=%s",
            self._run_id,
            website.id,
            website.name,
            payload_jobs_count,
            matched_jobs_count,
            saved_jobs_count,
            int((time.monotonic() - started_at) * 1000),
            has_error,
        )

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
