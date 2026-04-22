from unittest.mock import Mock, patch

import requests
from django.test import TestCase
from django.urls import reverse

from job_scraper.api_scraper import ApiScraper
from job_scraper.models import CustomWebsite, Job, ScraperExecutionLog
from job_scraper.request_scraper import JobScraper


def create_custom_website(**overrides):
    data = {
        "name": "Custom Job Board",
        "base_url": "https://example.com",
        "search_url": "https://example.com/search?q={keywords}&l={location}&page={page}",
        "job_list_selector": ".job",
        "title_selector": ".title",
        "company_selector": ".company",
        "location_selector": ".location",
        "job_link_selector": ".link",
    }
    data.update(overrides)
    return CustomWebsite.objects.create(**data)


class ModelTests(TestCase):
    def test_job_model_sanity(self):
        job = Job.objects.create(
            title="Senior Python Developer",
            company="Tech Company",
            location="Remote",
            description="Role description",
            source_website="LinkedIn",
        )

        self.assertEqual(job.title, "Senior Python Developer")
        self.assertIn("Tech Company", str(job))

    def test_custom_website_model_sanity(self):
        website = create_custom_website(name="RemoteBoard")

        self.assertEqual(website.name, "RemoteBoard")
        self.assertTrue(website.is_active)


class DashboardViewTests(TestCase):
    def setUp(self):
        self.indeed = create_custom_website(name="Indeed")
        self.linkedin = create_custom_website(name="LinkedIn")

        Job.objects.create(
            title="Backend Engineer",
            company="Acme",
            location="Remote",
            description="Python and Django",
            source_website="Indeed",
        )
        Job.objects.create(
            title="Data Engineer",
            company="Beta",
            location="Berlin",
            description="Spark and SQL",
            source_website="LinkedIn",
        )

    def test_dashboard_filters_by_selected_source(self):
        response = self.client.get(reverse("dashboard"), {"source_id": self.indeed.id})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["jobs"].paginator.count, 1)
        self.assertEqual(response.context["jobs"].object_list[0].source_website, "Indeed")


class TriggerScrapeViewTests(TestCase):
    def setUp(self):
        self.website = create_custom_website(name="RemoteBoard")

    def test_trigger_scrape_requires_post(self):
        response = self.client.get(reverse("trigger_scrape"))

        self.assertEqual(response.status_code, 405)

    @patch("job_scraper.views.JobScraper")
    def test_trigger_scrape_post_uses_selected_source(self, scraper_cls):
        scraper_cls.return_value.get_recent_jobs.return_value = []

        response = self.client.post(
            reverse("trigger_scrape"),
            {
                "q": "python",
                "countries": "us",
                "source_id": str(self.website.id),
            },
        )

        self.assertEqual(response.status_code, 302)
        scraper_cls.return_value.get_recent_jobs.assert_called_once_with(
            "us", "python", max_pages=1, website_id=self.website.id
        )


class WebsiteDeleteViewTests(TestCase):
    def setUp(self):
        self.website = create_custom_website(name="DeleteMe")

    def test_delete_website_requires_post(self):
        response = self.client.get(reverse("delete_website", args=[self.website.id]))

        self.assertEqual(response.status_code, 405)
        self.website.refresh_from_db()
        self.assertTrue(self.website.is_active)

    def test_delete_website_post_soft_deletes_website(self):
        response = self.client.post(reverse("delete_website", args=[self.website.id]))

        self.assertEqual(response.status_code, 302)
        self.website.refresh_from_db()
        self.assertFalse(self.website.is_active)


class JobDetailViewTests(TestCase):
    def test_job_detail_returns_saved_job(self):
        job = Job.objects.create(
            title="Backend Engineer",
            company="Acme",
            location="Remote",
            description="Build APIs",
            source_website="LinkedIn",
        )

        response = self.client.get(reverse("job_detail", args=[job.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["job"].id, job.id)


class RequestScraperEnrichmentTests(TestCase):
    def test_enrich_job_data_handles_country_without_unboundlocalerror(self):
        scraper = JobScraper()

        enriched = scraper._enrich_job_data(
            {"location": "Germany", "title": "Engineer", "company": "Acme"},
            "",
            "python",
        )

        self.assertEqual(enriched["country"], "Germany")
        self.assertTrue(enriched["continent"])


class ApiScraperLoggingTests(TestCase):
    def setUp(self):
        self.website = create_custom_website(
            name="API Source",
            is_api=True,
            api_jobs_path="data",
            api_title_key="title",
            api_company_key="company",
            api_location_key="location",
            api_description_key="description",
            api_url_key="url",
        )

    @patch("job_scraper.api_scraper.requests.get")
    def test_api_failure_still_creates_execution_log(self, get_mock):
        response = Mock()
        response.raise_for_status.side_effect = requests.HTTPError("boom")
        response.text = '{"error": "boom"}'
        get_mock.return_value = response

        jobs = ApiScraper().scrape(self.website, "python", "us")

        self.assertEqual(jobs, [])
        self.assertEqual(ScraperExecutionLog.objects.count(), 1)
        log = ScraperExecutionLog.objects.first()
        self.assertIn("API Request Failed", log.error_message)
        self.assertEqual(log.scraper_type, "api")
