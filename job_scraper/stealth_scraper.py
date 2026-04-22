import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
import random
import logging
from datetime import datetime
from django.core.files.base import ContentFile
from .models import CustomWebsite, Job, ScraperExecutionLog
from .utils import get_continent_from_country

logger = logging.getLogger(__name__)

class StealthScraper:
    """
    A generic stealth scraper using undetected_chromedriver to bypass bot protection.
    """

    def __init__(self, headless=True):
        self.headless = headless

    def scrape(
        self, website: CustomWebsite, keywords: str, location: str, max_pages: int = 1
    ):
        """
        Generic scrape method that uses a CustomWebsite object's selectors.
        """
        options = uc.ChromeOptions()
        if self.headless:
            options.add_argument('--headless')
        
        # Add random viewport to look more authentic
        options.add_argument(f"--window-size={random.randint(1200, 1920)},{random.randint(800, 1080)}")
        
        driver = None
        all_new_jobs = []
        error_msg = ""
        screenshot_bytes = None
        html_content = ""

        try:
            driver = uc.Chrome(options=options)
            
            for page_num in range(1, max_pages + 1):
                url = website.search_url.format(
                    keywords=keywords, location=location, page=page_num
                )
                try:
                    logger.info(f"Navigating to {url}")
                    driver.get(url)

                    time.sleep(random.uniform(3, 6))

                    try:
                        # Wait for the primary selector to ensure page loaded
                        WebDriverWait(driver, 20).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, website.job_list_selector))
                        )
                    except Exception as e:
                        logger.warning(f"Timeout waiting for {website.job_list_selector}")
                        error_msg = "Timeout waiting for primary selector. Possible CAPTCHA wall."
                        try:
                            html_content = driver.page_source
                            screenshot_bytes = driver.get_screenshot_as_png()
                        except:
                            pass
                        break

                    # Check for CAPTCHA manually
                    content_lower = driver.page_source.lower()
                    if any(x in content_lower for x in ["recaptcha", "hcaptcha", "cloudflare"]):
                        logger.error(f"Anti-bot detected on {website.name}")
                        error_msg = "Anti-bot (Cloudflare/CAPTCHA) detected."
                        try:
                            html_content = driver.page_source
                            screenshot_bytes = driver.get_screenshot_as_png()
                        except:
                            pass
                        break

                    # Parse with BeautifulSoup
                    soup = BeautifulSoup(driver.page_source, 'html.parser')
                    job_elements = soup.select(website.job_list_selector)
                    logger.info(f"Found {len(job_elements)} job cards on {website.name}")

                    for element in job_elements:
                        try:
                            title = ""
                            if website.title_selector:
                                title_elem = element.select_one(website.title_selector)
                                title = title_elem.get("title") or title_elem.get_text(strip=True) if title_elem else ""

                            company = ""
                            if website.company_selector:
                                company_elem = element.select_one(website.company_selector)
                                company = company_elem.get_text(strip=True) if company_elem else ""

                            loc_text = ""
                            if website.location_selector:
                                location_elem = element.select_one(website.location_selector)
                                loc_text = location_elem.get_text(strip=True) if location_elem else ""

                            job_url = ""
                            if website.job_link_selector:
                                link_elem = element.select_one(website.job_link_selector)
                                if link_elem and link_elem.get("href"):
                                    from urllib.parse import urljoin
                                    job_url = urljoin(website.base_url, link_elem.get("href"))

                            if not job_url or not title:
                                continue

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
        except Exception as e:
            logger.error(f"Failed to initialize or run undetected_chromedriver: {e}")
            error_msg = f"Driver Initialization/Execution Failed: {e}"
        finally:
            if driver:
                driver.quit()

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
