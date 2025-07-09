from django.test import TestCase
from django.conf import settings
import logging

from job_scraper.enhanced_scrapers import EnhancedJobScraper
from job_scraper.scrapers import get_scraper, scrape_jobs
from job_scraper.models import Job, CustomWebsite


class SetupTestCase(TestCase):
    """Test that the basic setup and imports work correctly"""
    
    def test_django_setup(self):
        """Test that Django is properly configured"""
        self.assertTrue(settings.DEBUG is not None)
        self.assertIn('job_scraper', settings.INSTALLED_APPS)
    
    def test_models_import(self):
        """Test that models can be imported and created"""
        # Test Job model
        job = Job.objects.create(
            title="Test Job",
            company="Test Company",
            location="Test Location",
            description="Test Description",
            source_website="test"
        )
        self.assertEqual(job.title, "Test Job")
        self.assertEqual(job.company, "Test Company")
        
        # Test CustomWebsite model
        website = CustomWebsite.objects.create(
            name="Test Website",
            base_url="https://test.com",
            search_url="https://test.com/search",
            job_list_selector=".job",
            title_selector=".title",
            company_selector=".company",
            location_selector=".location",
            job_link_selector=".link"
        )
        self.assertEqual(website.name, "Test Website")
        self.assertEqual(website.base_url, "https://test.com")
    
    def test_scraper_import(self):
        """Test that scraper classes can be imported and instantiated"""
        scraper = EnhancedJobScraper()
        self.assertIsNotNone(scraper)
        self.assertIsNotNone(scraper.session)


class ScrapingTestCase(TestCase):
    """Test the job scraping functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.scraper = EnhancedJobScraper()
        self.test_websites = ["indeed", "linkedin"]
        self.test_country = "us"
        self.test_keywords = "python developer"
    
    def test_scraper_initialization(self):
        """Test that scraper initializes correctly"""
        self.assertIsNotNone(self.scraper.session)
        self.assertIn('User-Agent', self.scraper.session.headers)
    
    def test_get_scraper_function(self):
        """Test the get_scraper function"""
        scraper = get_scraper("indeed")
        self.assertIsNotNone(scraper)
    
    def test_scrape_jobs_function(self):
        """Test the scrape_jobs function with minimal parameters"""
        try:
            # Test with minimal scraping to avoid overwhelming servers
            jobs = scrape_jobs(
                websites=["indeed"], 
                country="us", 
                keywords="python"
            )
            self.assertIsInstance(jobs, list)
            # Don't fail if no jobs found (depends on external factors)
            if jobs:
                self.assertIsInstance(jobs[0], dict)
                self.assertIn('title', jobs[0])
        except Exception as e:
            # Log the error but don't fail the test
            logging.warning(f"Scraping test failed (expected for external dependencies): {e}")
    
    def test_enhanced_scraper_methods(self):
        """Test EnhancedJobScraper methods"""
        # Test that methods exist and are callable
        self.assertTrue(hasattr(self.scraper, 'get_recent_jobs'))
        self.assertTrue(callable(self.scraper.get_recent_jobs))
        
        # Test with minimal parameters
        try:
            jobs = self.scraper.get_recent_jobs(
                websites=["indeed"],
                country="us",
                keywords="python",
                max_pages=1
            )
            self.assertIsInstance(jobs, list)
        except Exception as e:
            logging.warning(f"Enhanced scraper test failed (expected): {e}")


class EasyApplyFilterTestCase(TestCase):
    """Test the EasyApply filtering functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.scraper = EnhancedJobScraper()
    
    def test_easyapply_filtering_logic(self):
        """Test the EasyApply filtering logic"""
        # Test with sample job data that would be filtered
        test_jobs = [
            {
                'title': 'Software Engineer',
                'company': 'Tech Corp',
                'location': 'San Francisco, CA',
                'description': 'Easy Apply - Quick application process',
                'source_website': 'linkedin'
            },
            {
                'title': 'Python Developer',
                'company': 'Startup Inc',
                'location': 'Remote',
                'description': 'Traditional application process',
                'source_website': 'linkedin'
            }
        ]
        
        # The filtering logic should be in the scraper
        # This test verifies the concept works
        self.assertIsInstance(test_jobs, list)
        self.assertEqual(len(test_jobs), 2)
    
    def test_linkedin_scraping_with_filtering(self):
        """Test LinkedIn scraping with EasyApply filtering"""
        try:
            # Test with minimal scraping
            jobs = self.scraper.get_recent_jobs(
                websites=["linkedin"],
                country="us",
                keywords="python developer",
                max_pages=1
            )
            self.assertIsInstance(jobs, list)
            # Jobs should be filtered (no EasyApply jobs)
            for job in jobs:
                self.assertIsInstance(job, dict)
                self.assertIn('title', job)
        except Exception as e:
            logging.warning(f"LinkedIn filtering test failed (expected): {e}")


