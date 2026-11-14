# FacultyNxtGen

FacultyNxtGen is a verification-first academic recruitment platform for Indian universities, colleges and research institutions. It combines a public vacancy marketplace with candidate and institution portals, a staff review console, and private document handling. **All core recruitment features are free for candidates and registered educational institutions.**

**Tagline:** The Next Generation of Academic Careers.

## Stack

- Django 5.2 (modular monolith)
- PostgreSQL in production; SQLite fallback for local development
- Bootstrap 5.3, self-hosted Bootstrap Icons, Inter and Plus Jakarta Sans
- Celery + Redis for email, job expiry and alerts
- Resend transactional email with Django email fallback
- WhiteNoise static serving, CSP, rate limiting, TOTP MFA and audit logging

## What is included

**Public site**

- Home, Find Jobs, Teaching, Research, Non-Teaching
- Job detail with official notification, application method, click disclosure and `JobPosting` JSON-LD on live jobs only
- Institution directory and profiles
- About, Contact, Advertise, FAQ, blog, Privacy, Terms, Disclaimer, cookie preferences
- Custom 400/403/404/429/500 pages
- Sitemap, robots.txt and focused SEO landing pages

**Candidate portal**

- Email-verified registration, password reset, session security
- Academic profile, qualifications, teaching/research experience, publications, certifications
- CV and supporting documents with signed, time-limited downloads
- Saved jobs, application tracking, job alerts, recommendations
- Notifications, email preferences, data export and account deletion

**Institution portal**

- Institution registration with authorisation documents
- Verification gate before vacancy creation
- Recruiter invitations and team management
- Free vacancy posting after verification
- Draft, submit, edit, delete, pause and track vacancies
- Applicant review, internal notes and status workflow
- Job views, application and engagement analytics

**Staff dashboard**

- Platform statistics and review queues
- Institution verification decisions
- Job checklist approval, publish, reject and suspend
- Reports, user moderation and account access
- Content/enquiries, audit log and team access
- TOTP MFA required for staff in production

**Applications**

- Internal applications with profile snapshot, CV, consent and status history
- External applications through a tracked redirect with destination disclosure
- Candidate and recruiter status communication
- No payment, subscription or paid placement is required at any stage

## Quick start (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements/development.txt

Copy-Item .env.example .env
# Edit .env. For local development the defaults already use SQLite and the console email backend.

python manage.py migrate
python manage.py seed_reference
python manage.py createsuperuser
python manage.py runserver
```

Open `http://127.0.0.1:8000/`. The Django admin is at `/admin/`; the custom staff console is at `/dashboard/admin/`.

On first staff sign-in, TOTP setup is required when `MFA_REQUIRED_FOR_STAFF=True`. In development this can be disabled with `MFA_REQUIRED_FOR_STAFF=False`.

## Configuration

All configuration is environment-driven. See `.env.example` for the complete list. Important values:

| Variable | Purpose |
| --- | --- |
| `DJANGO_SETTINGS_MODULE` | `config.settings.development` or `config.settings.production` |
| `DJANGO_SECRET_KEY` | Long random signing key; required in production |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hostnames |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated HTTPS origins |
| `DATABASE_URL` | PostgreSQL URL used in production |
| `REDIS_URL` | Cache/broker backend for production rate limits and Celery |
| `SITE_URL` | Canonical absolute site URL used in email and SEO |
| `RESEND_API_KEY` | Enables Resend delivery; otherwise Django email is used |
| `PRIVATE_MEDIA_ROOT` | Filesystem location for private uploads |
| `CLAMAV_HOST`, `CLAMAV_PORT` | Optional ClamAV scan; uploads fail closed if configured but unreachable |
| `MFA_REQUIRED_FOR_STAFF` | Forces TOTP for staff accounts |

Never commit `.env`. The repository ignores it and runtime data.

## Management commands

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py seed_reference
python manage.py test
python manage.py collectstatic --noinput   # production
```

## Tests

```powershell
python manage.py test
```

The suite covers authentication, role permissions, institution verification, free job workflow, applications, recruiter review, job alerts, private documents, notifications/email, public pages and free-launch regressions (no payment routes, credentials, subscriptions or paid placement). Test databases are created automatically; no seeded production data is required.

Current result: **101 tests passing** on the local SQLite test database.

## Project layout

```
apps/
  accounts/        custom user, auth, MFA, data rights
  candidates/      candidate profile and academic records
  institutions/    institution registration, verification, recruiters
  jobs/            taxonomy, vacancies, search, alerts, workflow
  applications/    internal/external applications and status history
  documents/       private storage, validation, signed downloads
  payments/        migration-only app that drops the retired payment tables
  notifications/   email rendering/delivery, in-app notifications
  audit/           staff and security action log
  dashboard/       staff review console
  core/            public pages, reference data, SEO, shared helpers
  search/          cross-entity search
config/
  settings/        base, development, production, env helpers
  celery.py        Celery application
templates/         public, auth, candidate, institution, jobs,
                   notifications, dashboard, emails and error templates
static/            vendored Bootstrap, icons, self-hosted fonts, brand CSS/JS
documentation/     architecture, security and operations notes
deployment/        example Gunicorn, systemd and Nginx configuration
```

## Routes overview

| Area | Prefix |
| --- | --- |
| Public pages | `/`, `/jobs/`, `/institutions/`, `/about/`, `/contact/` |
| Accounts | `/accounts/` |
| Candidate dashboard | `/dashboard/candidate/` |
| Institution dashboard | `/dashboard/institution/` |
| Staff console | `/dashboard/admin/` |
| Applications | `/applications/` |
| Notifications | `/notifications/` |
| Private documents | `/documents/<id>/download/?token=...` |
| Django admin | `/admin/` |

## Documentation

- [Architecture](documentation/architecture.md)
- [Security model](documentation/security.md)
- [Deployment guide](documentation/deployment.md)
- [Phase completion report](documentation/phase-1-report.md)

## Current limitations

- Local development uses SQLite because no PostgreSQL server or Docker daemon was available. Production settings reject SQLite and require PostgreSQL.
- Resend and ClamAV live-provider flows are implemented but not exercised against live credentials. Automated tests cover rendering and failure paths with local backends.
- Celery runs eagerly in development. Production requires a Redis broker plus worker and beat processes.
- The retired `apps/payments` app remains installed only so migration `0002_remove_payment_models` can drop legacy payment tables on existing databases. It has no models, views, URLs, tasks or services.
- Browser-based visual QA across 360/375/390/430/768/1024/1280/1440 remains a manual pre-launch step; automated tests validate routing, templates and permissions.

## License and ownership

Proprietary project. The FacultyNxtGen name, logo and brand assets are supplied by the project owner and must not be redistributed without permission.
