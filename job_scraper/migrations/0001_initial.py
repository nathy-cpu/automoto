# Generated by Django 5.2.4 on 2025-07-04 21:46

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Job',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('company', models.CharField(max_length=200)),
                ('industry', models.CharField(blank=True, max_length=100)),
                ('location', models.CharField(max_length=200)),
                ('city', models.CharField(blank=True, max_length=100)),
                ('country', models.CharField(blank=True, max_length=100)),
                ('description', models.TextField()),
                ('requirements', models.TextField(blank=True)),
                ('salary', models.CharField(blank=True, max_length=100)),
                ('job_type', models.CharField(blank=True, max_length=50)),
                ('experience_level', models.CharField(blank=True, max_length=50)),
                ('deadline', models.DateField(blank=True, null=True)),
                ('posted_date', models.DateField(blank=True, null=True)),
                ('application_instructions', models.TextField(blank=True)),
                ('application_link', models.URLField(blank=True)),
                ('source_website', models.CharField(max_length=100)),
                ('source_url', models.URLField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
