import logging
import random
import re
import time
import uuid
from contextlib import contextmanager
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
    """Generic stealth scraper powered by SeleniumBase UC mode."""

    def __init__(self, headless=True, run_id=None):
        self.headless = headless
        self._run_id = run_id
        self._driver = None
        self._session_manager = self._build_session_manager()

    def scrape(
        self, website: CustomWebsite, keywords: str, location: str, max_pages: int = 1
    ):
        keywords = (keywords or "").strip()
        location = (location or "").strip()
        started_at = time.monotonic()

        self._ensure_run_id()
        self._log_scrape_start(website, max_pages)

        state = {
            "all_new_jobs": [],
            "error_msg": "",
            "screenshot_bytes": None,
            "html_content": "",
            "detail_fetch_count": 0,
            "detail_fetch_limit": 3,
            "detail_fetch_disabled": False,
            "detail_fetch_session_failures": 0,
            "selector_metrics": "",
            "card_parse_failures": 0,
        }

        try:
            with self._driver_session() as driver:
                self._scrape_pages(
                    driver, website, keywords, location, max_pages, state
                )
        except Exception as exc:
            state["error_msg"] = f"Driver Initialization/Execution Failed: {exc}"
            logger.exception(
                "stealth_driver_failed run_id=%s website_id=%s website=%s",
                self._run_id,
                website.id,
                website.name,
            )

        saved_jobs = self._save_jobs(state["all_new_jobs"])
        state["error_msg"] = self._finalize_error_message(
            state["error_msg"],
            len(state["all_new_jobs"]),
            state["card_parse_failures"],
        )
        self._log_execution(website, state)
        self._log_scrape_done(website, started_at, saved_jobs, state)
        self._reset_run_state()
        return saved_jobs

    def _ensure_run_id(self):
        if not self._run_id:
            self._run_id = uuid.uuid4().hex[:8]

    def _log_scrape_start(self, website: CustomWebsite, max_pages: int):
        logger.info(
            "stealth_scrape_start run_id=%s website_id=%s website=%s max_pages=%s",
            self._run_id,
            website.id,
            website.name,
            max_pages,
        )

    @contextmanager
    def _driver_session(self):
        manager = self._session_manager or self._build_session_manager()
        with manager as driver:
            self._driver = driver
            try:
                yield driver
            finally:
                self._driver = None
                self._session_manager = self._build_session_manager()

    def _build_session_manager(self):
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

    def _scrape_pages(self, driver, website, keywords, location, max_pages, state):
        for page_num in range(1, max_pages + 1):
            should_continue = self._scrape_page(
                driver, website, keywords, location, page_num, state
            )
            if not should_continue:
                break

    def _scrape_page(self, driver, website, keywords, location, page_num, state):
        url = website.search_url.format(
            keywords=keywords, location=location, page=page_num
        )
        logger.info(
            "stealth_page_start run_id=%s website_id=%s page=%s url=%s",
            self._run_id,
            website.id,
            page_num,
            url,
        )

        try:
            jitter_sleep(1.5, 3.2)
            self._open_url(driver, url)
            jitter_sleep(3.0, 5.5)

            if not self._attempt_captcha_solver(driver, website, page_num, state):
                return False
            if not self._wait_for_primary_selector(driver, website, state):
                return False

            html_content = self._get_page_source(driver)
            state["html_content"] = html_content
            soup = BeautifulSoup(html_content, "html.parser")
            job_elements = soup.select(website.job_list_selector)

            state["selector_metrics"] = self._selector_metrics(website, job_elements)
            if self._handle_anti_bot(website, job_elements, html_content, state):
                return False

            logger.info(
                "stealth_page_cards_found run_id=%s website_id=%s page=%s cards=%s selector_metrics=%s",
                self._run_id,
                website.id,
                page_num,
                len(job_elements),
                state["selector_metrics"],
            )
            self._collect_jobs_from_page(driver, website, keywords, job_elements, state)
            return True
        except Exception:
            logger.exception(
                "stealth_page_failed run_id=%s website_id=%s website=%s page=%s",
                self._run_id,
                website.id,
                website.name,
                page_num,
            )
            return False

    def _attempt_captcha_solver(self, driver, website, page_num, state):
        anti_bot_result = self._challenge_state(driver)
        if not anti_bot_result["blocked"]:
            return True

        try:
            self._solve_captcha(driver)
            jitter_sleep(2.0, 4.0)
            anti_bot_result = self._challenge_state(driver)
            logger.info(
                "captcha_solver_attempted run_id=%s website_id=%s page=%s blocked_after_attempt=%s reason=%s",
                self._run_id,
                website.id,
                page_num,
                anti_bot_result["blocked"],
                anti_bot_result["reason"],
            )
            if anti_bot_result["blocked"]:
                self._record_challenge_failure(driver, website, state, anti_bot_result)
                return False
            return True
        except Exception as exc:
            logger.warning(
                "captcha_solver_failed run_id=%s website_id=%s error=%s",
                self._run_id,
                website.id,
                str(exc),
            )
            self._capture_artifacts(driver, website, state)
            state["error_msg"] = f"Captcha solver failed: {exc}"
            return False

    def _wait_for_primary_selector(self, driver, website, state):
        try:
            self._wait_for_selector(driver, website.job_list_selector, 20)
            return True
        except Exception:
            logger.warning(
                "selector_timeout run_id=%s website_id=%s website=%s selector=%s",
                self._run_id,
                website.id,
                website.name,
                website.job_list_selector,
            )
            state["error_msg"] = (
                "Timeout waiting for primary selector. Possible CAPTCHA wall."
            )
            self._capture_artifacts(driver, website, state)
            return False

    def _handle_anti_bot(self, website, job_elements, html_content, state):
        anti_bot_result = classify_anti_bot_response(
            html_content=html_content,
            card_count=len(job_elements),
        )
        if not anti_bot_result["blocked"]:
            clear_block_state(website.id)
            return False

        outcome = record_block_event(website.id)
        logger.error(
            "anti_bot_detected run_id=%s website_id=%s website=%s reason=%s failures=%s",
            self._run_id,
            website.id,
            website.name,
            anti_bot_result["reason"],
            outcome["failures"],
        )
        state["error_msg"] = (
            "Anti-bot challenge detected. "
            f"{anti_bot_result['reason']} failures={outcome['failures']}"
        )
        self._capture_artifacts(self._driver, website, state)
        return True

    def _record_challenge_failure(self, driver, website, state, anti_bot_result):
        outcome = record_block_event(website.id)
        logger.error(
            "captcha_challenge_persisted run_id=%s website_id=%s website=%s reason=%s failures=%s",
            self._run_id,
            website.id,
            website.name,
            anti_bot_result["reason"],
            outcome["failures"],
        )
        state["error_msg"] = (
            "Captcha challenge still present after solver attempt. "
            f"{anti_bot_result['reason']} failures={outcome['failures']}"
        )
        self._capture_artifacts(driver, website, state)

    def _challenge_state(self, driver):
        html_content = self._get_page_source(driver)
        return classify_anti_bot_response(html_content=html_content, card_count=0)

    def _capture_artifacts(self, driver, website, state):
        try:
            state["html_content"] = self._get_page_source(driver)
            state["screenshot_bytes"] = self._get_screenshot_png(driver)
        except Exception:
            logger.debug(
                "artifact_capture_failed run_id=%s website_id=%s",
                self._run_id,
                website.id,
                exc_info=True,
            )

    def _selector_metrics(self, website, job_elements):
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
        return summarize_selector_coverage(coverage)

    def _collect_jobs_from_page(self, driver, website, keywords, job_elements, state):
        for element in job_elements:
            job_entry = self._parse_job_element(
                driver, website, keywords, element, state
            )
            if job_entry is not None:
                state["all_new_jobs"].append(job_entry)

    def _parse_job_element(self, driver, website, keywords, element, state):
        try:
            title = self._select_text(
                element, website.title_selector, prefer_title=True
            )
            company = self._select_text(element, website.company_selector)
            loc_text = self._select_text(element, website.location_selector)
            job_url = self._select_url(element, website)
            salary = self._select_text(element, website.salary_selector)

            if not job_url or not title:
                return None

            description = self._maybe_fetch_description(
                driver, website, keywords, job_url, state
            )
            job_data = {
                "title": title.strip(),
                "company": company.strip(),
                "location": loc_text.strip(),
                "job_url": job_url,
                "salary": salary,
                "description": description,
            }
            job_data = self._enrich_job_data(job_data, description, keywords)
            return {
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
                    "is_rfp": "contract" in keywords.lower()
                    or "rfp" in keywords.lower(),
                },
            }
        except Exception:
            state["card_parse_failures"] += 1
            logger.exception(
                "stealth_card_parse_failed run_id=%s website_id=%s website=%s",
                self._run_id,
                website.id,
                website.name,
            )
            return None

    def _maybe_fetch_description(self, driver, website, keywords, job_url, state):
        if not website.description_selector:
            return ""
        if state["detail_fetch_count"] >= state["detail_fetch_limit"]:
            return ""
        if state["detail_fetch_disabled"]:
            return ""
        if Job.objects.filter(source_url=job_url).exclude(description="").exists():
            return ""

        logger.info("Fetching description for %s", job_url)
        jitter_sleep(0.8, 1.8)
        try:
            description = self._get_description_selenium(
                driver, job_url, website.description_selector
            )
            state["detail_fetch_count"] += 1
            return description
        except Exception as exc:
            if not self._is_invalid_session_error(exc):
                raise
            state["detail_fetch_disabled"] = True
            state["detail_fetch_session_failures"] += 1
            logger.warning(
                "description_fetch_disabled_invalid_session run_id=%s website_id=%s website=%s job_url=%s",
                self._run_id,
                website.id,
                website.name,
                job_url,
            )
            return ""

    def _save_jobs(self, job_entries):
        saved_jobs = []
        for job_entry in job_entries:
            job, created = Job.objects.update_or_create(
                source_url=job_entry["source_url"],
                defaults=job_entry["defaults"],
            )
            if created:
                saved_jobs.append(job)
        return saved_jobs

    def _finalize_error_message(self, error_msg, jobs_seen, card_parse_failures):
        if error_msg:
            return error_msg
        if jobs_seen == 0 and card_parse_failures:
            return (
                f"Parsed cards but failed to extract/save {card_parse_failures} cards."
            )
        if jobs_seen == 0:
            return "No jobs found. CSS selectors may be outdated or the site is blocking silently."
        return ""

    def _log_execution(self, website: CustomWebsite, state):
        log = ScraperExecutionLog.objects.create(
            website=website,
            scraper_type="seleniumbase",
            jobs_found=len(state["all_new_jobs"]),
            error_message=state["error_msg"],
        )
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        if state["screenshot_bytes"]:
            log.screenshot.save(
                f"{website.name}_error_{timestamp_str}.png",
                ContentFile(state["screenshot_bytes"]),
                save=True,
            )
        if state["html_content"]:
            log.html_dump.save(
                f"{website.name}_error_{timestamp_str}.html",
                ContentFile(state["html_content"].encode("utf-8")),
                save=True,
            )

    def _log_scrape_done(self, website, started_at, saved_jobs, state):
        logger.info(
            "stealth_scrape_done run_id=%s website_id=%s website=%s jobs_seen=%s jobs_new=%s duration_ms=%s has_error=%s selector_metrics=%s detail_fetches=%s detail_fetch_disabled=%s detail_fetch_session_failures=%s card_parse_failures=%s",
            self._run_id,
            website.id,
            website.name,
            len(state["all_new_jobs"]),
            len(saved_jobs),
            int((time.monotonic() - started_at) * 1000),
            bool(state["error_msg"]),
            state["selector_metrics"] or "n/a",
            state["detail_fetch_count"],
            state["detail_fetch_disabled"],
            state["detail_fetch_session_failures"],
            state["card_parse_failures"],
        )

    def _reset_run_state(self):
        self._run_id = None
        self._driver = None
        self._session_manager = self._build_session_manager()

    def _select_text(self, element, selector, prefer_title=False):
        if not selector:
            return ""
        selected = element.select_one(selector)
        if not selected:
            return ""
        if prefer_title:
            return selected.get("title") or selected.get_text(strip=True)
        return selected.get_text(strip=True)

    def _select_url(self, element, website):
        if not website.job_link_selector:
            return ""
        link_elem = element.select_one(website.job_link_selector)
        if not link_elem or not link_elem.get("href"):
            return ""
        from urllib.parse import urljoin

        return urljoin(website.base_url, link_elem.get("href"))

    def _simulate_browse(self, driver):
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

    def _open_url(self, driver, url):
        driver.activate_cdp_mode(url)

    def _solve_captcha(self, driver):
        try:
            driver.uc_gui_click_captcha()
        except Exception:
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
        try:
            self._open_new_tab(driver)
            self._switch_to_newest_window(driver)
            self._open_url(driver, job_url)
            jitter_sleep(2.0, 4.0)

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
        geo = parse_location_components(job_data.get("location", ""))
        job_data["city"] = geo["city"]
        job_data["country"] = geo["country"]
        job_data["continent"] = geo["continent"]

        if not job_data.get("requirements") and description:
            job_data["requirements"] = self._extract_requirements(description)
        if not job_data.get("salary") and description:
            job_data["salary"] = self._extract_salary_fallback(description)

        job_data["job_type"] = self._extract_job_type(description)
        job_data["experience_level"] = self._extract_experience_level(description)
        job_data["industry"] = self._extract_industry(description)
        return job_data

    def _extract_salary_fallback(self, description: str) -> str:
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
