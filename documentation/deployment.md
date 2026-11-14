# Deployment guide

Target: a single Linux host (or a small autoscaling group) running Gunicorn, Celery, PostgreSQL, Redis and Nginx. The application is stateless apart from the database and media volumes, so it can be containerised later without changing the domain code.

## 1. Prerequisites

- Ubuntu 24.04 LTS or equivalent
- Python 3.12
- PostgreSQL 16+
- Redis 7+
- Nginx 1.24+
- A domain with TLS certificates (Let's Encrypt is sufficient)
- Resend account and verified sending domain (or an SMTP provider)
- Optional: ClamAV, Sentry, object storage for backups

System packages:

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3-pip build-essential \
  libpq-dev postgresql postgresql-contrib redis-server nginx certbot \
  python3-certbot-nginx clamav clamav-daemon
```

Create a service user and directories:

```bash
sudo useradd --system --home /srv/facultynxtgen --shell /usr/sbin/nologin facultynxtgen
sudo mkdir -p /srv/facultynxtgen /srv/facultynxtgen/media/public /srv/facultynxtgen/media/private
sudo chown -R facultynxtgen:www-data /srv/facultynxtgen
sudo chmod 750 /srv/facultynxtgen/media/private
```

## 2. PostgreSQL

```sql
CREATE ROLE facultynxtgen LOGIN PASSWORD 'replace-with-a-strong-password';
CREATE DATABASE facultynxtgen OWNER facultynxtgen;
ALTER DATABASE facultynxtgen SET timezone TO 'Asia/Kolkata';
```

Use TLS (`sslmode=require` or stricter) and restrict `pg_hba.conf` to the application host. Do not reuse the database superuser.

## 3. Redis

Redis is used for the cache (rate limits) and Celery. Bind it to localhost or a private network and require a password:

```conf
bind 127.0.0.1
protected-mode yes
requirepass replace-with-a-strong-password
appendonly no
maxmemory-policy allkeys-lru
```

## 4. Application install

```bash
sudo -u facultynxtgen git clone <repository-url> /srv/facultynxtgen
cd /srv/facultynxtgen
sudo -u facultynxtgen python3.12 -m venv .venv
sudo -u facultynxtgen .venv/bin/pip install --upgrade pip
sudo -u facultynxtgen .venv/bin/pip install -r requirements/production.txt
```

Create `/srv/facultynxtgen/.env` from `.env.example` and lock it down. The application loads this file through `python-dotenv`, and systemd reads the same file:

```bash
sudo install -m 640 -o root -g facultynxtgen /dev/null /srv/facultynxtgen/.env
sudo editor /srv/facultynxtgen/.env
```

Required production values at minimum:

```dotenv
DJANGO_SETTINGS_MODULE=config.settings.production
DJANGO_SECRET_KEY=<64+ random characters>
DJANGO_ALLOWED_HOSTS=facultynxtgen.com,www.facultynxtgen.com
CSRF_TRUSTED_ORIGINS=https://facultynxtgen.com,https://www.facultynxtgen.com
SITE_URL=https://facultynxtgen.com
DATABASE_URL=postgresql://facultynxtgen:<password>@127.0.0.1:5432/facultynxtgen?sslmode=require
REDIS_URL=redis://:<password>@127.0.0.1:6379/0
CELERY_BROKER_URL=redis://:<password>@127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://:<password>@127.0.0.1:6379/1
DJANGO_DEBUG=False
MFA_REQUIRED_FOR_STAFF=True
PRIVATE_MEDIA_ROOT=/srv/facultynxtgen/media/private
SUPPORT_EMAIL=support@facultynxtgen.com
DEFAULT_FROM_EMAIL=FacultyNxtGen <notifications@facultynxtgen.com>
RESEND_API_KEY=<live key>
RESEND_FROM_EMAIL=FacultyNxtGen <notifications@facultynxtgen.com>
```

No payment credentials are required. The platform runs as a free service with no Razorpay, checkout, subscription, invoice or refund configuration.

`DJANGO_SETTINGS_MODULE` is normally set by the service unit; keeping it in the env file makes management commands consistent.

## 5. Database, static files and checks

```bash
cd /srv/facultynxtgen
sudo -u facultynxtgen .venv/bin/python manage.py check --deploy
sudo -u facultynxtgen .venv/bin/python manage.py migrate
sudo -u facultynxtgen .venv/bin/python manage.py seed_reference
sudo -u facultynxtgen .venv/bin/python manage.py collectstatic --noinput
```

`seed_reference` creates only reference data (states, cities, departments, designations and FAQs). It does not create plans or pricing data.

Create the first staff account interactively:

```bash
sudo -u facultynxtgen .venv/bin/python manage.py createsuperuser
```

The account must complete TOTP setup before using the staff console.

## 6. Gunicorn and systemd

Example files are provided in `deployment/`:

- `deployment/gunicorn.conf.py`
- `deployment/facultynxtgen.service`
- `deployment/facultynxtgen-celery.service`
- `deployment/facultynxtgen-celerybeat.service`
- `deployment/nginx.conf.example`

Install them:

```bash
sudo cp deployment/gunicorn.conf.py /srv/facultynxtgen/deployment/gunicorn.conf.py
sudo cp deployment/facultynxtgen.service /etc/systemd/system/
sudo cp deployment/facultynxtgen-celery.service /etc/systemd/system/
sudo cp deployment/facultynxtgen-celerybeat.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now facultynxtgen facultynxtgen-celery facultynxtgen-celerybeat
```

Check:

```bash
sudo systemctl status facultynxtgen
sudo journalctl -u facultynxtgen -n 100 --no-pager
curl -I http://127.0.0.1:8000/
```

## 7. Nginx and TLS

```bash
sudo cp deployment/nginx.conf.example /etc/nginx/sites-available/facultynxtgen
sudo ln -s /etc/nginx/sites-available/facultynxtgen /etc/nginx/sites-enabled/facultynxtgen
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d facultynxtgen.com -d www.facultynxtgen.com
```

The example Nginx configuration:

- terminates TLS;
- passes `Host`, `X-Real-IP`, `X-Forwarded-For` and `X-Forwarded-Proto`;
- serves `/static/` from `staticfiles/`;
- serves only the public media directory at `/media/`;
- never exposes the private media directory;
- allows 12 MB request bodies so application-level validation can return a useful error.

Verify HTTPS redirects, HSTS and cookie flags after enabling TLS.

## 8. Celery

The worker and beat processes run under systemd. Beat uses the database scheduler (`django_celery_beat`), so migrations must be applied before starting beat.

```bash
sudo systemctl status facultynxtgen-celery facultynxtgen-celerybeat
sudo journalctl -u facultynxtgen-celery -n 100 --no-pager
```

Scheduled work:

- expire jobs hourly;
- send job alerts daily;
- deliver queued email.

If Redis is unavailable, the email service falls back to synchronous delivery. That keeps transactional mail working but degrades request latency; alert the on-call operator.

## 9. Email delivery

Resend should be configured with a verified domain, SPF, DKIM and DMARC. The application sends through the Resend API when `RESEND_API_KEY` is set; delivery status is stored on `EmailLog`.

There are no payment webhooks to configure. `/payments/` is not routed, and the retired payment app exposes no endpoints.

## 10. Private media and backups

Back up:

- PostgreSQL (`pg_dump` or managed snapshots);
- `/srv/facultynxtgen/media/private` (candidate CVs, evidence);
- `/srv/facultynxtgen/media/public` (institution logos and blog images);
- `/srv/facultynxtgen/.env` in a secret store, not in the same backup as the database.

Restore drills are required. Private media permissions should be `750` for directories and `640` for files, owned by the service user.

## 11. Deployment sequence

1. Put the app in maintenance mode or drain the load balancer.
2. Back up the database and private media.
3. Pull the release and install dependencies.
4. Run `migrate`.
5. Run `collectstatic`.
6. Restart Gunicorn, Celery worker and beat.
7. Smoke-test `/`, `/jobs/`, `/institutions/`, `/accounts/login/`, `/sitemap.xml` and `/robots.txt`.
8. Complete one free institution verification, job submission, staff publication and candidate application on staging.
9. Re-enable traffic and watch error, security and email logs.

For zero-downtime releases, run two app releases behind Nginx and switch the upstream symlink after migrations are backward compatible. Avoid destructive schema changes in the same release as application code that still reads the old schema.

## 12. Go-live checklist

- [ ] Production settings load with `check --deploy`
- [ ] PostgreSQL migrations applied; no pending migrations
- [ ] Static files collected; manifest storage works
- [ ] Private media path writable but not web-accessible
- [ ] TLS, HSTS, secure cookies and CSRF origins verified
- [ ] Staff MFA enforced and tested
- [ ] Resend domain authenticated; test email delivered
- [ ] Celery worker and beat running; schedules visible in admin
- [ ] Rate limits coordinated through Redis
- [ ] Backups and restore drill completed
- [ ] Sentry/alerts configured
- [ ] Free-launch messaging and legal pages reviewed
- [ ] Responsive and accessibility QA signed off
- [ ] Penetration test findings resolved
