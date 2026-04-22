import logging
import os

from django.conf import settings

import requests

from .models import Contact

logger = logging.getLogger(__name__)


class ApolloClient:
    """
    Client for interacting with the Apollo.io API for lead enrichment.
    """

    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("APOLLO_API_KEY")
        self.base_url = "https://api.apollo.io/v1"
        self.debug_mode = getattr(settings, "DEBUG_ENRICHMENT", True)

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

        endpoint = f"{self.base_url}/mixed_people/search"
        payload = {
            "q_organization_names": company_name,
            "person_titles": titles
            or ["CEO", "CTO", "Head of Engineering", "VP Sales"],
            "page": 1,
            "per_page": 5,
        }

        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": self.api_key,
        }

        try:
            response = requests.post(
                endpoint, json=payload, headers=headers, timeout=10
            )
            response.raise_for_status()
            data = response.json()

            contacts = []
            for person in data.get("people", []):
                contacts.append(
                    {
                        "name": person.get("name"),
                        "title": person.get("title"),
                        "email": person.get("email"),
                        "linkedin_url": person.get("linkedin_url"),
                        "phone": person.get("phone_number"),
                    }
                )
            return contacts

        except requests.HTTPError as exc:
            response = exc.response
            status_code = response.status_code if response is not None else None
            if status_code == 422:
                body = response.text[:500] if response is not None else ""
                logger.warning(
                    "apollo_search_unprocessable company=%s status=%s body=%s",
                    company_name,
                    status_code,
                    body,
                )
                return []
            logger.exception(
                "apollo_search_failed company=%s status=%s",
                company_name,
                status_code,
            )
            return []
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
