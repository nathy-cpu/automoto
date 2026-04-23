from unittest.mock import Mock, patch

from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

import requests

from job_scraper.anti_bot import (
    classify_anti_bot_response,
    clear_block_state,
    compute_selector_coverage,
    record_block_event,
    summarize_selector_coverage,
)
from job_scraper.api_scraper import ApiScraper
from job_scraper.apollo_client import ApolloClient
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
            country="United States",
            description="Python and Django",
            source_website="Indeed",
        )
        Job.objects.create(
            title="Data Engineer",
            company="Beta",
            location="Berlin",
            country="Germany",
            description="Spark and SQL",
            source_website="LinkedIn",
        )

    def test_dashboard_filters_by_selected_source(self):
        response = self.client.get(reverse("dashboard"), {"source_id": self.indeed.id})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["jobs"].paginator.count, 1)
        self.assertEqual(
            response.context["jobs"].object_list[0].source_website, "Indeed"
        )

    def test_dashboard_country_filter_matches_common_alias(self):
        response = self.client.get(reverse("dashboard"), {"countries": "us"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["jobs"].paginator.count, 1)
        self.assertEqual(
            response.context["jobs"].object_list[0].country, "United States"
        )


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


class AntiBotMitigationTests(TestCase):
    def tearDown(self):
        clear_block_state(999)

    def test_classifier_ignores_marker_strings_when_cards_exist(self):
        html = '<div class="job_seen_beacon"></div><script>var x="recaptcha cloudflare";</script>'

        result = classify_anti_bot_response(200, html, card_count=1)

        self.assertFalse(result["blocked"])

    def test_classifier_blocks_challenge_page_without_cards(self):
        html = '<html><div id="cf-challenge">Verify you are human</div></html>'

        result = classify_anti_bot_response(403, html, card_count=0)

        self.assertTrue(result["blocked"])
        self.assertIn("status=403", result["reason"])

    def test_record_block_event_enters_cooldown_after_threshold(self):
        first = record_block_event(999, threshold=2, cooldown_seconds=60)
        second = record_block_event(999, threshold=2, cooldown_seconds=60)

        self.assertEqual(first["failures"], 1)
        self.assertEqual(second["failures"], 2)
        self.assertIsNotNone(second["cooldown_until"])

    def test_compute_selector_coverage_summarizes_per_field_hits(self):
        from bs4 import BeautifulSoup

        doc = BeautifulSoup(
            '<div class="job"><span class="title">A</span></div><div class="job"></div>',
            "html.parser",
        )
        coverage = compute_selector_coverage(
            doc.select(".job"), {"title": ".title", "company": ".company"}
        )
        summary = summarize_selector_coverage(coverage)

        self.assertEqual(coverage["title"]["hits"], 1)
        self.assertEqual(coverage["title"]["total"], 2)
        self.assertIn("title=1/2(50%)", summary)
        self.assertIn("company=0/2(0%)", summary)


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


@override_settings(DEBUG_ENRICHMENT=False)
class ApolloClientTests(TestCase):
    @patch("job_scraper.apollo_client.requests.post")
    def test_search_contacts_uses_api_search_then_bulk_match(self, post_mock):
        search_response = Mock()
        search_response.raise_for_status = Mock()
        search_response.json.return_value = {
            "people": [
                {"id": "p1", "name": "Jane Doe", "title": "CTO"},
                {"id": "p2", "name": "John Roe", "title": "CEO"},
            ]
        }

        enrich_response = Mock()
        enrich_response.raise_for_status = Mock()
        enrich_response.json.return_value = {
            "matches": [
                {
                    "id": "p1",
                    "name": "Jane Doe",
                    "title": "CTO",
                    "email": "jane@example.com",
                    "linkedin_url": "https://linkedin.com/in/jane",
                    "phone_number": "+123",
                }
            ]
        }

        post_mock.side_effect = [search_response, enrich_response]
        client = ApolloClient(api_key="test-key")

        contacts = client.search_contacts("Acme")

        self.assertEqual(len(contacts), 1)
        self.assertEqual(contacts[0]["name"], "Jane Doe")
        self.assertEqual(post_mock.call_count, 2)
        self.assertIn("mixed_people/api_search", post_mock.call_args_list[0].args[0])
        self.assertIn("people/bulk_match", post_mock.call_args_list[1].args[0])


class RequestScraperCooldownTests(TestCase):
    def setUp(self):
        self.website = create_custom_website(name="BlockedBoard")

    @patch("job_scraper.request_scraper.get_cooldown_remaining", return_value=120)
    @patch("job_scraper.request_scraper.JobScraper._scrape_custom_website")
    def test_get_recent_jobs_skips_website_during_cooldown(
        self, scrape_mock, cooldown_mock
    ):
        jobs = JobScraper().get_recent_jobs("us", "python", website_id=self.website.id)

        self.assertEqual(jobs, [])
        scrape_mock.assert_not_called()
        self.assertEqual(ScraperExecutionLog.objects.count(), 1)
        self.assertIn(
            "Skipped due to anti-bot cooldown",
            ScraperExecutionLog.objects.first().error_message,
        )
