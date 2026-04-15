import asyncio
import random
import time
import logging
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from .models import Job
from .utils import get_continent_from_country

logger = logging.getLogger(__name__)

class StealthScraper:
    """
    A modern scraper for Indeed using Playwright and stealth plugins.
    """
    def __init__(self, headless=True):
        self.headless = headless

    def _get_search_url(self, keywords, location, job_type="contract"):
        base_url = "https://www.indeed.com/jobs"
        import urllib.parse
        params = {
            'q': keywords,
            'l': location,
            'jt': job_type,
            'fromage': 1, # Last 24 hours
        }
        return f"{base_url}?{urllib.parse.urlencode(params)}"

    def scrape_indeed(self, keywords, location, max_pages=1):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            Stealth().apply_stealth_sync(page)

            search_url = self._get_search_url(keywords, location)
            logger.info(f"Navigating to {search_url}")
            
            try:
                # Use a slower, more human-like wait
                page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
                
                # Randomized sleep to mimic human reading
                time.sleep(random.uniform(3, 7))
                
                # Scroll a bit to trigger lazy loading
                page.evaluate("window.scrollTo(0, 500)")
                time.sleep(1)

                # Wait for job cards with a fallback
                try:
                    page.wait_for_selector('[data-jk]', timeout=30000)
                except Exception:
                    logger.warning("Job cards selector timeout, checking page content...")
                
                # Check for "reCAPTCHA" or other blocks
                if "hcaptcha" in page.content().lower() or "recaptcha" in page.content().lower():
                    logger.error("Detected a CAPTCHA. Need to handle or use proxies.")
                    return []

                job_elements = page.query_selector_all('[data-jk]')
                logger.info(f"Found {len(job_elements)} job cards.")

                jobs_data = []
                for element in job_elements:
                    try:
                        job_id = element.get_attribute('data-jk')
                        title_elem = element.query_selector('h2.jobTitle span[title]')
                        title = title_elem.get_attribute('title') if title_elem else ""
                        
                        company_elem = element.query_selector('[data-testid="company-name"]')
                        company = company_elem.inner_text() if company_elem else ""
                        
                        location_elem = element.query_selector('[data-testid="text-location"]')
                        loc_text = location_elem.inner_text() if location_elem else ""
                        
                        # Build a detail URL
                        job_url = f"https://www.indeed.com/viewjob?jk={job_id}"
                        
                        jobs_data.append({
                            'id': job_id,
                            'title': title,
                            'company': company,
                            'location': loc_text,
                            'source_url': job_url,
                            'source_website': 'Indeed',
                            'is_rfp': 'contract' in keywords.lower() or 'rfp' in keywords.lower()
                        })
                    except Exception as e:
                        logger.error(f"Error parsing job card: {e}")
                
                # Deduplicate and save
                new_jobs = []
                for data in jobs_data:
                    city = ""
                    country = ""
                    if "," in data['location']:
                        parts = data['location'].split(",")
                        city = parts[0].strip()
                        country = parts[1].strip()
                    else:
                        country = data['location'].strip()

                    continent = get_continent_from_country(country)

                    job, created = Job.objects.update_or_create(
                        source_url=data['source_url'],
                        defaults={
                            'title': data['title'],
                            'company': data['company'],
                            'location': data['location'],
                            'city': city,
                            'country': country,
                            'continent': continent,
                            'source_website': data['source_website'],
                            'is_rfp': data['is_rfp'],
                            # We'll fill description and summary later to keep it fast
                        }
                    )
                    if created:
                        new_jobs.append(job)
                
                return new_jobs

            except Exception as e:
                logger.error(f"Scrape failed: {e}")
                # Optional: screenshot for debugging in non-docker environments
                # page.screenshot(path="scrape_fail.png")
                return []
            finally:
                browser.close()

    def _get_description(self, page, job_url):
        """Fetch job description from a specific job URL."""
        try:
            page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(random.uniform(1, 3))
            desc_elem = page.query_selector('#jobDescriptionText')
            return desc_elem.inner_text() if desc_elem else ""
        except Exception as e:
            logger.error(f"Failed to get description for {job_url}: {e}")
            return ""
