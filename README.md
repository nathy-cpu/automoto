# AutoMoto — RFP & Consulting Lead Discovery

Django app for discovering software project contracts, RFPs, and consulting opportunities across public procurement platforms and job boards.

## Current Scope

- Built-in sources: `Indeed`, `LinkedIn`, `We Work Remotely`, `Arbeitnow (API)`, `Remotive (API)`, `TED EU Tenders`, `UK Contracts Finder`
- Custom sources: user-managed websites using CSS selectors
- Server-rendered dashboard with database-backed results and pagination
- Scheduled discovery runs with email summaries for subscribed users

## Quick Start

### 1. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

Optional:

- Development tools: `pip install -r requirements-dev.txt`
- Production extras: `pip install -r requirements-prod.txt`

### 3. Configure environment

Create `.env` (or update existing):

```env
DEBUG=True
SECRET_KEY=replace-this
ALLOWED_HOSTS=localhost,127.0.0.1
```

Or start from the checked-in template:

```bash
cp .env.example .env
```

The template includes runtime knobs for:

- time zone
- scrape defaults
- scraper timeouts
- anti-bot cooldowns
- scheduler cleanup
- stealth browser sizing/warm-up behavior
- email delivery
- demo seed credentials

### 4. Run database migrations

```bash
venv/bin/python manage.py migrate
```

If this repo was already using an older SQLite database from before the custom user model was added, reset the local DB first:

```bash
mv db.sqlite3 db.sqlite3.bak
venv/bin/python manage.py migrate
```

### 5. Seed local demo data

```bash
venv/bin/python manage.py seed_demo_data
```

Default seeded login:

- email: `admin@example.com`
- password: `admin12345`

## Admin User Workflow

User accounts are admin-created only.

### Create a new user

1. Sign in to Django admin at `http://localhost:8000/admin/`.
2. Open `Users`.
3. Click `Add User`.
4. Enter the user's email and an initial password.
5. Leave `Staff status` off for normal app users.
6. Leave `Superuser status` off unless the user should administer the system.
7. Save the user.

### What the new user does next

1. Sign in at `http://localhost:8000/accounts/login/`.
2. Use the `Change Password` link in the app header if they want to replace the admin-set password.

### Deactivate a user

1. Open the user in Django admin.
2. Uncheck `Active`.
3. Save.

## Scheduled Scrapes

Scheduled scrapes are managed in Django admin only.

### Create a scheduled scrape

1. Sign in to `http://localhost:8000/admin/`.
2. Open `Scheduled scrapes`.
3. Create a new schedule.
4. Choose one or more source websites.
5. Set the same search inputs used by manual scrapes:
   - `keywords`
   - `countries` as a comma-separated list
   - `continents` as a comma-separated list
   - `location` only as a fallback if countries and continents are blank
6. Set max pages and enrichment limit.
7. Enter a 5-field cron expression such as:
   - `*/30 * * * *` for every 30 minutes
   - `0 * * * *` for hourly
   - `0 8,20 * * *` for 8:00 and 20:00 daily
8. Set an IANA timezone like `UTC` or `America/New_York`.
9. Keep `Active` enabled and save.

Location resolution matches the manual scrape button:

- first country if any countries are set
- otherwise first continent if any continents are set
- otherwise fallback location

### Apply schedule changes

The scheduler command reads schedules from the database when it starts.
If you add or edit schedules, restart the scheduler process so it reloads them.

### Test a schedule immediately

Use the `Run selected schedules now` admin action from the scheduled scrape changelist.

### Email subscriptions

Each scheduled scrape can have multiple subscribed users.

After a scheduled run completes, subscribed users receive:

- a summary email
- the number of new jobs found
- the top 10 new jobs
- a dashboard link for deeper review

Email backend behavior:

- development default: Django console email backend
- production default: SMTP backend

Useful environment variables:

- `EMAIL_BACKEND`
- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`
- `EMAIL_USE_TLS`
- `EMAIL_USE_SSL`
- `DEFAULT_FROM_EMAIL`
- `EMAIL_SUBJECT_PREFIX`
- `SITE_DOMAIN`

You can override that user:

```bash
venv/bin/python manage.py seed_demo_data --email you@example.com --password strongpass123
```

This command seeds:

- a dev superuser for login/admin access
- default source configurations
- sample jobs for the dashboard
- sample contacts for job detail pages

### 6. Start the app

```bash
./run.sh
```

Or:

```bash
venv/bin/python manage.py runserver 0.0.0.0:8000
```

### Running with Docker

You can also run the entire stack using Docker and Docker Compose:

```bash
docker-compose up --build
```

This will automatically handle all system dependencies, including Google Chrome for stealth scraping.

## URLs

- App: `http://localhost:8000`
- Admin: `http://localhost:8000/admin`

## Testing

Run deterministic test suite:

```bash
venv/bin/python manage.py test
```

## Hugging Face Spaces

This repo can run on a Docker Space.

### Recommended Space type

- SDK: `Docker`
- Hardware: start with CPU Basic for testing
- Persistent storage: recommended if you want SQLite data to survive restarts

### Required setup

1. Push this repository to a Hugging Face Docker Space.
2. In the Space variables/secrets, set at least:

```env
DEBUG=False
SECRET_KEY=replace-with-a-long-random-secret
ALLOWED_HOSTS=your-space-name.hf.space
CSRF_TRUSTED_ORIGINS=https://your-space-name.hf.space
SITE_DOMAIN=your-space-name.hf.space
SQLITE_PATH=/data/db.sqlite3
RUN_MIGRATIONS=true
RUN_COLLECTSTATIC=true
RUN_SCHEDULER=false
SECURE_SSL_REDIRECT=False
```

3. If you enabled persistent storage, keep `SQLITE_PATH=/data/db.sqlite3`.
4. If you want scheduled scrapes to run inside the same container, set `RUN_SCHEDULER=true`.

### Email on Spaces

For Gmail SMTP, set these secrets:

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=youraddress@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
DEFAULT_FROM_EMAIL=youraddress@gmail.com
```

### Notes

- The container starts with `/app/entrypoint.sh`.
- On boot it can run migrations, collect static files, optionally seed demo data, optionally start the scheduler, then launch Gunicorn.
- Running the scheduler in the same container is acceptable for a testing environment, but not ideal for scaled production.

## Notes

- Scraping behavior depends on external site markup and availability.
- Custom website scraping is configured from the app UI at `/websites/`.
- This repository intentionally avoids OS-specific bootstrap scripts and uses one manual setup flow.
