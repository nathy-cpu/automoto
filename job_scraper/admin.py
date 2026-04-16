from django.contrib import admin
from .models import Job, CustomWebsite, Contact

@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ('title', 'company', 'location', 'source_website', 'is_rfp', 'created_at')
    list_filter = ('source_website', 'is_rfp', 'continent')
    search_fields = ('title', 'company', 'location', 'description')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(CustomWebsite)
class CustomWebsiteAdmin(admin.ModelAdmin):
    list_display = ('name', 'base_url', 'use_stealth', 'is_active', 'created_at')
    list_filter = ('is_active', 'use_stealth')
    search_fields = ('name', 'base_url')
    readonly_fields = ('created_at',)

@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('name', 'title', 'company_name', 'email', 'created_at')
    search_fields = ('name', 'title', 'email', 'job__company')
    
    def company_name(self, obj):
        return obj.job.company
    company_name.short_description = 'Company'
