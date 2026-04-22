import logging
import random
import re
import time
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .models import CustomWebsite, Job

logger = logging.getLogger(__name__)

EASY_APPLY_INDICATORS = [
    "easy apply",
    "easyapply",
    "quick apply",
    "apply with linkedin",
    "apply with profile",
    "apply with your linkedin profile",
    "one-click apply",
    "apply with one click",
    "apply with your profile",
    "apply with your resume",
    "apply with your linkedin",
    "apply with linkedin profile",
    "apply with linkedin resume",
]


class JobScraper:
    """Enhanced scraper that can handle multiple websites and extract detailed job information"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
        )

    def get_recent_jobs(
        self,
        country: str,
        keywords: Optional[str] = None,
        max_pages: int = 2,
        website_id: Optional[int] = None,
    ) -> List[Job]:
        """Get recent job postings from active custom websites"""
        all_new_jobs = []
        active_websites = CustomWebsite.objects.filter(is_active=True)
        if website_id:
            active_websites = active_websites.filter(id=website_id)

        for website in active_websites:
            try:
                if website.is_api:
                    from .api_scraper import ApiScraper

                    scraper = ApiScraper()
                    jobs = scraper.scrape(website, keywords, country)
                    all_new_jobs.extend(jobs)
                elif website.use_stealth:
                    from .stealth_scraper import StealthScraper

                    scraper = StealthScraper(headless=True)
                    jobs = scraper.scrape(website, keywords, country, max_pages)
                    all_new_jobs.extend(jobs)
                else:
                    jobs = self._scrape_custom_website(
                        website, country, keywords, max_pages
                    )
                    all_new_jobs.extend(jobs)

                logger.info(f"Scraped {len(jobs)} jobs from {website.name}")

            except Exception as e:
                logger.error(f"Error scraping {website.name}: {e}")
                continue

        return all_new_jobs

    def _scrape_custom_website(
        self,
        website: CustomWebsite,
        country: str,
        keywords: Optional[str],
        max_pages: int,
    ) -> List[Job]:
        """Scrape custom website using stored selectors (Requests version)"""
        jobs = []
        error_msg = ""
        html_content = ""
        parsed_jobs_count = 0

        for page in range(max_pages):
            try:
                # Build search URL
                search_url = website.search_url
                if "{keywords}" in search_url and keywords:
                    search_url = search_url.replace("{keywords}", keywords)
                if "{location}" in search_url:
                    search_url = search_url.replace("{location}", country)
                if "{page}" in search_url:
                    search_url = search_url.replace("{page}", str(page + 1))

                response = self.session.get(search_url, timeout=30)
                try:
                    response.raise_for_status()
                except Exception as e:
                    error_msg = f"HTTP Error: {e}"
                    html_content = response.text if hasattr(response, "text") else ""
                    break

                soup = BeautifulSoup(response.content, "html.parser")
                job_cards = soup.select(website.job_list_selector)

                if not job_cards:
                    error_msg = f"No job cards found matching selector: {website.job_list_selector}"
                    html_content = response.text
                    break

                for card_number, card in enumerate(job_cards, start=1):
                    try:
                        job_data = self._parse_custom_card(
                            card,
                            website,
                            page + 1,
                            card_number,
                        )
                        if job_data:
                            # If we have a detail link and description selector, fetch details
                            if job_data.get("job_url") and website.description_selector:
                                detail_data = self._get_custom_details(
                                    job_data["job_url"], website
                                )
                                job_data.update(detail_data)

                            # Create/Update the Job model instance
                            job, created = Job.objects.update_or_create(
                                source_url=job_data["job_url"],
                                defaults={
                                    "title": job_data["title"],
                                    "company": job_data["company"],
                                    "location": job_data["location"],
                                    "salary": job_data.get("salary", ""),
                                    "posted_date": None,  # Parsing dates generically is hard, we'll use created_at
                                    "source_website": website.name,
                                    "description": job_data.get("description", ""),
                                    "requirements": job_data.get("requirements", ""),
                                    "application_link": job_data.get(
                                        "application_link", ""
                                    ),
                                    "is_rfp": (
                                        "contract" in keywords.lower()
                                        if keywords
                                        else False
                                    ),
                                },
                            )
                            parsed_jobs_count += 1
                            if created:
                                jobs.append(job)
                    except Exception as e:
                        logger.error(
                            f"Error parsing custom job card on {website.name}: {e}"
                        )
                        continue

                time.sleep(random.uniform(1, 3))

            except Exception as e:
                logger.error(f"Error scraping {website.name} page {page}: {e}")
                error_msg = str(e)
                break

        from .models import ScraperExecutionLog
        from django.core.files.base import ContentFile
        from datetime import datetime

        # Check for silent failures
        if parsed_jobs_count == 0 and not error_msg:
            error_msg = "No jobs found. CSS selectors may be outdated or the site is blocking silently."

        log = ScraperExecutionLog.objects.create(
            website=website,
            scraper_type='requests',
            jobs_found=parsed_jobs_count,
            error_message=error_msg,
        )
        if html_content:
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            log.html_dump.save(f"{website.name}_error_{timestamp_str}.html", ContentFile(html_content.encode('utf-8')), save=True)

        return jobs
    def _get_custom_details(self, job_url: str, website: CustomWebsite) -> Dict:
        """Fetch job detail page using custom selectors"""
        try:
            response = self.session.get(job_url, timeout=20)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")

            description = ""
            if website.description_selector:
                desc_elem = soup.select_one(website.description_selector)
                description = (
                    self._clean_text(desc_elem.get_text()) if desc_elem else ""
                )

            requirements = ""
            if website.requirements_selector:
                req_elem = soup.select_one(website.requirements_selector)
                requirements = self._clean_text(req_elem.get_text()) if req_elem else ""

            application_link = ""
            if website.apply_link_selector:
                apply_elem = soup.select_one(website.apply_link_selector)
                if apply_elem:
                    application_link = apply_elem.get("href")
                    if application_link and not application_link.startswith("http"):
                        application_link = urljoin(website.base_url, application_link)

            return {
                "description": description,
                "requirements": requirements,
                "application_link": application_link or job_url,
            }
        except Exception as e:
            logger.error(f"Error fetching custom details from {job_url}: {e}")
            return {}

    def _parse_custom_card(
        self,
        card,
        custom_website: CustomWebsite,
        page_number: int,
        card_number: int,
    ) -> Optional[Dict]:
        """Parse job card using custom selectors"""
        try:
            # Extract basic information using custom selectors
            title_elem = card.select_one(custom_website.title_selector)
            title = self._clean_text(title_elem.get_text()) if title_elem else ""

            company_elem = card.select_one(custom_website.company_selector)
            company = self._clean_text(company_elem.get_text()) if company_elem else ""

            location_elem = card.select_one(custom_website.location_selector)
            location = (
                self._clean_text(location_elem.get_text()) if location_elem else ""
            )

            # Extract job link
            job_link_elem = card.select_one(custom_website.job_link_selector)
            job_url = ""
            if job_link_elem:
                job_url = job_link_elem.get("href")
                if job_url and not job_url.startswith("http"):
                    job_url = urljoin(custom_website.base_url, job_url)

            # Extract additional information if selectors are provided
            salary = ""
            if custom_website.salary_selector:
                salary_elem = card.select_one(custom_website.salary_selector)
                salary = self._clean_text(salary_elem.get_text()) if salary_elem else ""

            posted_date = ""
            if custom_website.date_selector:
                date_elem = card.select_one(custom_website.date_selector)
                posted_date = (
                    self._clean_text(date_elem.get_text()) if date_elem else ""
                )

            return {
                "id": f"custom-{custom_website.pk}-{page_number}-{card_number}",
                "title": title,
                "company": company,
                "location": location,
                "salary": salary,
                "posted_date": posted_date,
                "source_website": custom_website.name,
                "source_url": job_url,
                "job_url": job_url,
            }

        except Exception as e:
            logger.error(f"Error parsing custom card: {e}")
            return None

    def _extract_requirements(self, description: str) -> str:
        """Extract requirements from job description"""
        requirements_keywords = [
            "requirements",
            "qualifications",
            "skills",
            "experience",
            "must have",
            "should have",
            "preferred",
            "minimum",
        ]

        lines = description.split("\n")
        requirements_lines = []
        in_requirements = False

        for line in lines:
            line_lower = line.lower()

            if any(keyword in line_lower for keyword in requirements_keywords):
                in_requirements = True

            if in_requirements and line.strip():
                if line.strip().startswith(("•", "-", "*", "·")):
                    requirements_lines.append(line.strip())
                elif re.match(r"^\d+\.", line.strip()):
                    requirements_lines.append(line.strip())

        return "\n".join(requirements_lines) if requirements_lines else ""

    def _extract_job_type(self, description: str) -> str:
        """Extract job type from description"""
        job_types = [
            "full-time",
            "part-time",
            "contract",
            "temporary",
            "internship",
            "freelance",
        ]
        description_lower = description.lower()

        for job_type in job_types:
            if job_type in description_lower:
                return job_type.title()

        return "Full-time"  # Default

    def _extract_experience_level(self, description: str) -> str:
        """Extract experience level from description"""
        levels = {
            "entry-level": ["entry level", "junior", "0-2 years", "1-2 years"],
            "mid-level": ["mid level", "intermediate", "3-5 years", "2-5 years"],
            "senior": ["senior", "lead", "5+ years", "7+ years", "experienced"],
            "executive": ["executive", "director", "manager", "head of"],
        }

        description_lower = description.lower()

        for level, keywords in levels.items():
            if any(keyword in description_lower for keyword in keywords):
                return level.title()

        return "Mid-level"  # Default

    def _extract_industry(self, description: str) -> str:
        """Extract industry from description"""
        industries = [
            "technology",
            "healthcare",
            "finance",
            "education",
            "retail",
            "manufacturing",
            "consulting",
            "marketing",
            "sales",
            "engineering",
        ]

        description_lower = description.lower()

        for industry in industries:
            if industry in description_lower:
                return industry.title()

        return "Technology"  # Default

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ""
        return re.sub(r"\s+", " ", text.strip())
