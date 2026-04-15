# AutoMoto Job Search Interface

Django app for searching jobs across supported job sites and user-defined custom job boards.

## Current Scope

- Built-in sources: `Indeed`, `LinkedIn`
- Custom sources: user-managed websites using CSS selectors
- Server-rendered UI with session-backed results and pagination

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

### 4. Run database migrations

```bash
venv/bin/python manage.py migrate
```

### 5. Start the app

```bash
./run.sh
```

Or:

```bash
venv/bin/python manage.py runserver 0.0.0.0:8000
```

## URLs

- App: `http://localhost:8000`
- Admin: `http://localhost:8000/admin`

## Testing

Run deterministic test suite:

```bash
venv/bin/python manage.py test
```

## Notes

- Scraping behavior depends on external site markup and availability.
- Custom website scraping is configured from the app UI at `/websites/`.
- This repository intentionally avoids OS-specific bootstrap scripts and uses one manual setup flow.
