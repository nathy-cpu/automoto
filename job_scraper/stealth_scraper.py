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
            error_msg = ""
            screenshot_bytes = None
            html_content = ""

            for page_num in range(1, max_pages + 1):
                url = website.search_url.format(
                    keywords=keywords, location=location, page=page_num
                )
                try:
                    logger.info(f"Navigating to {url}")
                    page.goto(url, wait_until="domcontentloaded", timeout=45000)

                    time.sleep(random.uniform(2, 5))

                    try:
                        page.wait_for_selector(website.job_list_selector, timeout=20000)
                    except Exception as e:
                        logger.warning(
                            f"Timeout waiting for {website.job_list_selector}"
                        )
                        error_msg = f"Timeout waiting for primary selector. Possible CAPTCHA wall."
                        try:
                            html_content = page.content()
                            screenshot_bytes = page.screenshot()
                        except:
                            pass
                        break

                    # Check for CAPTCHA
                    content_lower = page.content().lower()
                    if any(
                        x in content_lower
                        for x in ["recaptcha", "hcaptcha", "cloudflare"]
                    ):
                        logger.error(f"Anti-bot detected on {website.name}")
                        error_msg = "Anti-bot (Cloudflare/CAPTCHA) detected."
                        try:
                            html_content = page.content()
                            screenshot_bytes = page.screenshot()
                        except:
                            pass
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

                            all_new_jobs.append({
                                "source_url": job_url,
                                "defaults": {
                                    "title": title.strip(),
                                    "company": company.strip(),
                                    "location": loc_text.strip(),
                                    "city": city,
                                    "country": country,
                                    "continent": continent,
                                    "source_website": website.name,
                                    "is_rfp": "contract" in keywords.lower()
                                    or "rfp" in keywords.lower(),
                                }
                            })

                        except Exception as e:
                            logger.error(f"Error parsing card on {website.name}: {e}")

                except Exception as e:
                    logger.error(f"Page navigation failed for {website.name}: {e}")
                    break

        from .models import Job, ScraperExecutionLog
        from django.core.files.base import ContentFile
        from datetime import datetime

        # Save jobs outside event loop to avoid SynchronousOnlyOperation
        saved_jobs = []
        for job_data in all_new_jobs:
            job, created = Job.objects.update_or_create(
                source_url=job_data["source_url"],
                defaults=job_data["defaults"],
            )
            if created:
                saved_jobs.append(job)

        log = ScraperExecutionLog.objects.create(
            website=website,
            scraper_type='playwright',
            jobs_found=len(saved_jobs),
            error_message=error_msg,
        )
        
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        if screenshot_bytes:
            log.screenshot.save(f"{website.name}_error_{timestamp_str}.png", ContentFile(screenshot_bytes), save=True)
        if html_content:
            log.html_dump.save(f"{website.name}_error_{timestamp_str}.html", ContentFile(html_content.encode('utf-8')), save=True)

        return saved_jobs

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
