# Phase 1 — Foundation and Core Platform Report

> **Historical document.** This report records the Phase 1 build as it was delivered. It is retained for audit and context only. The payment, plan, subscription, invoice, refund and paid-placement functionality described below has since been **removed** as part of the free-launch conversion. The current product provides free academic recruitment services to registered educational institutions. See [architecture.md](architecture.md), [security.md](security.md) and the free-launch report for the current state.

**Status:** Superseded by the free-launch conversion
**Date:** 14 November 2026
**Environment used:** Windows, Python 3.12, Django 5.2.19, SQLite development fallback
**Production target:** PostgreSQL 16+, Redis 7+, Gunicorn, Nginx, Celery

---

## 1. Phase objective

Deliver the first working, end-to-end release of FacultyNxtGen: the public academic job marketplace, candidate and institution portals, staff review console, application workflow, private documents, Razorpay payment plumbing, notifications, SEO, security controls, automated tests and deployment documentation.

The phase deliberately stops short of launch. Pricing, legal copy, live provider credentials, PostgreSQL staging validation, and browser-based visual/accessibility QA require owner input and are listed in section 10.

---

## 2. What was delivered

### 2.1 Public website

- Home page with verified-institution and live-vacancy data only, category counts, department and state discovery, candidate/institution calls to action, trust and verification content.
- Find Jobs with composable filters (keyword, department, designation, state, city, institution type, experience, posted date, sort), pagination, empty states and preserved query strings.
- Focused landing pages: Teaching, Research, Non-Teaching, institution-type pages and state pages. Empty landing pages return 404 instead of thin content.
- Job detail: eligibility, pay, deadlines, source notification, institution card, related jobs, report-job flow, apply panel.
- External application disclosure modal showing the institution, official website, exact destination URL and deadline before the user leaves.
- Institution directory and institution public profile with live vacancies.
- About, Contact, Advertise, FAQ, Blog list/detail, Privacy, Terms, Disclaimer and Cookie Preferences.
- Newsletter double opt-in, contact enquiry intake, custom 400/403/404/429/500 pages.
- Sitemap, robots.txt, canonicals, meta descriptions, Open Graph, breadcrumbs.
- `JobPosting` JSON-LD only on live, public job detail pages; `directApply` is false for external roles.

### 2.2 Accounts and authentication

- Custom email-first user model with UUID primary key, unique email and Indian mobile validation.
- Candidate and institution registration, email verification with time-limited tokens, verification resend.
- Login with per-IP rate limiting and per-account failed-attempt lockout.
- Password reset, password change, session hardening.
- TOTP MFA for staff with QR provisioning, confirmation and recovery through staff reset.
- Data export and account-deletion request flows.
- Role decorators and role-scoped dashboard redirects.

### 2.3 Candidate portal

- Academic profile with headline, bio, qualifications, PhD status, specialization, preferred roles/locations.
- Structured qualification, teaching experience, research experience, publication and certification records.
- CV and supporting document uploads through private storage with signed downloads.
- Profile completion indicator and visibility controls.
- Saved jobs, application list/detail, withdrawal, job alerts, recommendations.
- Notifications and per-category email preferences.
- Privacy settings, data export, account deletion request.

### 2.4 Institution portal

- Institution registration with authorisation/registration documents and primary recruiter creation.
- Pending/verified/rejected/suspended gate: unverified institutions cannot submit or publish vacancies.
- Recruiter invitations and team management.
- Vacancy drafts with structural validation, edit, delete, submit, clone, pause and status history.
- Applicant review with profile snapshot, CV, supporting documents, internal notes and controlled status transitions.
- Analytics for views, applications and external clicks.
- Plan selection, order history, invoices, refund requests.
- Institution profile and logo management.

### 2.5 Applications

- Internal applications with CV, consent, optional cover letter/supporting documents, profile snapshot and duplicate prevention.
- Status machine: submitted → under review → shortlisted → selected/rejected; candidate withdrawal.
- Immutable status history with actor, note and timestamp; status emails.
- External application click tracking and guarded redirect (`https`, `http`, `mailto` only), with anonymous continuation.
- Idempotent submission protection and cross-institution access denial.

