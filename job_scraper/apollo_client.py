import requests
import logging
import os
from django.conf import settings

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
            logger.info(f"[DEBUG MODE] Mocking contact search for {company_name}")
            return [
                {
                    "name": "Jane Doe",
                    "title": "CTO",
                    "email": "jane@example.com",
                    "linkedin_url": "https://linkedin.com/in/janedoe",
                    "phone": "+123456789"
                }
            ]

        if not self.api_key:
            logger.error("Apollo API Key is missing.")
            return []

        endpoint = f"{self.base_url}/mixed_people/search"
        payload = {
            "api_key": self.api_key,
            "q_organization_names": company_name,
            "person_titles": titles or ["CEO", "CTO", "Head of Engineering", "VP Sales"],
            "page": 1,
            "per_page": 5
        }
        
        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache"
        }

        try:
            response = requests.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            contacts = []
            for person in data.get("people", []):
                contacts.append({
                    "name": person.get("name"),
                    "title": person.get("title"),
                    "email": person.get("email"),
                    "linkedin_url": person.get("linkedin_url"),
                    "phone": person.get("phone_number")
                })
            return contacts

        except Exception as e:
            logger.error(f"Apollo search failed: {e}")
            return []

    def enrich_job_contacts(self, job):
        """
        Find and save contacts for a given job.
        """
        from .models import Contact
        
        contacts_data = self.search_contacts(job.company, job.location)
        
        for data in contacts_data:
            Contact.objects.get_or_create(
                job=job,
                email=data['email'],
                defaults={
                    'name': data['name'],
                    'title': data['title'],
                    'phone': data['phone'] or "",
                    'linkedin_url': data['linkedin_url'] or ""
                }
            )
        
        return len(contacts_data)
