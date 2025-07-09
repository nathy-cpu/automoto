import logging
import random
import re
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class JobScraper:
    """Base class for job scrapers"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
        )

    def get_recent_jobs(
        self, country: str, keywords: Optional[str] = None, max_pages: int = 5
    ) -> List[Dict]:
        """Get recent job postings from the last 24 hours"""
        raise NotImplementedError

    def parse_job_details(self, job_url: str) -> Dict:
        """Parse detailed job information from a job posting page"""
        raise NotImplementedError

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ""
        return re.sub(r"\s+", " ", text.strip())

    def _extract_salary(self, text: str) -> str:
        """Extract salary information from text"""
        salary_patterns = [
            r"\$[\d,]+(?:-\$[\d,]+)?\s*(?:per\s+year|annually|yearly)",
            r"[\d,]+(?:-\d+)?\s*(?:USD|EUR|GBP)\s*(?:per\s+year|annually)",
            r"\$[\d,]+(?:-\$[\d,]+)?\s*(?:per\s+hour|hourly)",
        ]

        for pattern in salary_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group()
        return ""

    def _extract_date(self, text: str) -> Optional[str]:
        """Extract and parse date information"""
        date_patterns = [
            r"(\d{1,2})\s+(?:days?|hours?)\s+ago",
            r"(\d{1,2})\s+(?:minutes?|mins?)\s+ago",
            r"posted\s+(\d{1,2})\s+(?:days?|hours?)\s+ago",
            r"(\d{1,2}/\d{1,2}/\d{4})",
            r"(\d{1,2}-\d{1,2}-\d{4})",
        ]

        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group()
        return None


class IndeedScraper(JobScraper):
    """Scraper for Indeed.com"""

    def get_recent_jobs(
        self, country: str, keywords: Optional[str] = None, max_pages: int = 5
    ) -> List[Dict]:
        jobs = []

        # Country-specific Indeed URLs
        country_urls = {
            "us": "https://www.indeed.com",
            "uk": "https://uk.indeed.com",
            "ca": "https://ca.indeed.com",
            "au": "https://au.indeed.com",
            "de": "https://de.indeed.com",
            "fr": "https://fr.indeed.com",
        }

        base_url = country_urls.get(country.lower(), "https://www.indeed.com")

        for page in range(max_pages):
            try:
                # Build search URL
                search_params = {
                    "l": country,
                    "fromage": "1",  # Last 24 hours
                    "start": page * 10,
                }

                if keywords:
                    search_params["q"] = keywords

                url = f"{base_url}/jobs"
                response = self.session.get(url, params=search_params)
                response.raise_for_status()

                soup = BeautifulSoup(response.content, "html.parser")
                job_cards = soup.find_all("div", {"data-jk": True})

                if not job_cards:
                    break

                for card in job_cards:
                    try:
                        job_data = self._parse_indeed_card(card, base_url)
                        if job_data:
                            jobs.append(job_data)
                    except Exception as e:
                        logger.error(f"Error parsing Indeed job card: {e}")
                        continue

                time.sleep(random.uniform(1, 3))  # Be respectful

            except Exception as e:
                logger.error(f"Error scraping Indeed page {page}: {e}")
                break

        return jobs

    def _parse_indeed_card(self, card, base_url: str) -> Optional[Dict]:
        """Parse individual job card from Indeed"""
        try:
            job_id = card.get("data-jk")
            if not job_id:
                return None

            # Extract basic info
            title_elem = card.find("h2", class_="jobTitle")
            title = self._clean_text(title_elem.get_text()) if title_elem else ""

            company_elem = card.find("span", class_="companyName")
            company = self._clean_text(company_elem.get_text()) if company_elem else ""

            location_elem = card.find("div", class_="companyLocation")
            location = (
                self._clean_text(location_elem.get_text()) if location_elem else ""
            )

            # Extract salary if available
            salary_elem = card.find("div", class_="salary-snippet")
            salary = self._clean_text(salary_elem.get_text()) if salary_elem else ""

            # Extract posted date
            date_elem = card.find("span", class_="date")
            posted_date = self._clean_text(date_elem.get_text()) if date_elem else ""

            # Build job URL
            job_url = f"{base_url}/viewjob?jk={job_id}"

            return {
                "id": job_id,
                "title": title,
                "company": company,
                "location": location,
                "salary": salary,
                "posted_date": posted_date,
                "source_website": "Indeed",
                "source_url": job_url,
                "job_url": job_url,
            }

        except Exception as e:
            logger.error(f"Error parsing Indeed card: {e}")
            return None

    def parse_job_details(self, job_url: str) -> Dict:
        """Parse detailed job information from Indeed job page"""
        try:
            response = self.session.get(job_url)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")

            # Extract detailed information
            description_elem = soup.find("div", {"id": "jobDescriptionText"})
            description = (
                self._clean_text(description_elem.get_text())
                if description_elem
                else ""
            )

            # Extract requirements
            requirements = self._extract_requirements(description)

            # Extract application instructions
            apply_elem = soup.find("div", class_="jobsearch-ApplyButton")
            application_instructions = (
                self._clean_text(apply_elem.get_text()) if apply_elem else ""
            )

            # Extract application link
            apply_link_elem = soup.find("a", class_="jobsearch-ApplyButton")
            application_link = apply_link_elem.get("href") if apply_link_elem else ""
            if application_link and not application_link.startswith("http"):
                application_link = urljoin(job_url, application_link)

            return {
                "description": description,
                "requirements": requirements,
                "application_instructions": application_instructions,
                "application_link": application_link,
            }

        except Exception as e:
            logger.error(f"Error parsing Indeed job details: {e}")
            return {}


class LinkedInScraper(JobScraper):
    """Scraper for LinkedIn Jobs"""

    def get_recent_jobs(
        self, country: str, keywords: Optional[str] = None, max_pages: int = 5
    ) -> List[Dict]:
        jobs = []

        # LinkedIn Jobs URL
        base_url = "https://www.linkedin.com/jobs/search"

        for page in range(max_pages):
            try:
                search_params = {
                    "location": country,
                    "f_TPR": "r86400",  # Last 24 hours
                    "start": page * 25,
                }

                if keywords:
                    search_params["keywords"] = keywords

                response = self.session.get(base_url, params=search_params)
                response.raise_for_status()

                soup = BeautifulSoup(response.content, "html.parser")
                job_cards = soup.find_all("div", class_="base-card")

                if not job_cards:
                    break

                for card in job_cards:
                    try:
                        job_data = self._parse_linkedin_card(card)
                        if job_data:
                            jobs.append(job_data)
                    except Exception as e:
                        logger.error(f"Error parsing LinkedIn job card: {e}")
                        continue

                time.sleep(random.uniform(2, 4))

            except Exception as e:
                logger.error(f"Error scraping LinkedIn page {page}: {e}")
                break

        return jobs

    def _parse_linkedin_card(self, card) -> Optional[Dict]:
        """Parse individual job card from LinkedIn"""
        try:
            # Extract job ID
            job_link_elem = card.find("a", class_="base-card__full-link")
            if not job_link_elem:
                return None

            job_url = job_link_elem.get("href")
            job_id = job_url.split("/")[-1] if job_url else None

            # Extract basic info
            title_elem = card.find("h3", class_="base-search-card__title")
            title = self._clean_text(title_elem.get_text()) if title_elem else ""

            company_elem = card.find("h4", class_="base-search-card__subtitle")
            company = self._clean_text(company_elem.get_text()) if company_elem else ""

            location_elem = card.find("span", class_="job-search-card__location")
            location = (
                self._clean_text(location_elem.get_text()) if location_elem else ""
            )

            # Extract posted date
            date_elem = card.find("time")
            posted_date = self._clean_text(date_elem.get_text()) if date_elem else ""

            return {
                "id": job_id,
                "title": title,
                "company": company,
                "location": location,
                "posted_date": posted_date,
                "source_website": "LinkedIn",
                "source_url": job_url,
                "job_url": job_url,
            }

        except Exception as e:
            logger.error(f"Error parsing LinkedIn card: {e}")
            return None


class GlassdoorScraper(JobScraper):
    """Scraper for Glassdoor"""

    def get_recent_jobs(
        self, country: str, keywords: Optional[str] = None, max_pages: int = 5
    ) -> List[Dict]:
        jobs = []

        base_url = "https://www.glassdoor.com/Job"

        for page in range(max_pages):
            try:
                search_params = {
                    "loc": country,
                    "fromage": "1",  # Last 24 hours
                    "p": page + 1,
                }

                if keywords:
                    search_params["sc.keyword"] = keywords

                response = self.session.get(base_url, params=search_params)
                response.raise_for_status()

                soup = BeautifulSoup(response.content, "html.parser")
                job_cards = soup.find_all("li", class_="react-job-listing")

                if not job_cards:
                    break

                for card in job_cards:
                    try:
                        job_data = self._parse_glassdoor_card(card)
                        if job_data:
                            jobs.append(job_data)
                    except Exception as e:
                        logger.error(f"Error parsing Glassdoor job card: {e}")
                        continue

                time.sleep(random.uniform(1, 3))

            except Exception as e:
                logger.error(f"Error scraping Glassdoor page {page}: {e}")
                break

        return jobs

    def _parse_glassdoor_card(self, card) -> Optional[Dict]:
        """Parse individual job card from Glassdoor"""
        try:
            # Extract job ID and URL
            job_link_elem = card.find("a", class_="jobLink")
            if not job_link_elem:
                return None

            job_url = job_link_elem.get("href")
            job_id = job_url.split("/")[-1] if job_url else None

            # Extract basic info
            title_elem = card.find("a", class_="jobLink")
            title = self._clean_text(title_elem.get_text()) if title_elem else ""

            company_elem = card.find("a", class_="employer-name")
            company = self._clean_text(company_elem.get_text()) if company_elem else ""

            location_elem = card.find("span", class_="location")
            location = (
                self._clean_text(location_elem.get_text()) if location_elem else ""
            )

            # Extract salary
            salary_elem = card.find("span", class_="salary-estimate")
            salary = self._clean_text(salary_elem.get_text()) if salary_elem else ""

            return {
                "id": job_id,
                "title": title,
                "company": company,
                "location": location,
                "salary": salary,
                "source_website": "Glassdoor",
                "source_url": job_url,
                "job_url": job_url,
            }

        except Exception as e:
            logger.error(f"Error parsing Glassdoor card: {e}")
            return None


def get_scraper(website: str) -> JobScraper:
    """Factory function to get the appropriate scraper"""
    scrapers = {
        "indeed": IndeedScraper,
        "linkedin": LinkedInScraper,
        "glassdoor": GlassdoorScraper,
    }

    scraper_class = scrapers.get(website.lower())
    if not scraper_class:
        raise ValueError(f"Unsupported website: {website}")

    return scraper_class()


def scrape_jobs(
    websites: List[str], country: str, keywords: Optional[str] = None
) -> List[Dict]:
    """Main function to scrape jobs from multiple websites"""
    all_jobs = []

    for website in websites:
        try:
            scraper = get_scraper(website)
            jobs = scraper.get_recent_jobs(country, keywords)
            all_jobs.extend(jobs)
            logger.info(f"Scraped {len(jobs)} jobs from {website}")
        except Exception as e:
            logger.error(f"Error scraping {website}: {e}")
            continue

    return all_jobs


def _extract_requirements(description: str) -> str:
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

        # Check if we're entering requirements section
        if any(keyword in line_lower for keyword in requirements_keywords):
            in_requirements = True

        # Add lines that look like requirements
        if in_requirements and line.strip():
            if line.strip().startswith(("•", "-", "*", "·")):
                requirements_lines.append(line.strip())
            elif re.match(r"^\d+\.", line.strip()):
                requirements_lines.append(line.strip())

    return "\n".join(requirements_lines) if requirements_lines else ""