### 2.6 Staff console (`/dashboard/admin/`)

- Statistics dashboard and review queues.
- Institution verification decisions with document review and notes.
- Job checklist review: approve, publish, reject, suspend, with reasons and history.
- Reports moderation, user moderation, recruiter/account oversight.
- Payment and refund handling, order inspection.
- Content management for blog, FAQs, contact enquiries and newsletter subscribers.
- Audit log viewer.
- Staff access restricted by `is_staff`; TOTP enforced in production.
- Django admin retained as an operational fallback with read-only registrations for sensitive records and custom password forms.

### 2.7 Payments and advertising — retired

> **Historical only.** Everything in this subsection was removed in the free-launch conversion. No payment code, model, route, credential or template remains active.

- Plans: featured advertisement, premium advertisement, monthly and annual subscription.
- Server-side order creation; prices always read from the database.
- Razorpay order API integration, checkout callback signature verification, webhook secret verification and replay-safe fulfilment.
- Payment, invoice (PDF), refund and advertisement records.
- Featured placement only from a paid, unexpired advertisement created by fulfilment; no frontend flag can unlock it.
- Plan limits gate active jobs, not drafts.
- Scheduled advertisement and job expiry.

### 2.8 Notifications and email

- In-app notifications with categories, read state and safe local redirects.
- Transactional email pipeline with Resend adapter and Django email fallback.
- HTML and text bodies rendered once and persisted on `EmailLog` so Celery workers do not depend on request objects.
- Email preference enforcement, marketing opt-in, signed unsubscribe links.
- Staff notifications for verification, jobs, contact enquiries and payments.
- Celery tasks for email, job alerts, job expiry and advertisement expiry.

### 2.9 Security and operations

- Argon2 password hashing, secure cookie settings, HSTS/HTTPS redirects in production.
- CSP with per-request nonce; scripts are self-hosted or explicitly allow-listed (Razorpay).
- CSRF on all state-changing requests; ORM-only queries.
- Rate limiting on registration, login, reset, contact, newsletter, institution registration, search, reports, checkout, refunds and exports.
- Honeypot fields added at form initialisation on public/institution/refund forms.
- Upload validation by extension, size, magic bytes and real content; optional ClamAV integration that fails closed.
- Private document storage with signed, expiring, user-bound download links and audit logging.
- Audit log for security-relevant actions.
- Development/production settings split; production refuses SQLite, weak secrets, missing hosts/CSRF origins.
- WhiteNoise static serving, Redis cache for rate limits, Sentry-ready configuration.

### 2.10 Brand and frontend

- Official `Logo.png` used without recolouring; derived brand mark and favicon.
- Navy `#10264A`, blue `#087BDB`, light `#F4F7FC` tokens.
- Self-hosted Inter and Plus Jakarta Sans; vendored Bootstrap 5.3.3 and Bootstrap Icons 1.11.3.
- One shared template tree with a role-aware dashboard shell.
- External brand CSS/JS to satisfy CSP; Razorpay checkout script loaded only on the order detail page.
- Responsive Bootstrap layouts and WCAG 2.2 AA-oriented markup (skip link, landmarks, labels, focus states, reduced motion). Viewport QA remains manual.

---

## 3. Architecture summary

Modular monolith with one Django project (`config`) and twelve domain apps:

| App | Responsibility |
| --- | --- |
| `core` | public pages, states/cities, blog, FAQs, newsletter, SEO, shared forms/middleware |
| `accounts` | custom user, auth, MFA, data rights, role decorators |
| `candidates` | candidate profile and academic records |
| `institutions` | institutions, verification evidence, recruiters |
| `jobs` | taxonomy, vacancies, search, alerts, workflow, analytics |
| `applications` | internal applications and external click tracking |
| `documents` | private storage, upload validation, signed downloads |
| `payments` | historical: plans, orders, Razorpay, invoices, refunds, advertisements. Now migration-only; runtime code removed. |
| `notifications` | email rendering/delivery and in-app notifications |
| `audit` | action log |
| `dashboard` | staff review console |
| `search` | cross-entity search |

