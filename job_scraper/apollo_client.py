import hashlib
import logging
import os

from django.conf import settings
from django.core.cache import cache

import requests

from .models import Contact

logger = logging.getLogger(__name__)

DEFAULT_CONTACT_TITLES = ["CEO", "CTO", "Head of Engineering", "VP Sales"]


class ApolloClient:
    """
    Client for interacting with the Apollo.io API for lead enrichment.
    """

    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("APOLLO_API_KEY")
        self.base_url = "https://api.apollo.io"
        self.debug_mode = getattr(settings, "DEBUG_ENRICHMENT", True)

    def _handle_http_error(
        self, exc: requests.HTTPError, context: str, company_name: str
    ):
        response = exc.response
        status_code = response.status_code if response is not None else None
        body = response.text[:500] if response is not None else ""

        if status_code == 422:
            logger.warning(
                "%s_unprocessable company=%s status=%s body=%s",
                context,
                company_name,
                status_code,
                body,
            )
            return []

        if status_code in (401, 403):
            cache.set(self._backoff_cache_key(), status_code, timeout=900)
            logger.warning(
                "%s_forbidden company=%s status=%s body=%s backoff_seconds=900",
                context,
                company_name,
                status_code,
                body,
            )
            return []

        if status_code == 429:
            cache.set(self._backoff_cache_key(), status_code, timeout=300)
            logger.warning(
                "%s_rate_limited company=%s status=%s body=%s backoff_seconds=300",
                context,
                company_name,
                status_code,
                body,
            )
            return []

        logger.exception(
            "%s_failed company=%s status=%s",
            context,
            company_name,
            status_code,
        )
        return []

    def _extract_people(self, payload):
        if isinstance(payload, list):
            return payload
        if not isinstance(payload, dict):
            return []
        for key in ("people", "matches", "contacts", "results", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
        return []

    def _backoff_cache_key(self):
        key = (self.api_key or "").encode("utf-8")
        suffix = hashlib.sha256(key).hexdigest()[:12] if key else "no_key"
        return f"apollo_api_backoff:{suffix}"

    def _person_to_contact(self, person):
        data = person.get("person", person) if isinstance(person, dict) else {}
        first_name = data.get("first_name") or ""
        last_name = data.get("last_name") or data.get("last_name_obfuscated") or ""
        name = data.get("name") or f"{first_name} {last_name}".strip()
        return {
            "name": name,
            "title": data.get("title") or data.get("job_title") or "",
            "email": data.get("email") or data.get("primary_email") or "",
            "linkedin_url": data.get("linkedin_url")
            or data.get("linkedin_profile_url")
            or "",
            "phone": data.get("phone_number")
            or data.get("phone")
            or data.get("direct_phone")
            or "",
        }

    def _people_api_search(self, company_name, location=None, titles=None):
        endpoint = f"{self.base_url}/api/v1/mixed_people/api_search"
        params = {
            "q_keywords": company_name,
            "per_page": 5,
            "include_similar_titles": True,
            "person_titles[]": titles or DEFAULT_CONTACT_TITLES,
        }
        if location:
            params["organization_locations[]"] = [location]

        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": self.api_key,
        }

        response = requests.post(endpoint, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        payload = response.json()
        people = self._extract_people(payload)

        logger.info(
            "apollo_people_search_done company=%s people=%s",
            company_name,
            len(people),
        )
        return people

    def _bulk_people_enrich(self, details, company_name):
        endpoint = f"{self.base_url}/api/v1/people/bulk_match"
        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": self.api_key,
        }
        payload = {
            "details": details,
            "reveal_personal_emails": False,
            "reveal_phone_number": False,
        }

        response = requests.post(endpoint, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        people = self._extract_people(data)

        logger.info(
            "apollo_people_enrich_done company=%s people=%s",
            company_name,
            len(people),
        )
        return people

    def search_contacts(self, company_name, location=None, titles=None):
        """
        Search for contacts in a company.
        """
        if self.debug_mode:
            logger.info("apollo_debug_mock_search company=%s", company_name)
            return [
                {
                    "name": "Jane Doe",
                    "title": "CTO",
                    "email": "jane@example.com",
                    "linkedin_url": "https://linkedin.com/in/janedoe",
                    "phone": "+123456789",
                }
            ]

        if not self.api_key:
            logger.error("Apollo API Key is missing.")
            return []

        backoff_status = cache.get(self._backoff_cache_key())
        if backoff_status:
            logger.warning(
                "apollo_search_skipped_backoff company=%s status=%s",
                company_name,
                backoff_status,
            )
            return []

        try:
            people = self._people_api_search(
                company_name, location=location, titles=titles
            )
            person_ids = []
            for person in people:
                person_data = (
                    person.get("person", person) if isinstance(person, dict) else {}
                )
                person_id = person_data.get("id") or person_data.get("person_id")
                if person_id:
                    person_ids.append({"id": person_id})

            if not person_ids:
                return []

            enriched_people = self._bulk_people_enrich(person_ids[:10], company_name)
            contacts = [self._person_to_contact(person) for person in enriched_people]
            contacts = [contact for contact in contacts if contact.get("name")]
            return contacts

        except requests.HTTPError as exc:
            return self._handle_http_error(exc, "apollo_search", company_name)
        except Exception:
            logger.exception("apollo_search_failed company=%s", company_name)
            return []

    def enrich_job_contacts(self, job):
        """
        Find and save contacts for a given job.
        """
        if not job.company or job.company.strip().lower() in [
            "not available",
            "unknown",
            "",
        ]:
            logger.warning(
                "apollo_enrichment_skipped job_id=%s reason=missing_company",
                job.id,
            )
            return 0

        contacts_data = self.search_contacts(job.company, job.location)

        for data in contacts_data:
            Contact.objects.update_or_create(
                job=job,
                name=data["name"],
                defaults={
                    "email": data["email"],
                    "title": data["title"],
                    "phone": data["phone"] or "",
                    "linkedin_url": data["linkedin_url"] or "",
                },
            )

        return len(contacts_data)
