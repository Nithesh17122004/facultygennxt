# Architecture

## 1. Shape of the system

FacultyNxtGen is a **modular monolith**. One Django project (`config`) hosts a set of bounded apps under `apps/`. The alternative — separate services for jobs, applications and candidate profiles — was rejected for the first release because:

- the domain has strong transactional links (an application must see a live job, a document belongs to a candidate but may be read by one institution);
- a single deployable unit keeps verification workflows and audit logging consistent;
- the expected traffic profile does not justify distributed operations;
- a clean app boundary still allows a future extraction if volume demands it.

Dependencies between apps are intentionally acyclic where possible. Cross-app references use string model references and service functions rather than importing views.

```
config/                 settings, URLs, WSGI/ASGI, Celery
apps/core/              public pages, reference data, SEO, shared validation
apps/accounts/          custom user, authentication, MFA, privacy rights
apps/candidates/        candidate profile and academic records
apps/institutions/      institutions, verification documents, recruiters
apps/jobs/              taxonomy, jobs, search, alerts, workflow
apps/applications/      internal applications, external click tracking
apps/documents/         private storage and signed downloads
apps/payments/          migration-only app that removes the retired payment schema
apps/notifications/     email pipeline and in-app notifications
apps/audit/             immutable action log
apps/dashboard/         staff review console
apps/search/            cross-entity search endpoints
templates/              one shared template tree
static/                 vendored Bootstrap, icons, fonts, brand CSS/JS
```

## 2. Roles and access

The custom user model (`apps.accounts.User`) has one of three roles:

| Role | Purpose |
| --- | --- |
| `candidate` | Academic professional managing a profile and applications |
| `recruiter` | Institution team member managing vacancies and applicants |
| `admin` | Platform staff reviewing institutions, jobs and reports |

Access is enforced in layers:

1. **Authentication** — email/password, Argon2 hashing, optional TOTP.
2. **Role decorators** — `candidate_required`, `recruiter_required`, `staff_required` (in account/institution helpers).
3. **Institution scoping** — recruiter queries are filtered to the recruiter's institution, not just to the role.
4. **Object ownership** — candidate documents, applications and alerts are filtered by the signed-in user.
5. **Verification gates** — an institution must be `verified` and active before vacancies can be submitted or published.
6. **Free access** — no payment, subscription or paid placement gate exists. Every verified institution can post vacancies and invite recruiters without payment.

The staff console (`/dashboard/admin/`) and Django admin (`/admin/`) are separate surfaces. The custom console is the intended review workflow; Django admin is an operational fallback and has read-only registrations for sensitive records.

## 3. Data model overview

### Accounts and candidates

- `User` — UUID primary key, unique email and mobile, role, verification timestamp, login lockout state, last-seen timestamp.
- `AccountDeletionRequest` — queued privacy request with processing state.
- `CandidateProfile` — one-to-one with a candidate user; headline, qualifications summary, PhD status, specialization, CV link, visibility flags.
- Structured records: `Qualification`, `TeachingExperience`, `ResearchExperience`, `Publication`, `Certification`.
- `SavedJob`, `JobAlert` — candidate engagement, both scoped to the candidate.

### Institutions

- `Institution` — profile, location, verification status (`pending`, `verified`, `rejected`, `suspended`), verification notes and timestamps.
- `InstitutionDocument` — private evidence with review status.
- `Recruiter` — links a user to an institution, with primary/active flags and optional invite state.

### Jobs

- `Department`, `Designation` — reference taxonomy, seeded separately from live vacancies.
- `Job` — the vacancy aggregate: institution, poster, taxonomy, location, eligibility, pay, deadlines, source information, application method, review checklist and status.
- `JobStatusHistory` — audit trail for workflow transitions.
- `JobView`, `JobReport`, `ExternalClick` — analytics and trust signals.
- `JobAlertDelivery` — prevents duplicate alert mail for the same alert/job pair.

### Applications

- `Application` — candidate, job, cover letter, resume, immutable profile snapshot, status, consent timestamp.
- `ApplicationDocument` — supporting files attached to an application.
- `ApplicationNote` — recruiter-only notes.
- `ApplicationStatusHistory` — status changes with actor, note and timestamp.
- `ExternalClick` — destination and metadata for external applications.

### Retired payment schema