Key invariants:

- Public visibility requires `status=published`, `is_deleted=false`, deadline not passed, and a verified, active institution.
- Institution verification gates vacancy submission. (The payment gate on capacity and featured placement has been removed; posting is free.)
- Documents are never public URLs; access is owner, staff, or the institution the candidate applied to.
- Status transitions happen in services, not views or templates.

Full rationale: [architecture.md](architecture.md).

---

## 4. Files created

### Configuration

- `manage.py`
- `config/__init__.py`, `config/urls.py`, `config/wsgi.py`, `config/asgi.py`, `config/celery.py`
- `config/settings/__init__.py`
- `config/settings/base.py`, `development.py`, `production.py`, `env.py`

### Applications (126 Python files excluding migrations)

Each app contains `__init__.py`, `apps.py`, `models.py`, `views.py`, `urls.py`, `forms.py` and/or `services.py`, `admin.py`, `tests.py`, `migrations/0001_initial.py` as applicable. Additional notable files:

- `apps/accounts/decorators.py`, `middleware.py`, `tokens.py`, `validators.py`
- `apps/candidates/signals.py`
- `apps/jobs/managers.py`, `filters.py`, `recruiter_views.py`, `tasks.py`
- `apps/applications/services.py`
- `apps/documents/storage.py`, `services.py`, `templatetags/documents.py`
- `apps/payments/services.py`, `invoice.py`, `razorpay.py` integration paths
- `apps/notifications/services.py`, `tasks.py`
- `apps/audit/services.py`
- `apps/core/testing.py` (shared test factories), `constants.py`, `utils.py`, `validators.py`, `widgets.py`, `context_processors.py`, `middleware.py`
- `apps/core/management/commands/seed_reference.py`

### Templates (128 HTML files)

`templates/base.html` plus:

- `public/` — home, about, contact, advertise, FAQ, blog, legal pages, newsletter states
- `accounts/` — login, register, verification, password reset/change, MFA, data rights
- `candidates/` — dashboard, profile, records, documents, saved jobs, alerts, applications, settings
- `institutions/` — registration, dashboard, profile, recruiters, jobs, applicants, analytics, payments, settings
- `jobs/` — find, landing pages, detail, apply, report
- `applications/` — apply, list, detail
- `payments/` — plans, order detail, invoices, refunds
- `notifications/` — list, preferences, unsubscribe
- `dashboard/` — role-aware shell and 15 staff console pages
- `emails/` — base plus 20 HTML and 20 text templates
- `errors/` — 400, 403, 404, 429, 500
- `partials/` and `components/` — cards, filters, pagination, forms, alerts

### Static assets (21 files)

- Bootstrap 5.3.3 CSS/JS bundle, Bootstrap Icons CSS and font files
- Self-hosted Inter and Plus Jakarta Sans font files
- `static/css/brand.css`
- `static/js/main.js`, `static/js/payments.js`
- `static/images/` — official logo, brand mark, favicon and app icons

### Documentation and deployment

- `README.md`
- `.env.example`
- `.gitignore`
- `requirements.txt`
- `requirements/base.txt`, `development.txt`, `production.txt`
- `documentation/architecture.md`
- `documentation/security.md`
- `documentation/deployment.md`
- `documentation/phase-1-report.md` (this file)
- `deployment/gunicorn.conf.py`
- `deployment/facultynxtgen.service`
- `deployment/facultynxtgen-celery.service`
- `deployment/facultynxtgen-celerybeat.service`
- `deployment/nginx.conf.example`

---

## 5. Database changes

### Migrations (12 initial migrations)

