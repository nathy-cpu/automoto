import logging
import random
import re
import time
import uuid
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .models import CustomWebsite, Job

logger = logging.getLogger(__name__)


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
        run_id = uuid.uuid4().hex[:8]
        start_time = time.monotonic()
        all_new_jobs = []
        active_websites = CustomWebsite.objects.filter(is_active=True)
        if website_id:
            active_websites = active_websites.filter(id=website_id)

        logger.info(
            "scrape_run_start run_id=%s websites=%s country=%s max_pages=%s website_id=%s",
            run_id,
            active_websites.count(),
            country,
            max_pages,
            website_id,
        )

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

                logger.info(
                    "scrape_website_done run_id=%s website_id=%s website=%s jobs_new=%s scraper=%s",
                    run_id,
                    website.id,
                    website.name,
                    len(jobs),
                    "api" if website.is_api else ("selenium_stealth" if website.use_stealth else "requests"),
                )

            except Exception:
                logger.exception(
                    "scrape_website_failed run_id=%s website_id=%s website=%s",
                    run_id,
                    website.id,
                    website.name,
                )
                continue

        logger.info(
            "scrape_run_done run_id=%s total_jobs_new=%s duration_ms=%s",
            run_id,
            len(all_new_jobs),
            int((time.monotonic() - start_time) * 1000),
        )

        return all_new_jobs

    def _scrape_custom_website(
        self,
        website: CustomWebsite,
        country: str,
        keywords: Optional[str],
        max_pages: int,
    ) -> List[Job]:
        """Scrape custom website using stored selectors (Requests version)"""
        started_at = time.monotonic()
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

                            # Apply heuristic parsing
                            description = job_data.get("description", "")
                            job_data = self._enrich_job_data(job_data, description, keywords)

                            # Create/Update the Job model instance
                            job, created = Job.objects.update_or_create(
                                source_url=job_data["job_url"],
                                defaults={
                                    "title": job_data["title"],
                                    "company": job_data["company"],
                                    "location": job_data["location"],
                                    "city": job_data.get("city", ""),
                                    "country": job_data.get("country", ""),
                                    "continent": job_data.get("continent", ""),
                                    "salary": job_data.get("salary", ""),
                                    "job_type": job_data.get("job_type", ""),
                                    "experience_level": job_data.get("experience_level", ""),
                                    "industry": job_data.get("industry", ""),
                                    "posted_date": None,  # Parsing dates generically is hard, we'll use created_at
                                    "source_website": website.name,
                                    "description": description,
                                    "requirements": job_data.get("requirements", ""),
                                    "application_link": job_data.get(
                                        "application_link", ""
                                    ),
                                    "is_rfp": (
                                        "contract" in (keywords or "").lower()
                                        or "rfp" in (keywords or "").lower()
                                    ),
                                },
                            )
                            parsed_jobs_count += 1
                            if created:
                                jobs.append(job)
                    except Exception:
                        logger.exception(
                            "card_parse_failed website_id=%s website=%s page=%s card=%s",
                            website.id,
                            website.name,
                            page + 1,
                            card_number,
                        )
                        continue

                time.sleep(random.uniform(1, 3))

            except Exception as e:
                logger.exception(
                    "page_scrape_failed website_id=%s website=%s page=%s",
                    website.id,
                    website.name,
                    page + 1,
                )
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

        logger.info(
            "requests_scrape_done website_id=%s website=%s jobs_new=%s duration_ms=%s has_error=%s",
            website.id,
            website.name,
            len(jobs),
            int((time.monotonic() - started_at) * 1000),
            bool(error_msg),
        )

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
        except Exception:
            logger.exception(
                "detail_fetch_failed website_id=%s website=%s job_url=%s",
                website.id,
                website.name,
                job_url,
            )
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

        except Exception:
            logger.exception(
                "card_parse_exception website_id=%s website=%s page=%s card=%s",
                custom_website.id,
                custom_website.name,
                page_number,
                card_number,
            )
            return None

    def _enrich_job_data(self, job_data: dict, description: str, keywords: str) -> dict:
        """Apply heuristic parsing to fill in missing fields."""
        
        # 1. Location parsing (City, Country, Continent)
        loc_text = job_data.get("location", "")
        city = ""
        country = ""
        continent = ""
        
        US_STATES = [
            "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"
        ]

        if loc_text:
            loc_upper = loc_text.upper()
            # Direct matches for broad regions
            if "EUROPE" in loc_upper:
                country = "United Kingdom" # Fallback country to help continent mapping
                continent = "Europe"
            elif "EMEA" in loc_upper:
                continent = "Europe"
            elif "USA" in loc_upper or "UNITED STATES" in loc_upper:
                country = "United States"
                continent = "North America"
            elif "," in loc_text:
                parts = [p.strip() for p in loc_text.split(",")]
                city = parts[0]
                # Check if last part is a US state or "USA"
                last_part = parts[-1].upper()
                if last_part in US_STATES or last_part == "USA" or last_part == "UNITED STATES":
                    country = "United States"
                    continent = "North America"
                else:
                    country = parts[-1]
            else:
                country = loc_text.strip()
        
        if not continent:
            from .utils import get_continent_from_country
            continent = get_continent_from_country(country) if country else "Unknown"
        
        job_data["city"] = city
        job_data["country"] = country
        job_data["continent"] = continent

        # 2. Requirements fallback
        if not job_data.get("requirements") and description:
            job_data["requirements"] = self._extract_requirements(description)
            
        # 3. Salary fallback
        if not job_data.get("salary") and description:
            job_data["salary"] = self._extract_salary_fallback(description)
            
        # 4. Job type & experience
        job_data["job_type"] = self._extract_job_type(description)
        job_data["experience_level"] = self._extract_experience_level(description)
        job_data["industry"] = self._extract_industry(description)
        
        return job_data

    def _extract_salary_fallback(self, description: str) -> str:
        """Find salary patterns in text like $100,000 - $120,000"""
        salary_pattern = re.compile(
            r"(\$[\d,]+(?:\.\d{2})?(?:\s*(?:-|to)\s*\$[\d,]+(?:\.\d{2})?)?(?:\s*(?:a|per|/)\s*(?:year|yr|month|mo|hour|hr|week|wk|annually|k))?)",
            re.IGNORECASE
        )
        match = salary_pattern.search(description)
        if match:
            return match.group(1)
        
        # Look for EUR/GBP as well
        alt_pattern = re.compile(
            r"((?:€|£)[\d,]+(?:\.\d{2})?(?:\s*(?:-|to)\s*(?:€|£)[\d,]+(?:\.\d{2})?)?(?:\s*(?:a|per|/)\s*(?:year|yr|month|mo|hour|hr|week|wk|annually|k))?)",
            re.IGNORECASE
        )
        alt_match = alt_pattern.search(description)
        if alt_match:
            return alt_match.group(1)
            
        return ""

    def _extract_requirements(self, description: str) -> str:
        """Extract requirements from job description"""
        requirements_keywords = [
            "requirements", "qualifications", "skills", "experience",
            "must have", "should have", "preferred", "minimum",
            "what you need", "what you'll bring", "what we are looking for",
            "what we're looking for", "your profile", "who you are"
        ]

        lines = description.split("\n")
        requirements_lines = []
        in_requirements = False
        
        for line in lines:
            line_lower = line.lower()
            
            # Stop if we hit benefits or other sections
            if any(k in line_lower for k in ["benefits", "what we offer", "perks", "equal opportunity"]):
                in_requirements = False

            if any(keyword in line_lower for keyword in requirements_keywords):
                in_requirements = True
                continue # Skip the header line itself

            if in_requirements and line.strip():
                if line.strip().startswith(("•", "-", "*", "·", "✓", "o ")):
                    requirements_lines.append(line.strip())
                elif re.match(r"^\d+\.", line.strip()):
                    requirements_lines.append(line.strip())

        return "\n".join(requirements_lines) if requirements_lines else ""

    def _extract_job_type(self, description: str) -> str:
        """Extract job type from description"""
        job_types = [
            "full-time", "part-time", "contract", "temporary", "internship", "freelance"
        ]
        description_lower = description.lower()
        for job_type in job_types:
            if job_type in description_lower:
                return job_type.title()
        return "Full-time"

    def _extract_experience_level(self, description: str) -> str:
        """Extract experience level from description"""
        levels = {
            "entry-level": ["entry level", "junior", "0-2 years", "1-2 years"],
            "mid-level": ["mid level", "intermediate", "3-5 years", "2-5 years"],
            "senior": ["senior", "lead", "5+ years", "7+ years", "experienced"],
            "executive": ["executive", "director", "manager", "head of", "chief"],
        }
        description_lower = description.lower()
        for level, keywords in levels.items():
            if any(keyword in description_lower for keyword in keywords):
                return level.title()
        return "Mid-level"

    def _extract_industry(self, description: str) -> str:
        """Extract industry from description"""
        industries = [
            "technology", "healthcare", "finance", "education", "retail",
            "manufacturing", "consulting", "marketing", "sales", "engineering",
            "software", "logistics"
        ]
        description_lower = description.lower()
        for industry in industries:
            if industry in description_lower:
                return industry.title()
        return "Technology"

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ""
        return re.sub(r"\s+", " ", text.strip())
