from django.shortcuts import render, get_object_or_404
from django.http import HttpRequest
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Job

# Create your views here.

def job_search(request: HttpRequest):
    if request.method == 'POST':
        keywords = request.POST.get('keywords', '')
        location = request.POST.get('location', '')
        websites = request.POST.getlist('websites')
        
        # For now, return mock data - this will be replaced with actual scraping
        mock_jobs = [
            {
                'id': 1,
                'title': 'Senior Python Developer',
                'company': 'Tech Corp',
                'location': 'New York, NY',
                'source_website': 'indeed'
            },
            {
                'id': 2,
                'title': 'Data Scientist',
                'company': 'AI Solutions',
                'location': 'San Francisco, CA',
                'source_website': 'linkedin'
            },
            {
                'id': 3,
                'title': 'Full Stack Developer',
                'company': 'Startup Inc',
                'location': 'Remote',
                'source_website': 'glassdoor'
            }
        ]
        
        # Filter by selected websites
        if websites:
            mock_jobs = [job for job in mock_jobs if job['source_website'] in websites]
        
        # Pagination
        paginator = Paginator(mock_jobs, 10)  # 10 jobs per page
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)
        
        context = {
            'results': page_obj,
            'pagination': page_obj,
            'params': {
                'keywords': keywords,
                'location': location,
                'websites': websites
            }
        }
        return render(request, 'job_scraper/job_search.html', context)
    
    return render(request, 'job_scraper/job_search.html')

def job_detail(request: HttpRequest, job_id: int):
    # For now, return mock detailed data - this will be replaced with actual database queries
    mock_job_detail = {
        'id': job_id,
        'title': 'Senior Python Developer',
        'company': 'Tech Corp',
        'industry': 'Technology',
        'location': 'New York, NY',
        'city': 'New York',
        'country': 'United States',
        'description': 'We are looking for a Senior Python Developer to join our growing team...',
        'requirements': '• 5+ years of Python development experience\n• Experience with Django, Flask\n• Knowledge of databases (PostgreSQL, MySQL)\n• Experience with cloud platforms (AWS, GCP)',
        'salary': '$120,000 - $150,000',
        'job_type': 'Full-time',
        'experience_level': 'Senior',
        'deadline': '2024-02-15',
        'posted_date': '2024-01-15',
        'application_instructions': 'Please submit your resume and cover letter through our application portal.',
        'application_link': 'https://techcorp.com/careers/python-developer',
        'source_website': 'Indeed',
        'source_url': 'https://indeed.com/viewjob?jk=123456'
    }
    
    return render(request, 'job_scraper/job_detail.html', {'job': mock_job_detail})