| App | Migration |
| --- | --- |
| accounts | `0001_initial` |
| core | `0001_initial` |
| candidates | `0001_initial`, `0002_initial` |
| institutions | `0001_initial` |
| jobs | `0001_initial` |
| documents | `0001_initial` |
| applications | `0001_initial`, `0002_initial` |
| payments | `0001_initial` |
| notifications | `0001_initial` |
| audit | `0001_initial` |

All applied to the development database. `makemigrations --check --dry-run` reports no pending model changes.

### Reference data seeded

`python manage.py seed_reference` created:

- 36 states and union territories
- 183 cities
- 29 departments
- 20 designations
- 10 FAQs

`python manage.py seed_reference --with-plans` created 4 sample plans in the original build. The flag, the plans and all pricing data have since been removed; current `seed_reference` creates reference data only.

### Development database state

- 1 staff user, 0 candidates, 0 institutions, 0 jobs, 0 blog posts, 0 orders, 0 newsletter subscribers.
- No fake production job advertisements, institutions or testimonials were created.
- Individual app migrations are standard Django migrations; PostgreSQL-specific behaviour still needs staging validation.

---

## 6. Commands used

```powershell
# Setup
python -m pip install -r requirements/development.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py seed_reference
python manage.py seed_reference --with-plans

# Development
python manage.py runserver

# Verification
python manage.py check
python manage.py check --deploy     # with temporary production environment values
python manage.py makemigrations --check --dry-run
python manage.py test
```

The development superuser is `admin@facultynxtgen.local`. Its password was generated during setup and shared in the working session only; it is not stored in this repository. Reset it with:

```powershell
python manage.py changepassword admin@facultynxtgen.local
```

Staff MFA is required on first console login when `MFA_REQUIRED_FOR_STAFF=True`. Development currently disables the requirement by default.

---

## 7. Tests and verification

### Automated tests

**90 tests, all passing** (`python manage.py test`, ~10 seconds, SQLite test database).

Coverage by module:

| Module | Focus |
| --- | --- |
| `apps/accounts/tests.py` | registration, verification, login lockout, password reset, MFA, data export/deletion, role redirects |
| `apps/institutions/tests.py` | registration, document upload, verification gate, recruiter scoping, dashboard permissions |
| `apps/jobs/tests.py` | live visibility, drafts, filters, JSON-LD, expiry, external route disclosure, workflow transitions |
| `apps/applications/tests.py` | internal submission, duplicate prevention, external rejection, status machine, cross-institution denial |
| `apps/payments/tests.py` | historical: order creation, signature verification, webhook rejection, idempotent fulfilment, refunds, featured placement. Removed with the payment runtime. |
| `apps/documents/tests.py` | extension/size/content validation, malware hook, private storage, signed links, token tampering, cross-user denial, soft delete |
| `apps/notifications/tests.py` | rendered body persistence, missing templates, preference suppression, scoping, mark-read, unsubscribe |
| `apps/core/tests.py` | public pages, live-only home, blog visibility, contact+honeypot, newsletter double opt-in, cookies, sitemap/robots, custom 404 |

### Static verification

- `python manage.py check` — no issues (2 development-only rate-limit cache checks silenced).
- `python manage.py makemigrations --check --dry-run` — no changes.
- `python manage.py check --deploy` — clean with production environment values, after switching production cache to `django_redis`.
- All 128 templates compile.
- Development server smoke test: 23 routes returned expected 200/302/404, including public pages, auth, institution registration, plans, staff console and custom 404.

### Bugs found and fixed during verification

- Notification mark-read route used a UUID converter for an integer primary key.
- Marketing email without an authenticated user crashed on unsubscribe URL construction.
- Home institution annotation used inconsistent names (`live_count` vs `live_jobs_count`).
- Honeypot fields declared on a plain mixin were never collected by the form metaclass; the field is now injected in `__init__`.
- External application modal hid the destination behind a login requirement; anonymous users can now continue through the tracked redirect with full disclosure.
- Expired-job test created a deadline before the publication date, violating the model constraint.
- Candidate test factory cached a stale profile after CV assignment.
- `last_seen_at` middleware called `.objects` on the user instance instead of the user model manager.
- Production cache used Django's built-in Redis backend, which `django-ratelimit` does not support; switched to `django-redis`.

