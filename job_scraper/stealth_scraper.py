import logging
import random
import time
import uuid
from datetime import datetime

from django.core.files.base import ContentFile

from bs4 import BeautifulSoup
from seleniumbase import SB

from .anti_bot import (
    classify_anti_bot_response,
    clear_block_state,
    compute_selector_coverage,
    jitter_sleep,
    record_block_event,
    summarize_selector_coverage,
)
from .models import CustomWebsite, Job, ScraperExecutionLog
from .utils import parse_location_components

logger = logging.getLogger(__name__)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


class StealthScraper:
    """
    A generic stealth scraper using SeleniumBase UC mode.
    """

    def __init__(self, headless=True):
        self.headless = headless

    def scrape(
        self, website: CustomWebsite, keywords: str, location: str, max_pages: int = 1
    ):
        """
        Generic scrape method that uses a CustomWebsite object's selectors.
        """
        keywords = (keywords or "").strip()
        location = (location or "").strip()
        run_id = uuid.uuid4().hex[:8]
        started_at = time.monotonic()

        logger.info(
            "stealth_scrape_start run_id=%s website_id=%s website=%s max_pages=%s",
            run_id,
            website.id,
            website.name,
            max_pages,
        )

        all_new_jobs = []
        error_msg = ""
        screenshot_bytes = None
        html_content = ""
        detail_fetch_count = 0
        detail_fetch_limit = 3
        detail_fetch_disabled = False
        detail_fetch_session_failures = 0
        selector_metrics = ""
        card_parse_failures = 0

        try:
            with self._session() as driver:
                for page_num in range(1, max_pages + 1):
                    url = website.search_url.format(
                        keywords=keywords, location=location, page=page_num
                    )
                    try:
                        jitter_sleep(1.5, 3.2)
                        logger.info(
                            "stealth_page_start run_id=%s website_id=%s page=%s url=%s",
                            run_id,
                            website.id,
                            page_num,
                            url,
                        )

                        self._open_url(driver, url)

                        jitter_sleep(3.0, 5.5)
                        # self._simulate_browse(driver)

                        try:
                            self._solve_captcha(driver)
                            logger.info(
                                "captcha_solver_attempted run_id=%s website_id=%s page=%s",
                                run_id,
                                website.id,
                                page_num,
                            )
                        except Exception as captcha_err:
                            logger.warning(
                                "captcha_solver_failed run_id=%s website_id=%s error=%s",
                                run_id,
                                website.id,
                                str(captcha_err),
                            )

                        try:
                            # Wait for the primary selector to ensure page loaded
                            self._wait_for_selector(
                                driver, website.job_list_selector, 20
                            )
                        except Exception:
                            logger.warning(
                                "selector_timeout run_id=%s website_id=%s website=%s selector=%s",
                                run_id,
                                website.id,
                                website.name,
                                website.job_list_selector,
                            )
                            error_msg = "Timeout waiting for primary selector. Possible CAPTCHA wall."
                            try:
                                html_content = self._get_page_source(driver)
                                screenshot_bytes = self._get_screenshot_png(driver)
                            except Exception:
                                logger.debug(
                                    "artifact_capture_failed run_id=%s website_id=%s",
                                    run_id,
                                    website.id,
                                    exc_info=True,
                                )
                            break

                        html_content = self._get_page_source(driver)
                        soup = BeautifulSoup(html_content, "html.parser")
                        job_elements = soup.select(website.job_list_selector)
                        coverage = compute_selector_coverage(
                            job_elements,
                            {
                                "title": website.title_selector,
                                "company": website.company_selector,
                                "location": website.location_selector,
                                "job_link": website.job_link_selector,
                                "salary": website.salary_selector,
                                "date": website.date_selector,
                            },
                        )
                        selector_metrics = summarize_selector_coverage(coverage)
                        anti_bot_result = classify_anti_bot_response(
                            html_content=html_content,
                            card_count=len(job_elements),
                        )
                        if anti_bot_result["blocked"]:
                            outcome = record_block_event(website.id)
                            logger.error(
                                "anti_bot_detected run_id=%s website_id=%s website=%s reason=%s failures=%s",
                                run_id,
                                website.id,
                                website.name,
                                anti_bot_result["reason"],
                                outcome["failures"],
                            )
                            error_msg = (
                                "Anti-bot challenge detected. "
                                f"{anti_bot_result['reason']} failures={outcome['failures']}"
                            )
                            try:
                                screenshot_bytes = self._get_screenshot_png(driver)
                            except Exception:
                                logger.debug(
                                    "artifact_capture_failed run_id=%s website_id=%s",
                                    run_id,
                                    website.id,
                                    exc_info=True,
                                )
                            break

                        clear_block_state(website.id)
                        logger.info(
                            "stealth_page_cards_found run_id=%s website_id=%s page=%s cards=%s selector_metrics=%s",
                            run_id,
                            website.id,
                            page_num,
                            len(job_elements),
                            selector_metrics,
                        )

                        for element in job_elements:
                            try:
                                title = ""
                                if website.title_selector:
                                    title_elem = element.select_one(
                                        website.title_selector
                                    )
                                    title = (
                                        title_elem.get("title")
                                        or title_elem.get_text(strip=True)
                                        if title_elem
                                        else ""
                                    )

                                company = ""
                                if website.company_selector:
                                    company_elem = element.select_one(
                                        website.company_selector
                                    )
                                    company = (
                                        company_elem.get_text(strip=True)
                                        if company_elem
                                        else ""
                                    )

                                loc_text = ""
                                if website.location_selector:
                                    location_elem = element.select_one(
                                        website.location_selector
                                    )
                                    loc_text = (
                                        location_elem.get_text(strip=True)
                                        if location_elem
                                        else ""
                                    )

                                job_url = ""
                                if website.job_link_selector:
                                    link_elem = element.select_one(
                                        website.job_link_selector
                                    )
                                    if link_elem and link_elem.get("href"):
                                        from urllib.parse import urljoin

                                        job_url = urljoin(
                                            website.base_url, link_elem.get("href")
                                        )

                                if not job_url or not title:
                                    continue

                                salary = ""
                                if website.salary_selector:
                                    salary_elem = element.select_one(
                                        website.salary_selector
                                    )
                                    salary = (
                                        salary_elem.get_text(strip=True)
                                        if salary_elem
                                        else ""
                                    )

                                description = ""
                                requirements = ""

                                if (
                                    job_url
                                    and website.description_selector
                                    and detail_fetch_count < detail_fetch_limit
                                    and not detail_fetch_disabled
                                ):
                                    if (
                                        not Job.objects.filter(source_url=job_url)
                                        .exclude(description="")
                                        .exists()
                                    ):
                                        logger.info(
                                            f"Fetching description for {job_url}"
                                        )
                                        jitter_sleep(0.8, 1.8)
                                        try:
                                            description = (
                                                self._get_description_selenium(
                                                    driver,
                                                    job_url,
                                                    website.description_selector,
                                                )
                                            )
                                            detail_fetch_count += 1
                                        except Exception as exc:
                                            if not self._is_invalid_session_error(exc):
                                                raise
                                            detail_fetch_disabled = True
                                            detail_fetch_session_failures += 1
                                            logger.warning(
                                                "description_fetch_disabled_invalid_session run_id=%s website_id=%s website=%s job_url=%s",
                                                run_id,
                                                website.id,
                                                website.name,
                                                job_url,
                                            )

                                job_data = {
                                    "title": title.strip(),
                                    "company": company.strip(),
                                    "location": loc_text.strip(),
                                    "job_url": job_url,
                                    "salary": salary,
                                    "description": description,
                                }

                                job_data = self._enrich_job_data(
                                    job_data, description, keywords
                                )

                                all_new_jobs.append(
                                    {
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
                                            "experience_level": job_data.get(
                                                "experience_level", ""
                                            ),
                                            "industry": job_data.get("industry", ""),
                                            "description": job_data.get(
                                                "description", ""
                                            ),
                                            "requirements": job_data.get(
                                                "requirements", ""
                                            ),
                                            "source_website": website.name,
                                            "is_rfp": "contract" in keywords.lower()
                                            or "rfp" in keywords.lower(),
                                        },
                                    }
                                )

                            except Exception:
                                card_parse_failures += 1
                                logger.exception(
                                    "stealth_card_parse_failed run_id=%s website_id=%s website=%s",
                                    run_id,
                                    website.id,
                                    website.name,
                                )

                    except Exception:
                        logger.exception(
                            "stealth_page_failed run_id=%s website_id=%s website=%s page=%s",
                            run_id,
                            website.id,
                            website.name,
                            page_num,
                        )
                        break
        except Exception as e:
            logger.exception(
                "stealth_driver_failed run_id=%s website_id=%s website=%s",
                run_id,
                website.id,
                website.name,
            )
            error_msg = f"Driver Initialization/Execution Failed: {e}"

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
            if card_parse_failures:
                error_msg = f"Parsed cards but failed to extract/save {card_parse_failures} cards."
            else:
                error_msg = "No jobs found. CSS selectors may be outdated or the site is blocking silently."

        log = ScraperExecutionLog.objects.create(
            website=website,
            scraper_type="seleniumbase",
            jobs_found=len(all_new_jobs),
            error_message=error_msg,
        )

        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        if screenshot_bytes:
            log.screenshot.save(
                f"{website.name}_error_{timestamp_str}.png",
                ContentFile(screenshot_bytes),
                save=True,
            )
        if html_content:
            log.html_dump.save(
                f"{website.name}_error_{timestamp_str}.html",
                ContentFile(html_content.encode("utf-8")),
                save=True,
            )

        logger.info(
            "stealth_scrape_done run_id=%s website_id=%s website=%s jobs_seen=%s jobs_new=%s duration_ms=%s has_error=%s selector_metrics=%s detail_fetches=%s detail_fetch_disabled=%s detail_fetch_session_failures=%s card_parse_failures=%s",
            run_id,
            website.id,
            website.name,
            len(all_new_jobs),
            len(saved_jobs),
            int((time.monotonic() - started_at) * 1000),
            bool(error_msg),
            selector_metrics or "n/a",
            detail_fetch_count,
            detail_fetch_disabled,
            detail_fetch_session_failures,
            card_parse_failures,
        )

        return saved_jobs

    def _simulate_browse(self, driver):
        """Introduce small browse-like pauses and scrolling before extraction."""
        try:
            driver.execute_script(
                "window.scrollTo(0, Math.floor(document.body.scrollHeight * 0.2));"
            )
            jitter_sleep(0.4, 1.0)
            driver.execute_script(
                "window.scrollTo(0, Math.floor(document.body.scrollHeight * 0.45));"
            )
            jitter_sleep(0.5, 1.1)
            driver.execute_script("window.scrollTo(0, 0);")
        except Exception:
            logger.debug("stealth_browse_simulation_failed", exc_info=True)

    def _session(self):
        width = random.randint(1200, 1920)
        height = random.randint(800, 1080)
        return SB(
            browser="chrome",
            headless2=self.headless,
            uc=True,
            uc_subprocess=True,
            agent=random.choice(USER_AGENTS),
            locale_code="en-US",
            window_size=f"{width},{height}",
            chromium_arg="--disable-blink-features=AutomationControlled,--disable-dev-shm-usage",
            test=True,
        )

    def _open_url(self, driver, url):
        # Using uc_open_with_reconnect which is the recommended way to bypass Cloudflare Turnstile
        driver.uc_open_with_reconnect(url, reconnect_time=5)
        # driver.sleep(2)
        # driver.solve_captcha_if_detected()
        # driver.open(url)

    def _solve_captcha(self, driver):
        try:
            # Try SeleniumBase's undetected GUI clicker for Cloudflare
            driver.uc_gui_click_captcha()
        except Exception:
            # Fallback to standard solve_captcha
            driver.solve_captcha()

    def _wait_for_selector(self, driver, selector, timeout):
        driver.wait_for_element_present(selector, by="css selector", timeout=timeout)

    def _get_page_source(self, driver):
        return driver.get_page_source()

    def _get_screenshot_png(self, driver):
        return driver.driver.get_screenshot_as_png()

    def _open_new_tab(self, driver):
        driver.open_new_tab(switch_to=True)

    def _switch_to_newest_window(self, driver):
        driver.switch_to_newest_window()

    def _switch_to_default_window(self, driver):
        driver.switch_to_default_window()

    def _get_description_selenium(self, driver, job_url, selector):
        """Fetch job description from a detail URL using SeleniumBase driver."""
        try:
            # We open in a new tab to avoid losing search state
            self._open_new_tab(driver)
            self._switch_to_newest_window(driver)
            self._open_url(driver, job_url)

            jitter_sleep(2.0, 4.0)

            # Wait for selector
            try:
                self._wait_for_selector(driver, selector, 10)
            except Exception:
                logger.debug(
                    "description_selector_wait_timeout selector=%s job_url=%s",
                    selector,
                    job_url,
                    exc_info=True,
                )

            soup = BeautifulSoup(self._get_page_source(driver), "html.parser")
            desc_elem = soup.select_one(selector)

            text = ""
            if desc_elem:
                # Try to keep some formatting
                for br in desc_elem.find_all("br"):
                    br.replace_with("\n")
                for p in desc_elem.find_all("p"):
                    p.append("\n")
                text = desc_elem.get_text()

            driver.driver.close()
            self._switch_to_default_window(driver)
            return text.strip()
        except Exception as exc:
            logger.exception("description_fetch_failed job_url=%s", job_url)
            try:
                if len(driver.driver.window_handles) > 1:
                    driver.driver.close()
                    self._switch_to_default_window(driver)
            except Exception:
                logger.debug(
                    "description_tab_cleanup_failed job_url=%s",
                    job_url,
                    exc_info=True,
                )
            if self._is_invalid_session_error(exc):
                raise
            return ""

    def _is_invalid_session_error(self, exc):
        return exc.__class__.__name__ == "InvalidSessionIdException" or (
            "invalid session id" in str(exc).lower()
        )

    def _enrich_job_data(self, job_data: dict, description: str, keywords: str) -> dict:
        """Apply heuristic parsing to fill in missing fields."""
        geo = parse_location_components(job_data.get("location", ""))
        city = geo["city"]
        country = geo["country"]
        continent = geo["continent"]

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
            re.IGNORECASE,
        )
        match = salary_pattern.search(description)
        if match:
            return match.group(1)
        alt_pattern = re.compile(
            r"((?:€|£)[\d,]+(?:\.\d{2})?(?:\s*(?:-|to)\s*(?:€|£)[\d,]+(?:\.\d{2})?)?(?:\s*(?:a|per|/)\s*(?:year|yr|month|mo|hour|hr|week|wk|annually|k))?)",
            re.IGNORECASE,
        )
        alt_match = alt_pattern.search(description)
        if alt_match:
            return alt_match.group(1)
        return ""

    def _extract_requirements(self, description: str) -> str:
        import re

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
            if any(
                k in line_lower
                for k in ["benefits", "what we offer", "perks", "equal opportunity"]
            ):
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
            if any(keyword in description_lower for keyword in keywords):
                return level.title()
        return "Mid-level"

    def _extract_industry(self, description: str) -> str:
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
            "software",
            "logistics",
        ]
        description_lower = description.lower()
        for industry in industries:
            if industry in description_lower:
                return industry.title()
        return "Technology"
