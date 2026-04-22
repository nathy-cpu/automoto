# EasyApply Filtering (Archived)

## Current Status

LinkedIn-specific EasyApply filtering pipeline is not implemented in current scraper.
Current scraping architecture uses generic `CustomWebsite` integrations via:

- Requests scraper (`job_scraper/request_scraper.py`)
- Stealth scraper (`job_scraper/stealth_scraper.py`)
- JSON API scraper (`job_scraper/api_scraper.py`)

## Why This Document Changed

Previous version referenced methods and scripts no longer present in repository:

- `_parse_linkedin_card`
- `_get_linkedin_job_details`
- `_scrape_linkedin`
- `test_easyapply_filter.py`

## If EasyApply Filtering Is Needed Again

1. Add explicit apply-mode extraction logic in scraper pipeline.
2. Add filtering policy flags (allow/deny EasyApply) per source.
3. Add tests in `job_scraper/tests.py` for filtering behavior.
4. Update website seed config in `job_scraper/management/commands/seed_websites.py`.

## Notes

Use `CustomWebsite` selector/API configuration for source-specific behavior.
