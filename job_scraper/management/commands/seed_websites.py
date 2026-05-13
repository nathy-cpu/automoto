from django.core.management.base import BaseCommand

from job_scraper.models import CustomWebsite

DEFAULT_WEBSITES = [
    {
        "name": "Indeed",
        "base_url": "https://www.indeed.com",
        "search_url": "https://www.indeed.com/jobs?q={keywords}&l={location}&fromage=1",
        "job_list_selector": ".job_seen_beacon",
        "title_selector": 'h2.jobTitle span[id^="jobTitle-"]',
        "company_selector": '[data-testid="company-name"]',
        "location_selector": '[data-testid="text-location"]',
        "salary_selector": '[data-testid="attribute_snippet_salary"], .salary-snippet-container, .salary-snippet, .salaryOnly',
        "date_selector": '[data-testid="timing-attribute"]',
        "job_link_selector": "h2.jobTitle a",
        "description_selector": "#jobDescriptionText",
        "use_stealth": True,
    },
    {
        "name": "LinkedIn",
        "base_url": "https://www.linkedin.com",
        "search_url": "https://www.linkedin.com/jobs/search?keywords={keywords}&location={location}&f_TPR=r86400",
        "job_list_selector": ".base-search-card",
        "title_selector": ".base-search-card__title",
        "company_selector": ".base-search-card__subtitle",
        "location_selector": ".job-search-card__location",
        "salary_selector": ".job-search-card__salary-info",
        "date_selector": ".job-search-card__listdate, .job-search-card__listdate--new",
        "job_link_selector": ".base-card__full-link",
        "description_selector": ".show-more-less-html__markup, .description__text",
        "use_stealth": True,
    },
    {
        "name": "We Work Remotely",
        "base_url": "https://weworkremotely.com",
        "search_url": "https://weworkremotely.com/remote-jobs/search?term={keywords}",
        "job_list_selector": "#search-results section.jobs li.new-listing-container:not(.listing-ad)",
        "title_selector": 'a[href*="/remote-jobs/"] h3, a[href*="/remote-jobs/"] h4',
        "company_selector": ".company",
        "location_selector": ".region",
        "date_selector": ".date, .time",
        "job_link_selector": 'a[href*="/remote-jobs/"]',
        "description_selector": ".lis-container, main article",
    },
    {
        "name": "Arbeitnow (API)",
        "base_url": "https://www.arbeitnow.com",
        "search_url": "https://www.arbeitnow.com/api/job-board-api?search={keywords}",
        "job_list_selector": "N/A",
        "title_selector": "N/A",
        "company_selector": "N/A",
        "location_selector": "N/A",
        "job_link_selector": "N/A",
        "is_api": True,
        "api_jobs_path": "data",
        "api_title_key": "title",
        "api_company_key": "company_name",
        "api_location_key": "location",
        "api_description_key": "description",
        "api_url_key": "url",
    },
    {
        "name": "Remotive (API)",
        "base_url": "https://remotive.com",
        "search_url": "https://remotive.com/api/remote-jobs?search={keywords}",
        "job_list_selector": "N/A",
        "title_selector": "N/A",
        "company_selector": "N/A",
        "location_selector": "N/A",
        "job_link_selector": "N/A",
        "is_api": True,
        "api_jobs_path": "jobs",
        "api_title_key": "title",
        "api_company_key": "company_name",
        "api_location_key": "candidate_required_location",
        "api_description_key": "description",
        "api_url_key": "url",
    },
    {
        "name": "TED EU Tenders",
        "base_url": "https://ted.europa.eu",
        "search_url": "https://ted.europa.eu/TED/search/search.do?keywords={keywords}&language=en&pageNo=1&sortBy=0&status=0&yearFilter=0",
        "job_list_selector": ".searchResults tr, .notice-list-item",
        "title_selector": "a[href*='/TED/view/'] span, .notice-title a",
        "company_selector": ".notice-buyer, .buyer-name",
        "location_selector": ".notice-country, .country-name",
        "date_selector": ".notice-date, .pub-date",
        "job_link_selector": ".notice-title a, a[href*='/TED/view/']",
        "description_selector": ".notice-content, .TED-content",
        "use_stealth": True,
    },
    {
        "name": "UK Contracts Finder",
        "base_url": "https://www.contractsfinder.service.gov.uk",
        "search_url": "https://www.contractsfinder.service.gov.uk/Search/Results?&searchQuery={keywords}",
        "job_list_selector": ".search-result, .notice-item, .opportunity-card",
        "title_selector": ".search-result-title a, .notice-title a",
        "company_selector": ".search-result-organisation, .buyer-name",
        "location_selector": ".search-result-location, .notice-location",
        "date_selector": ".search-result-date, .notice-published",
        "job_link_selector": ".search-result-title a, .notice-title a",
        "description_selector": ".search-result-description, .notice-detail",
        "use_stealth": True,
    },
]


class Command(BaseCommand):
    help = "Seed the database with initial custom website configurations"

    def handle(self, *args, **kwargs):
        for ws_data in DEFAULT_WEBSITES:
            obj, created = CustomWebsite.objects.update_or_create(
                name=ws_data["name"], defaults=ws_data
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f"Successfully created {ws_data['name']}")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f"Successfully updated {ws_data['name']}")
                )
