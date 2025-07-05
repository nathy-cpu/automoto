import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import time
import random
from urllib.parse import urljoin, urlparse
import logging
from .models import CustomWebsite

logger = logging.getLogger(__name__)

class EnhancedJobScraper:
    """Enhanced scraper that can handle multiple websites and extract detailed job information"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def get_recent_jobs(self, websites: List[str], country: str, keywords: Optional[str] = None, max_pages: int = 10) -> List[Dict]:
        """Get recent job postings from multiple websites"""
        all_jobs = []
        
        for website in websites:
            try:
                if website == 'indeed':
                    jobs = self._scrape_indeed(country, keywords, max_pages)
                elif website == 'linkedin':
                    jobs = self._scrape_linkedin(country, keywords, max_pages)
                elif website == 'glassdoor':
                    jobs = self._scrape_glassdoor(country, keywords, max_pages)
                elif website == 'monster':
                    jobs = self._scrape_monster(country, keywords, max_pages)
                elif website == 'careerbuilder':
                    jobs = self._scrape_careerbuilder(country, keywords, max_pages)
                elif website == 'ziprecruiter':
                    jobs = self._scrape_ziprecruiter(country, keywords, max_pages)
                else:
                    # Try custom website
                    jobs = self._scrape_custom_website(website, country, keywords, max_pages)
                
                all_jobs.extend(jobs)
                logger.info(f"Scraped {len(jobs)} jobs from {website}")
                
            except Exception as e:
                logger.error(f"Error scraping {website}: {e}")
                continue
        
        return all_jobs
    
    def _scrape_indeed(self, country: str, keywords: Optional[str], max_pages: int) -> List[Dict]:
        """Enhanced Indeed scraper with better detail extraction"""
        jobs = []
        country_urls = {
            'us': 'https://www.indeed.com',
            'uk': 'https://uk.indeed.com',
            'ca': 'https://ca.indeed.com',
            'au': 'https://au.indeed.com',
        }
        
        base_url = country_urls.get(country.lower(), 'https://www.indeed.com')
        
        for page in range(max_pages):
            try:
                search_params = {
                    'l': country,
                    'fromage': '1',  # Last 24 hours
                    'start': page * 10
                }
                
                if keywords:
                    search_params['q'] = keywords
                
                url = f"{base_url}/jobs"
                response = self.session.get(url, params=search_params)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                job_cards = soup.find_all('div', {'data-jk': True})
                
                if not job_cards:
                    break
                
                for card in job_cards:
                    try:
                        job_data = self._parse_indeed_card(card, base_url)
                        if job_data:
                            # Get detailed job information
                            detailed_job = self._get_indeed_job_details(job_data['job_url'])
                            job_data.update(detailed_job)
                            jobs.append(job_data)
                    except Exception as e:
                        logger.error(f"Error parsing Indeed job card: {e}")
                        continue
                
                time.sleep(random.uniform(1, 3))
                
            except Exception as e:
                logger.error(f"Error scraping Indeed page {page}: {e}")
                break
        
        return jobs
    
    def _parse_indeed_card(self, card, base_url: str) -> Optional[Dict]:
        """Parse individual job card from Indeed with enhanced data extraction"""
        try:
            job_id = card.get('data-jk')
            if not job_id:
                return None
            
            # Extract basic info
            title_elem = card.find('h2', class_='jobTitle')
            title = self._clean_text(title_elem.get_text()) if title_elem else ""
            
            company_elem = card.find('span', class_='companyName')
            company = self._clean_text(company_elem.get_text()) if company_elem else ""
            
            location_elem = card.find('div', class_='companyLocation')
            location = self._clean_text(location_elem.get_text()) if location_elem else ""
            
            # Extract salary
            salary_elem = card.find('div', class_='salary-snippet')
            salary = self._clean_text(salary_elem.get_text()) if salary_elem else ""
            
            # Extract posted date
            date_elem = card.find('span', class_='date')
            posted_date = self._clean_text(date_elem.get_text()) if date_elem else ""
            
            # Build job URL
            job_url = f"{base_url}/viewjob?jk={job_id}"
            
            return {
                'id': job_id,
                'title': title,
                'company': company,
                'location': location,
                'salary': salary,
                'posted_date': posted_date,
                'source_website': 'Indeed',
                'source_url': job_url,
                'job_url': job_url
            }
            
        except Exception as e:
            logger.error(f"Error parsing Indeed card: {e}")
            return None
    
    def _get_indeed_job_details(self, job_url: str) -> Dict:
        """Get detailed job information from Indeed job page"""
        try:
            response = self.session.get(job_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract detailed information
            description_elem = soup.find('div', {'id': 'jobDescriptionText'})
            description = self._clean_text(description_elem.get_text()) if description_elem else ""
            
            # Extract requirements
            requirements = self._extract_requirements(description)
            
            # Extract application instructions and link
            apply_elem = soup.find('div', class_='jobsearch-ApplyButton')
            application_instructions = self._clean_text(apply_elem.get_text()) if apply_elem else ""
            
            # Look for direct apply link
            apply_link_elem = soup.find('a', class_='jobsearch-ApplyButton')
            application_link = ""
            if apply_link_elem:
                application_link = apply_link_elem.get('href')
                if application_link and not application_link.startswith('http'):
                    application_link = urljoin(job_url, application_link)
            
            # Extract job type and experience level
            job_type = self._extract_job_type(description)
            experience_level = self._extract_experience_level(description)
            
            # Extract industry
            industry = self._extract_industry(description)
            
            return {
                'description': description,
                'requirements': requirements,
                'application_instructions': application_instructions,
                'application_link': application_link,
                'job_type': job_type,
                'experience_level': experience_level,
                'industry': industry
            }
            
        except Exception as e:
            logger.error(f"Error getting Indeed job details: {e}")
            return {}
    
    def _scrape_linkedin(self, country: str, keywords: Optional[str], max_pages: int) -> List[Dict]:
        """Enhanced LinkedIn scraper"""
        jobs = []
        base_url = "https://www.linkedin.com/jobs/search"
        
        for page in range(max_pages):
            try:
                search_params = {
                    'location': country,
                    'f_TPR': 'r86400',  # Last 24 hours
                    'start': page * 25
                }
                
                if keywords:
                    search_params['keywords'] = keywords
                
                response = self.session.get(base_url, params=search_params)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                job_cards = soup.find_all('div', class_='base-card')
                
                if not job_cards:
                    break
                
                for card in job_cards:
                    try:
                        job_data = self._parse_linkedin_card(card)
                        if job_data:
                            # Get detailed job information
                            detailed_job = self._get_linkedin_job_details(job_data['job_url'])
                            job_data.update(detailed_job)
                            jobs.append(job_data)
                    except Exception as e:
                        logger.error(f"Error parsing LinkedIn job card: {e}")
                        continue
                
                time.sleep(random.uniform(2, 4))
                
            except Exception as e:
                logger.error(f"Error scraping LinkedIn page {page}: {e}")
                break
        
        return jobs
    
    def _parse_linkedin_card(self, card) -> Optional[Dict]:
        """Parse LinkedIn job card with enhanced data extraction"""
        try:
            job_link_elem = card.find('a', class_='base-card__full-link')
            if not job_link_elem:
                return None
            
            job_url = job_link_elem.get('href')
            job_id = job_url.split('/')[-1] if job_url else None
            
            title_elem = card.find('h3', class_='base-search-card__title')
            title = self._clean_text(title_elem.get_text()) if title_elem else ""
            
            company_elem = card.find('h4', class_='base-search-card__subtitle')
            company = self._clean_text(company_elem.get_text()) if company_elem else ""
            
            location_elem = card.find('span', class_='job-search-card__location')
            location = self._clean_text(location_elem.get_text()) if location_elem else ""
            
            date_elem = card.find('time')
            posted_date = self._clean_text(date_elem.get_text()) if date_elem else ""
            
            return {
                'id': job_id,
                'title': title,
                'company': company,
                'location': location,
                'posted_date': posted_date,
                'source_website': 'LinkedIn',
                'source_url': job_url,
                'job_url': job_url
            }
            
        except Exception as e:
            logger.error(f"Error parsing LinkedIn card: {e}")
            return None
    
    def _get_linkedin_job_details(self, job_url: str) -> Dict:
        """Get detailed job information from LinkedIn job page"""
        try:
            response = self.session.get(job_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract description
            description_elem = soup.find('div', class_='show-more-less-html')
            description = self._clean_text(description_elem.get_text()) if description_elem else ""
            
            # Extract requirements
            requirements = self._extract_requirements(description)
            
            # Look for apply button
            apply_elem = soup.find('a', class_='apply-button')
            application_link = ""
            if apply_elem:
                application_link = apply_elem.get('href')
                if application_link and not application_link.startswith('http'):
                    application_link = urljoin(job_url, application_link)
            
            return {
                'description': description,
                'requirements': requirements,
                'application_link': application_link
            }
            
        except Exception as e:
            logger.error(f"Error getting LinkedIn job details: {e}")
            return {}
    
    def _scrape_custom_website(self, website_name: str, country: str, keywords: Optional[str], max_pages: int) -> List[Dict]:
        """Scrape custom website using stored selectors"""
        try:
            custom_website = CustomWebsite.objects.get(name=website_name, is_active=True)
            jobs = []
            
            for page in range(max_pages):
                try:
                    # Build search URL
                    search_url = custom_website.search_url
                    if '{keywords}' in search_url and keywords:
                        search_url = search_url.replace('{keywords}', keywords)
                    if '{location}' in search_url:
                        search_url = search_url.replace('{location}', country)
                    if '{page}' in search_url:
                        search_url = search_url.replace('{page}', str(page + 1))
                    
                    response = self.session.get(search_url)
                    response.raise_for_status()
                    
                    soup = BeautifulSoup(response.content, 'html.parser')
                    job_cards = soup.select(custom_website.job_list_selector)
                    
                    if not job_cards:
                        break
                    
                    for card in job_cards:
                        try:
                            job_data = self._parse_custom_card(card, custom_website)
                            if job_data:
                                jobs.append(job_data)
                        except Exception as e:
                            logger.error(f"Error parsing custom job card: {e}")
                            continue
                    
                    time.sleep(random.uniform(1, 3))
                    
                except Exception as e:
                    logger.error(f"Error scraping custom website page {page}: {e}")
                    break
            
            return jobs
            
        except CustomWebsite.DoesNotExist:
            logger.error(f"Custom website '{website_name}' not found")
            return []
    
    def _parse_custom_card(self, card, custom_website: CustomWebsite) -> Optional[Dict]:
        """Parse job card using custom selectors"""
        try:
            # Extract basic information using custom selectors
            title_elem = card.select_one(custom_website.title_selector)
            title = self._clean_text(title_elem.get_text()) if title_elem else ""
            
            company_elem = card.select_one(custom_website.company_selector)
            company = self._clean_text(company_elem.get_text()) if company_elem else ""
            
            location_elem = card.select_one(custom_website.location_selector)
            location = self._clean_text(location_elem.get_text()) if location_elem else ""
            
            # Extract job link
            job_link_elem = card.select_one(custom_website.job_link_selector)
            job_url = ""
            if job_link_elem:
                job_url = job_link_elem.get('href')
                if job_url and not job_url.startswith('http'):
                    job_url = urljoin(custom_website.base_url, job_url)
            
            # Extract additional information if selectors are provided
            salary = ""
            if custom_website.salary_selector:
                salary_elem = card.select_one(custom_website.salary_selector)
                salary = self._clean_text(salary_elem.get_text()) if salary_elem else ""
            
            posted_date = ""
            if custom_website.date_selector:
                date_elem = card.select_one(custom_website.date_selector)
                posted_date = self._clean_text(date_elem.get_text()) if date_elem else ""
            
            return {
                'id': f"{custom_website.name}_{len(jobs)}",
                'title': title,
                'company': company,
                'location': location,
                'salary': salary,
                'posted_date': posted_date,
                'source_website': custom_website.name,
                'source_url': job_url,
                'job_url': job_url
            }
            
        except Exception as e:
            logger.error(f"Error parsing custom card: {e}")
            return None
    
    def _extract_requirements(self, description: str) -> str:
        """Extract requirements from job description"""
        requirements_keywords = [
            'requirements', 'qualifications', 'skills', 'experience',
            'must have', 'should have', 'preferred', 'minimum'
        ]
        
        lines = description.split('\n')
        requirements_lines = []
        in_requirements = False
        
        for line in lines:
            line_lower = line.lower()
            
            if any(keyword in line_lower for keyword in requirements_keywords):
                in_requirements = True
            
            if in_requirements and line.strip():
                if line.strip().startswith(('•', '-', '*', '·')):
                    requirements_lines.append(line.strip())
                elif re.match(r'^\d+\.', line.strip()):
                    requirements_lines.append(line.strip())
        
        return '\n'.join(requirements_lines) if requirements_lines else ""
    
    def _extract_job_type(self, description: str) -> str:
        """Extract job type from description"""
        job_types = ['full-time', 'part-time', 'contract', 'temporary', 'internship', 'freelance']
        description_lower = description.lower()
        
        for job_type in job_types:
            if job_type in description_lower:
                return job_type.title()
        
        return "Full-time"  # Default
    
    def _extract_experience_level(self, description: str) -> str:
        """Extract experience level from description"""
        levels = {
            'entry-level': ['entry level', 'junior', '0-2 years', '1-2 years'],
            'mid-level': ['mid level', 'intermediate', '3-5 years', '2-5 years'],
            'senior': ['senior', 'lead', '5+ years', '7+ years', 'experienced'],
            'executive': ['executive', 'director', 'manager', 'head of']
        }
        
        description_lower = description.lower()
        
        for level, keywords in levels.items():
            if any(keyword in description_lower for keyword in keywords):
                return level.title()
        
        return "Mid-level"  # Default
    
    def _extract_industry(self, description: str) -> str:
        """Extract industry from description"""
        industries = [
            'technology', 'healthcare', 'finance', 'education', 'retail',
            'manufacturing', 'consulting', 'marketing', 'sales', 'engineering'
        ]
        
        description_lower = description.lower()
        
        for industry in industries:
            if industry in description_lower:
                return industry.title()
        
        return "Technology"  # Default
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ""
        return re.sub(r'\s+', ' ', text.strip())
    
    # Placeholder methods for other websites
    def _scrape_glassdoor(self, country: str, keywords: Optional[str], max_pages: int) -> List[Dict]:
        # Implementation for Glassdoor
        return []
    
    def _scrape_monster(self, country: str, keywords: Optional[str], max_pages: int) -> List[Dict]:
        # Implementation for Monster
        return []
    
    def _scrape_careerbuilder(self, country: str, keywords: Optional[str], max_pages: int) -> List[Dict]:
        # Implementation for CareerBuilder
        return []
    
    def _scrape_ziprecruiter(self, country: str, keywords: Optional[str], max_pages: int) -> List[Dict]:
        # Implementation for ZipRecruiter
        return [] 