---

## 8. How to review this phase

1. Read [architecture.md](architecture.md) and [security.md](security.md).
2. Start the server: `python manage.py runserver`.
3. Review public routes: `/`, `/jobs/`, job detail, `/institutions/`, `/about/`, `/contact/`, `/faq/`, `/blog/`, legal pages.
4. Register a candidate and an institution using test email addresses. The console email backend prints verification links.
5. Sign in to `/dashboard/admin/` as the development staff user and review verification/job/payment queues.
6. Run `python manage.py test` and confirm 90 passing tests.
7. Review sample plans and legal copy before approving production use.

---

## 9. Decisions that need owner confirmation

- ~~**Pricing and GST:** the four plans created by `--with-plans` are samples.~~ Superseded: plans and pricing were removed for the free launch.
- **Legal copy:** Privacy, Terms and Disclaimer are structured drafts and require counsel review for Indian law and data protection. (Payment/refund obligations no longer apply.)
- **Brand:** the logo is used as supplied. Confirm the derived mark/favicon and social preview card.
- **Contact details:** phone, address and support email are placeholders in `.env.example` and must be replaced.
- **Email sender:** confirm the production domain and Resend/SMTP provider.
- **MFA policy:** confirm staff TOTP is mandatory and who holds break-glass access.
- **Retention:** 365 days for candidate data and 730 days for audit logs are defaults, not legal advice.

---

## 10. Known issues and limitations

### Environment blockers

- **No local PostgreSQL server and no running Docker daemon.** Development runs on SQLite. Production settings reject SQLite and require `DATABASE_URL`; PostgreSQL migrations, constraints and concurrent behaviour must be verified in staging before launch.
- ~~**No live Razorpay credentials.**~~ Superseded: the payment integration was removed; no gateway credentials are required.
- **No live Resend credentials.** Delivery uses the Django console backend in development; the Resend adapter is untested against the live API.
- **No ClamAV daemon.** Upload validation and the fail-closed scanner hook are tested; virus scanning is not active unless `CLAMAV_HOST` is configured.

### Manual QA outstanding

- Browser-based visual and responsive QA at 360, 375, 390, 430, 768, 1024, 1280 and 1440 px.
- Screen-reader and keyboard audit against WCAG 2.2 AA.
- ~~Cross-browser payment checkout test.~~ Removed with the payment runtime.
- Email rendering QA in major clients.
- Real-device testing for file uploads and PDF downloads.

### Product/compliance

- ~~Sample plans and tax settings need commercial and legal review.~~ Removed with the payment runtime.
- Legal pages need counsel review.
- No WAF/bot-management service; rate limits and honeypots are the current controls.
- CSP still permits inline styles; a future pass can remove the remaining inline style attributes.
- No CI pipeline or container image is configured yet.
- No git repository is initialised in the working directory.

### Minor technical notes

- `requests` and `urllib3` emit a dependency warning in this environment; a compatible `requests` pin is included, but the global Python environment still reports the installed urllib3 version.
- SQLite is single-writer; load and concurrency behaviour must be tested on PostgreSQL.
- Celery runs eagerly in development; production requires Redis plus worker and beat services.

---

## 11. Approval requested

Phase 1 is functionally complete and verified to the extent possible without external services, PostgreSQL and a browser. Please review the delivered scope and the decisions in section 9.

On approval, the recommended next phase is **staging readiness and launch hardening**:

1. Provision PostgreSQL and Redis, run migrations and the full suite there.
2. Execute Resend deliverability tests.
3. Replace contact details and legal copy.
4. Complete responsive and accessibility QA and fix findings.
5. Add CI, backup/restore drills and monitoring.
6. Conduct a penetration test before accepting real candidate data.

No further feature work should start until this phase is approved.