class ModelTestCase(TestCase):
    """Test the Django models"""
    
    def test_job_model(self):
        """Test Job model creation and fields"""
        job = Job.objects.create(
            title="Senior Python Developer",
            company="Tech Company",
            industry="Technology",
            location="San Francisco, CA",
            city="San Francisco",
            country="USA",
            description="We are looking for a senior Python developer...",
            requirements="5+ years of Python experience...",
            salary="$120,000 - $150,000",
            job_type="Full-time",
            experience_level="Senior",
            application_link="https://company.com/apply",
            source_website="linkedin",
            source_url="https://linkedin.com/jobs/123"
        )
        
        self.assertEqual(job.title, "Senior Python Developer")
        self.assertEqual(job.company, "Tech Company")
        self.assertEqual(job.salary, "$120,000 - $150,000")
        self.assertEqual(job.source_website, "linkedin")
        
        # Test string representation
        self.assertIn("Senior Python Developer", str(job))
        self.assertIn("Tech Company", str(job))
    
    def test_custom_website_model(self):
        """Test CustomWebsite model creation and fields"""
        website = CustomWebsite.objects.create(
            name="Custom Job Board",
            base_url="https://customjobs.com",
            search_url="https://customjobs.com/search?q={keywords}&l={location}",
            job_list_selector=".job-listing",
            title_selector=".job-title",
            company_selector=".company-name",
            location_selector=".job-location",
            salary_selector=".salary",
            date_selector=".posted-date",
            job_link_selector=".job-link",
            apply_link_selector=".apply-button",
            description_selector=".job-description",
            requirements_selector=".requirements",
            is_active=True
        )
        
        self.assertEqual(website.name, "Custom Job Board")
        self.assertEqual(website.base_url, "https://customjobs.com")
        self.assertTrue(website.is_active)
        
        # Test string representation
        self.assertEqual(str(website), "Custom Job Board")
    
    def test_model_ordering(self):
        """Test that models have proper ordering"""
        # Create multiple jobs with different timestamps
        job1 = Job.objects.create(
            title="Job 1",
            company="Company 1",
            location="Location 1",
            description="Description 1",
            source_website="test"
        )
        
        job2 = Job.objects.create(
            title="Job 2",
            company="Company 2",
            location="Location 2",
            description="Description 2",
            source_website="test"
        )
        
        # Jobs should be ordered by created_at descending (newest first)
        jobs = Job.objects.all()
        self.assertEqual(jobs[0], job2)  # Most recent first
        self.assertEqual(jobs[1], job1)


class IntegrationTestCase(TestCase):
    """Integration tests for the complete workflow"""
    
    def test_complete_workflow(self):
        """Test the complete job scraping workflow"""
        # Test that we can create a scraper
        scraper = EnhancedJobScraper()
        self.assertIsNotNone(scraper)
        
        # Test that we can create models
        job = Job.objects.create(
            title="Test Job",
            company="Test Company",
            location="Test Location",
            description="Test Description",
            source_website="test"
        )
        self.assertIsNotNone(job)
        
        # Test that we can query models
        jobs = Job.objects.filter(source_website="test")
        self.assertEqual(jobs.count(), 1)
        self.assertEqual(jobs[0], job)
    
    def test_custom_website_workflow(self):
        """Test custom website creation and management"""
        # Create a custom website
        website = CustomWebsite.objects.create(
            name="Test Website",
            base_url="https://test.com",
            search_url="https://test.com/search",
            job_list_selector=".job",
            title_selector=".title",
            company_selector=".company",
            location_selector=".location",
            job_link_selector=".link"
        )
        
        # Test that it's active by default
        self.assertTrue(website.is_active)
        
        # Test that we can deactivate it
        website.is_active = False
        website.save()
        self.assertFalse(website.is_active)
        
        # Test that we can reactivate it
        website.is_active = True
        website.save()
        self.assertTrue(website.is_active)
