from unittest.mock import Mock, patch

from django.test import TestCase

from bs4 import BeautifulSoup

from job_scraper.scrapers import EnhancedJobScraper
from job_scraper.models import CustomWebsite, Job


class ModelTestCase(TestCase):
    def test_job_model_sanity(self):
        job = Job.objects.create(
            title="Senior Python Developer",
            company="Tech Company",
            location="Remote",
            description="Role description",
            source_website="linkedin",
        )

        self.assertEqual(job.title, "Senior Python Developer")
        self.assertIn("Tech Company", str(job))

    def test_custom_website_model_sanity(self):
        website = CustomWebsite.objects.create(
            name="Custom Job Board",
            base_url="https://customjobs.com",
            search_url="https://customjobs.com/search?q={keywords}&l={location}&page={page}",
            job_list_selector=".job",
            title_selector=".title",
            company_selector=".company",
            location_selector=".location",
            job_link_selector=".link",
        )

        self.assertEqual(website.name, "Custom Job Board")
        self.assertTrue(website.is_active)


class JobSearchViewTests(TestCase):
    def setUp(self):
        CustomWebsite.objects.create(
            name="RemoteBoard",
            base_url="https://remoteboard.example",
            search_url="https://remoteboard.example/jobs?q={keywords}&l={location}&page={page}",
            job_list_selector=".job",
            title_selector=".title",
            company_selector=".company",
            location_selector=".location",
            job_link_selector=".link",
        )

    @patch("job_scraper.views.EnhancedJobScraper")
    def test_job_search_uses_default_websites_when_none_selected(self, scraper_cls):
        scraper_cls.return_value.get_recent_jobs.return_value = []

        response = self.client.post("/", {"keywords": "python", "location": "us"})

        self.assertEqual(response.status_code, 200)
        scraper_cls.return_value.get_recent_jobs.assert_called_once_with(
            ["indeed", "linkedin"],
            "us",
            "python",
            max_pages=15,
        )

    @patch("job_scraper.views.EnhancedJobScraper")
    def test_job_search_post_and_pagination_are_session_backed(self, scraper_cls):
        scraped_jobs = [
            {
                "id": f"src-{i}",
                "title": f"Job {i}",
                "company": "Company",
                "location": "Remote",
                "source_website": "Indeed",
            }
            for i in range(1, 13)
        ]
        scraper_cls.return_value.get_recent_jobs.return_value = scraped_jobs

        first_page = self.client.post("/", {"keywords": "python", "location": "us"})
        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(len(first_page.context["results"].object_list), 10)
        self.assertEqual(first_page.context["results"].paginator.count, 12)

        second_page = self.client.get("/?page=2")
        self.assertEqual(second_page.status_code, 200)
        self.assertEqual(second_page.context["results"].number, 2)
        self.assertEqual(len(second_page.context["results"].object_list), 2)
        self.assertEqual(
            second_page.context["results"].object_list[0]["title"], "Job 11"
        )


class JobDetailViewTests(TestCase):
    def test_job_detail_returns_job_from_session(self):
        session = self.client.session
        session["scraped_jobs"] = [
            {
                "id": 1,
                "title": "Backend Engineer",
                "company": "Acme",
                "location": "Remote",
                "source_website": "LinkedIn",
            }
        ]
        session.save()

        response = self.client.get("/job/1/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["job"]["title"], "Backend Engineer")
        self.assertIsNone(response.context.get("error"))

    def test_job_detail_missing_session_job_returns_explicit_error(self):
        session = self.client.session
        session["scraped_jobs"] = [{"id": 1, "title": "Backend Engineer"}]
        session.save()

        response = self.client.get("/job/99/")

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["job"])
        self.assertIn("unavailable", response.context["error"].lower())


class EnhancedScraperCustomWebsiteTests(TestCase):
    def setUp(self):
        self.website = CustomWebsite.objects.create(
            name="MyBoard",
            base_url="https://example.com",
            search_url="https://example.com/search?q={keywords}&l={location}&page={page}",
            job_list_selector=".job",
            title_selector=".title",
            company_selector=".company",
            location_selector=".location",
            job_link_selector=".link",
            salary_selector=".salary",
            date_selector=".date",
        )
        self.scraper = EnhancedJobScraper()

    def test_parse_custom_card_uses_deterministic_id(self):
        html = """
        <div class="job">
          <span class="title">Python Engineer</span>
          <span class="company">Acme</span>
          <span class="location">Remote</span>
          <span class="salary">$100k</span>
          <span class="date">1 day ago</span>
          <a class="link" href="/jobs/123">Apply</a>
        </div>
        """
        card = BeautifulSoup(html, "html.parser").select_one(".job")

        job_data = self.scraper._parse_custom_card(
            card,
            self.website,
            page_number=2,
            card_number=3,
        )

        self.assertEqual(job_data["id"], f"custom-{self.website.pk}-2-3")
        self.assertEqual(job_data["job_url"], "https://example.com/jobs/123")

    @patch("job_scraper.enhanced_scrapers.time.sleep", return_value=None)
    def test_scrape_custom_website_is_case_insensitive(self, _sleep_mock):
        html = """
        <div class="job">
          <span class="title">Python Engineer</span>
          <span class="company">Acme</span>
          <span class="location">Remote</span>
          <a class="link" href="/jobs/123">Apply</a>
        </div>
        """

        response = Mock()
        response.content = html.encode("utf-8")
        response.raise_for_status = Mock()

        with patch.object(
            self.scraper.session, "get", return_value=response
        ) as get_mock:
            jobs = self.scraper._scrape_custom_website(
                website_name="myboard",
                country="us",
                keywords="python",
                max_pages=1,
            )

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["id"], f"custom-{self.website.pk}-1-1")
        get_mock.assert_called_once_with(
            "https://example.com/search?q=python&l=us&page=1",
            timeout=30,
        )
