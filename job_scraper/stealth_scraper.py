import asyncio
import logging
import random
import time

from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

from .models import CustomWebsite, Job
from .utils import get_continent_from_country

logger = logging.getLogger(__name__)


class StealthScraper:
    """
    A generic stealth scraper using Playwright to bypass bot protection.
    """

    def __init__(self, headless=True):
        self.headless = headless

    def scrape(
        self, website: CustomWebsite, keywords: str, location: str, max_pages: int = 1
    ):
        """
        Generic scrape method that uses a CustomWebsite object's selectors.
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            Stealth().apply_stealth_sync(page)

            all_new_jobs = []

            for page_num in range(max_pages):
                # Build search URL from template
                search_url = website.search_url
                if "{keywords}" in search_url:
                    search_url = search_url.replace("{keywords}", keywords)
                if "{location}" in search_url:
                    search_url = search_url.replace("{location}", location)
                if "{page}" in search_url:
                    search_url = search_url.replace("{page}", str(page_num + 1))

                logger.info(f"Navigating to {search_url} (Page {page_num+1})")

                try:
                    page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
                    time.sleep(random.uniform(4, 8))

                    # Scroll to trigger lazy loading
                    page.evaluate("window.scrollTo(0, 800)")
                    time.sleep(1)

                    # Wait for results or timeout
                    try:
                        page.wait_for_selector(website.job_list_selector, timeout=20000)
                    except Exception:
                        logger.warning(
                            f"Timeout waiting for {website.job_list_selector}"
                        )

                    # Check for CAPTCHA
                    content_lower = page.content().lower()
                    if any(
                        x in content_lower
                        for x in ["recaptcha", "hcaptcha", "cloudflare"]
                    ):
                        logger.error(f"Anti-bot detected on {website.name}")
                        break

                    job_elements = page.query_selector_all(website.job_list_selector)
                    logger.info(
                        f"Found {len(job_elements)} job cards on {website.name}"
                    )

                    for element in job_elements:
                        try:
                            # Extract data using model selectors
                            title = ""
                            if website.title_selector:
                                title_elem = element.query_selector(
                                    website.title_selector
                                )
                                if title_elem:
                                    # Try title attribute first, then inner text
                                    title = (
                                        title_elem.get_attribute("title")
                                        or title_elem.inner_text()
                                    )

                            company = ""
                            if website.company_selector:
                                company_elem = element.query_selector(
                                    website.company_selector
                                )
                                company = (
                                    company_elem.inner_text() if company_elem else ""
                                )

                            loc_text = ""
                            if website.location_selector:
                                location_elem = element.query_selector(
                                    website.location_selector
                                )
                                loc_text = (
                                    location_elem.inner_text() if location_elem else ""
                                )

                            job_url = ""
                            if website.job_link_selector:
                                link_elem = element.query_selector(
                                    website.job_link_selector
                                )
                                if link_elem:
                                    relative_url = link_elem.get_attribute("href")
                                    if relative_url:
                                        from urllib.parse import urljoin

                                        job_url = urljoin(
                                            website.base_url, relative_url
                                        )

                            if not job_url or not title:
                                continue

                            # Save/Update Job
                            city = ""
                            country = ""
                            if "," in loc_text:
                                parts = loc_text.split(",")
                                city = parts[0].strip()
                                country = parts[1].strip()
                            else:
                                country = loc_text.strip()

                            continent = get_continent_from_country(country)

                            job, created = Job.objects.update_or_create(
                                source_url=job_url,
                                defaults={
                                    "title": title.strip(),
                                    "company": company.strip(),
                                    "location": loc_text.strip(),
                                    "city": city,
                                    "country": country,
                                    "continent": continent,
                                    "source_website": website.name,
                                    "is_rfp": "contract" in keywords.lower()
                                    or "rfp" in keywords.lower(),
                                },
                            )
                            if created:
                                all_new_jobs.append(job)

                        except Exception as e:
                            logger.error(f"Error parsing card on {website.name}: {e}")

                except Exception as e:
                    logger.error(f"Page navigation failed for {website.name}: {e}")
                    break

            browser.close()
            return all_new_jobs

    def scrape_indeed(self, keywords, location, max_pages=1):
        """Deprecated: Use generic scrape() instead"""
        website = CustomWebsite.objects.get(name="Indeed")
        return self.scrape(website, keywords, location, max_pages)

    def _get_description(self, page, job_url):
        """Fetch job description from a specific job URL."""
        try:
            page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(random.uniform(1, 3))
            desc_elem = page.query_selector("#jobDescriptionText")
            return desc_elem.inner_text() if desc_elem else ""
        except Exception as e:
            logger.error(f"Failed to get description for {job_url}: {e}")
            return ""
