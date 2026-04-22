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

                            salary = ""
                            if website.salary_selector:
                                salary_elem = element.select_one(website.salary_selector)
                                salary = salary_elem.get_text(strip=True) if salary_elem else ""

                            description = ""
                            requirements = ""
                            
                            # If we have a detail link and description selector, fetch details
                            # We only do this for new jobs to save time, or if requested
                            if job_url and website.description_selector:
                                # Check if job already exists with description
                                if not Job.objects.filter(source_url=job_url).exclude(description="").exists():
                                    logger.info(f"Fetching description for {job_url}")
                                    description = self._get_description_selenium(driver, job_url, website.description_selector)
                            
                            job_data = {
                                "title": title.strip(),
                                "company": company.strip(),
                                "location": loc_text.strip(),
                                "job_url": job_url,
                                "salary": salary,
                                "description": description,
                            }
                            
                            # Apply the same heuristic enrichment logic
                            job_data = self._enrich_job_data(job_data, description, keywords)

                            all_new_jobs.append({
                                "source_url": job_url,
                                "defaults": {
                                    "title": job_data.get("title", ""),
                                    "company": job_data.get("company", ""),
                                    "location": job_data.get("location", ""),
                                    "city": job_data.get("city", ""),
                                    "country": job_data.get("country", ""),
                                    "continent": job_data.get("continent", ""),
                                    "salary": job_data.get("salary", ""),
                                    "job_type": job_data.get("job_type", ""),
                                    "experience_level": job_data.get("experience_level", ""),
                                    "industry": job_data.get("industry", ""),
                                    "description": job_data.get("description", ""),
                                    "requirements": job_data.get("requirements", ""),
                                    "source_website": website.name,
                                    "is_rfp": "contract" in keywords.lower() or "rfp" in keywords.lower(),
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

        # Check for silent failures
        if len(all_new_jobs) == 0 and not error_msg:
            error_msg = "No jobs found. CSS selectors may be outdated or the site is blocking silently."

        log = ScraperExecutionLog.objects.create(
            website=website,
            scraper_type='playwright',
            jobs_found=len(all_new_jobs),
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

    def _get_description_selenium(self, driver, job_url, selector):
        """Fetch job description from a specific job URL using Selenium."""
        try:
            # We open in a new tab to avoid losing search state
            driver.execute_script("window.open('');")
            driver.switch_to.window(driver.window_handles[-1])
            driver.get(job_url)
            
            time.sleep(random.uniform(2, 4))
            
            # Wait for selector
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
            except:
                pass

            soup = BeautifulSoup(driver.page_source, 'html.parser')
            desc_elem = soup.select_one(selector)
            
            text = ""
            if desc_elem:
                # Try to keep some formatting
                for br in desc_elem.find_all("br"):
                    br.replace_with("\n")
                for p in desc_elem.find_all("p"):
                    p.append("\n")
                text = desc_elem.get_text()
                
            driver.close()
            driver.switch_to.window(driver.window_handles[0])
            return text.strip()
        except Exception as e:
            logger.error(f"Failed to get description for {job_url}: {e}")
            try:
                if len(driver.window_handles) > 1:
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])
            except:
                pass
            return ""

    def _enrich_job_data(self, job_data: dict, description: str, keywords: str) -> dict:
        """Apply heuristic parsing to fill in missing fields."""
        loc_text = job_data.get("location", "")
        city = ""
        country = ""
        if loc_text:
            if "," in loc_text:
                parts = loc_text.split(",")
                city = parts[0].strip()
                country = parts[-1].strip()
            else:
                country = loc_text.strip()
        
        from .utils import get_continent_from_country
        continent = get_continent_from_country(country) if country else ""
        
        job_data["city"] = city
        job_data["country"] = country
        job_data["continent"] = continent

        if not job_data.get("requirements") and description:
            job_data["requirements"] = self._extract_requirements(description)
        if not job_data.get("salary") and description:
            job_data["salary"] = self._extract_salary_fallback(description)
            
        job_data["job_type"] = self._extract_job_type(description)
        job_data["experience_level"] = self._extract_experience_level(description)
        job_data["industry"] = self._extract_industry(description)
        
        return job_data

    def _extract_salary_fallback(self, description: str) -> str:
        import re
        salary_pattern = re.compile(
            r"(\$[\d,]+(?:\.\d{2})?(?:\s*(?:-|to)\s*\$[\d,]+(?:\.\d{2})?)?(?:\s*(?:a|per|/)\s*(?:year|yr|month|mo|hour|hr|week|wk|annually|k))?)",
            re.IGNORECASE
        )
        match = salary_pattern.search(description)
        if match: return match.group(1)
        alt_pattern = re.compile(
            r"((?:€|£)[\d,]+(?:\.\d{2})?(?:\s*(?:-|to)\s*(?:€|£)[\d,]+(?:\.\d{2})?)?(?:\s*(?:a|per|/)\s*(?:year|yr|month|mo|hour|hr|week|wk|annually|k))?)",
            re.IGNORECASE
        )
        alt_match = alt_pattern.search(description)
        if alt_match: return alt_match.group(1)
        return ""

    def _extract_requirements(self, description: str) -> str:
        import re
        requirements_keywords = [
            "requirements", "qualifications", "skills", "experience",
            "must have", "should have", "preferred", "minimum",
        ]
        lines = description.split("\n")
        requirements_lines = []
        in_requirements = False
        for line in lines:
            line_lower = line.lower()
            if any(k in line_lower for k in ["benefits", "what we offer", "perks", "equal opportunity"]):
                in_requirements = False
            if any(keyword in line_lower for keyword in requirements_keywords):
                in_requirements = True
                continue
            if in_requirements and line.strip():
                if line.strip().startswith(("•", "-", "*", "·", "✓", "o ")):
                    requirements_lines.append(line.strip())
                elif re.match(r"^\d+\.", line.strip()):
                    requirements_lines.append(line.strip())
        return "\n".join(requirements_lines) if requirements_lines else ""

    def _extract_job_type(self, description: str) -> str:
        job_types = ["full-time", "part-time", "contract", "temporary", "internship", "freelance"]
        description_lower = description.lower()
        for job_type in job_types:
            if job_type in description_lower: return job_type.title()
        return "Full-time"

    def _extract_experience_level(self, description: str) -> str:
        levels = {
            "entry-level": ["entry level", "junior", "0-2 years", "1-2 years"],
            "mid-level": ["mid level", "intermediate", "3-5 years", "2-5 years"],
            "senior": ["senior", "lead", "5+ years", "7+ years", "experienced"],
            "executive": ["executive", "director", "manager", "head of", "chief"],
        }
        description_lower = description.lower()
        for level, keywords in levels.items():
            if any(keyword in description_lower for keyword in keywords): return level.title()
        return "Mid-level"

    def _extract_industry(self, description: str) -> str:
        industries = [
            "technology", "healthcare", "finance", "education", "retail",
            "manufacturing", "consulting", "marketing", "sales", "engineering",
            "software", "logistics"
        ]
        description_lower = description.lower()
        for industry in industries:
            if industry in description_lower: return industry.title()
        return "Technology"