The original plan, order, payment, invoice, refund, advertisement and subscription tables were removed by `apps.payments.migrations.0002_remove_payment_models`. The `apps.payments` package remains installed only so existing databases can apply that migration. It has no models, views, URLs, admin, forms, tasks or services.

### Documents, notifications, audit

- `Document` — owner, private file, original name, MIME type, size, checksum, purpose, soft-delete state.
- `Notification` — in-app message with category, level, read state and optional local URL.
- `EmailPreference` — per-user category opt-in.
- `EmailLog` — every attempt, rendered HTML/text, provider ID, status and error.
- `AuditLog` — actor, action, entity, summary, IP/user agent and metadata.

## 4. Public request flow

```
Browser
  → Nginx / WhiteNoise
  → Django middleware (security headers, CSP, sessions, CSRF, auth, OTP, last seen)
  → URLconf
      public views in core/jobs/institutions
      role dashboards in candidates/institutions/dashboard
  → services (jobs, applications, notifications)
  → PostgreSQL + private filesystem
```

Public jobs are read through `Job.objects.live()`, which requires all of:

- `status = published`
- `is_deleted = false`
- `deadline >= today`
- institution `verification_status = verified`
- institution `is_active = true`

This prevents a draft, expired or suspended vacancy from leaking through a stale URL, sitemap or search result. Expired job URLs return HTTP 410 with similar live roles.

## 5. Verification and job workflow

### Institution verification

```
register → pending → staff review → verified | rejected
                                      ↓
                              suspend (if later needed)
```

- Registration creates the institution, the primary recruiter and a private authorisation document in one transaction.
- Recruiters can maintain their profile and documents while pending.
- Vacancy creation and submission are blocked until the institution is verified.
- Staff decisions write `verified_at`, `verified_by`, notes and an audit entry, then notify the institution.

### Vacancy lifecycle

```
draft → pending → approved → published
   ↑        ↓         ↓          ↓
   └── rejected       └── rejected / suspended / expired
```

- Recruiters create drafts. Structural fields are required even for drafts so incomplete records cannot be submitted later.
- Submission validates the structural fields and the verification gate, records `JobStatusHistory`, notifies staff, and moves the job to `pending`.
- Staff review a checklist: institution verified, recruiter verified, advertisement/source captured, application route checked, deadline checked, eligibility checked.
- Approval moves to `approved`; publishing sets `published_at` and makes the role visible through `Job.objects.live()`.
- Rejection requires a reason and notifies the recruiter.
- Suspension hides the role immediately while preserving its history.
- A scheduled task expires roles after the deadline.

Vacancy posting is free. There is no plan limit, subscription quota or paid placement step between approval and publication; verification and the review checklist are the only gates.

## 6. Application flow

### Internal application

1. Candidate opens a live job with `application_method = internal`.
2. The candidate must be email-verified and have a candidate profile.
3. The form requires a CV, consent and an optional cover letter; supporting files are optional.
4. `submit_application` validates eligibility and prevents duplicates.
5. The service stores an immutable JSON snapshot of the candidate profile, links the documents, creates status history and notifies the institution.
6. Recruiters can move an application through a controlled state machine:
   `submitted → under_review → shortlisted → selected | rejected`.
   Candidates can withdraw while the process is open.
7. Every transition records an actor and optional note and sends a status email.

### External application

1. The job detail page explains that the application is handled by the institution.
2. The modal discloses the institution, its official website, the exact application page and the deadline.
3. The tracked link (`/applications/click/<job_id>/`) re-checks that the job is live and the method is external, records an `ExternalClick`, then redirects to the allow-listed scheme (`https`, `http` or `mailto`).
4. FacultyNxtGen never accepts an external application on the institution's behalf.

## 7. Free recruitment model

FacultyNxtGen currently provides free academic recruitment services to registered educational institutions.

- Candidate registration, profiles, saved jobs, alerts, applications and notifications are free.
- Verified institutions can post vacancies, manage applicants and invite recruiters without a plan or payment.
- Vacancy visibility depends on the review checklist and the application deadline, not on a paid placement.
- There is no checkout, order, subscription, invoice, refund or webhook flow in the runtime code.
- The retired payment tables are dropped by a migration; no payment credentials are required for startup or operation.

## 8. Private documents

- Files are written through `PrivateDocumentStorage`, whose `url()` deliberately raises.
- Uploads are validated by extension, size, magic bytes and (for PDFs) an EOF check; images are opened and verified with Pillow.
- Optional ClamAV scanning fails closed if a scanner is configured but unreachable.
- Access is always mediated by a view:
  - owner;
  - staff;
  - recruiter for an application to their institution;
  - recruiter for institutional evidence or a notification belonging to their institution.
- Links are signed with Django's signer and bind both document ID and user ID. They expire after `DOCUMENT_DOWNLOAD_LINK_TTL` seconds (default 600).
- A valid token for one user cannot be reused by another; tampering or expiry returns 404.
- Downloads are `Content-Disposition: attachment`, `Cache-Control: private, no-store` and `X-Content-Type-Options: nosniff`.

## 9. Notifications and email

- `send_email` checks the user's `EmailPreference` before rendering.
- HTML and text bodies are rendered once and persisted on `EmailLog`, so Celery workers do not need request-scoped objects.
- Delivery uses Resend when `RESEND_API_KEY` is set; otherwise Django's configured email backend is used.
- Development runs Celery eagerly. Production queues a task after commit and falls back to synchronous delivery if the broker is unavailable.
- Missing templates are recorded as failed logs rather than raising into the request.
- In-app notifications are created by the same service layer (`notify_user`, `notify_staff`).

## 10. Search and SEO

- Public filters are composable and validated by `filter_live_jobs`; only live roles are searchable.
- Sitemap includes public pages, live jobs, verified institutions and published blog posts, with a cap per entity.
- `robots.txt` disallows private areas and points to the sitemap.
- Canonical URLs, meta descriptions, Open Graph tags and breadcrumbs are passed from views.
- `JobPosting` JSON-LD is emitted only on live, public job detail pages, with `directApply` false for external roles.
- Focused landing pages target teaching, research, institution type and state queries; empty states return 404 rather than thin pages.

## 11. Frontend and brand

- Bootstrap 5.3.3 and Bootstrap Icons 1.11.3 are vendored; Inter and Plus Jakarta Sans are self-hosted.
- The official logo is used without recolouring. Light navigation and footer surfaces use a white backing so the dark wordmark stays legible.
- Brand tokens: navy `#10264A`, blue `#087BDB`, light `#F4F7FC`.
- CSS and JavaScript are external files to satisfy CSP. Inline scripts require a nonce.
- Layouts are built on Bootstrap's responsive grid with explicit checks at 360, 375, 390, 430, 768, 1024, 1280 and 1440 px planned before launch.
- Accessibility target is WCAG 2.2 AA: skip link, landmarks, labelled controls, visible focus, error associations and reduced-motion handling.

## 12. Background work

Celery tasks:

- expire jobs hourly;
- send job alerts daily;
- deliver queued email.

Celery Beat uses the database scheduler (`django_celery_beat`) so schedules can be managed operationally. In development, eager execution avoids requiring Redis.

## 13. Design decisions and trade-offs

| Decision | Reason | Trade-off |
| --- | --- | --- |
| Modular monolith | Transactional consistency and simpler operations | Requires discipline to keep app boundaries clean |
| PostgreSQL in production, SQLite locally | Production correctness without blocking local setup | SQLite-specific behaviour must not leak into models |
| Private filesystem storage | Simple, provider-neutral, no public URLs | Requires volume permissions and backups |
| Signed links instead of session-only checks | Shareable within one user session and auditable | Links expire; clients must request a new one |
| Status machine in services | Prevents invalid transitions from any view/admin | Services must be used consistently |
| Free launch with no payment runtime | Removes payment risk and credentials while keeping every core recruitment feature available | Future paid options would require a new, separately reviewed module |
| Server-rendered templates | SEO, accessibility and fast first paint | Less interactive than a SPA |
| Render email bodies at send time | Async workers stay independent of request objects | Rendered HTML is stored and must be handled as personal data |

## 14. Testing strategy

- Django `TestCase` per app, using shared factories in `apps/core/testing.py`.
- Service-level tests for workflow, permissions and free-launch regressions.
- View-level tests for status codes, redirects, scoping and template rendering.
- File tests use a temporary private storage location and real PDF bytes.
- Email tests assert persisted rendered bodies, suppression and failure handling.
- Public tests cover SEO endpoints, newsletter double opt-in and custom error pages.

The suite currently runs on SQLite. PostgreSQL-specific constraints are written in standard Django syntax and should also be exercised in staging against PostgreSQL.
