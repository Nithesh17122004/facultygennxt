# Security model

This document describes the controls implemented in the codebase and the operational steps required to keep them effective. It is not a certification or a substitute for an independent penetration test before launch.

## 1. Threat model

Primary assets:

- candidate identity, academic records, CVs and supporting documents;
- institution verification evidence and recruiter accounts;
- staff accounts with moderation powers;
- audit history and platform integrity signals.

Primary threats:

- account takeover through credential stuffing or weak passwords;
- unauthorised access to private candidate or institutional documents;
- fake institutions or fraudulent vacancies;
- malicious file uploads;
- privilege escalation between candidate, recruiter and staff roles;
- scraping, spam and denial of service against public forms;
- data leakage through URLs, logs, email or error pages.

## 2. Authentication and account security

- Custom email-based user model; email addresses are normalised and unique.
- Passwords are hashed with **Argon2** first, with Django's PBKDF2/BCrypt fallbacks configured.
- Password policy: minimum 10 characters plus Django's similarity, common-password and numeric validators.
- Email verification is required before sensitive candidate actions.
- Login lockout after `LOGIN_MAX_FAILED_ATTEMPTS` (default 5) for `LOGIN_LOCKOUT_MINUTES` (default 15).
- Session cookies are `HttpOnly`, `SameSite=Lax`, named `fng_session`, and expire after 8 hours by default. Secure cookies are forced in production.
- Password reset uses Django's signed, time-limited token flow; reset emails are logged like all other email.
- Password changes and account deletion require the current password and re-authentication.
- Staff MFA uses TOTP (`django-otp`) with QR provisioning. In production `MFA_REQUIRED_FOR_STAFF=True` blocks staff without a confirmed device. Staff with a confirmed device must verify it before using the console.
- Django admin requires staff status; custom add/change forms avoid password-field mistakes.

## 3. Authorisation

- Role decorators guard every dashboard and mutating endpoint.
- Institution-scoped queries always join through `Recruiter` membership; a recruiter cannot read another institution's jobs, applicants or documents.
- Candidate objects are filtered by the owning user.
- Staff access is explicit via `is_staff`, not merely `is_superuser`.
- Object-level document checks are centralised in `user_can_access_document`.
- Sensitive views use POST for state changes and CSRF protection.
- IDOR tests cover cross-institution applications and cross-user documents.

## 4. CSRF, XSS and injection

- Django's CSRF middleware is enabled for all state-changing requests; templates use `{% csrf_token %}`.
- `CSRF_TRUSTED_ORIGINS` is mandatory in production; secure CSRF cookies are enabled there.
- Templates auto-escape by default. User content is not marked safe unless it is system-generated (for example the salary formatter).
- The `JobPosting` JSON-LD payload escapes `<` to prevent script-context breakout.
- Content Security Policy:
  - `default-src 'self'`
  - scripts only from self plus a per-request nonce;
  - no `unsafe-eval`;
  - frames restricted to self;
  - `object-src 'none'`, `base-uri 'self'`, `form-action 'self'`, `frame-ancestors 'none'`.
- `style-src` allows inline styles because the templates use a small number of layout attributes; scripts do not rely on inline execution without a nonce.
- ORM queries are parameterised by Django. Raw SQL is not used for user-controlled filters.
- All public filter values are validated/coerced before use.

## 5. Rate limiting and abuse controls

`django-ratelimit` protects public and authenticated endpoints. Examples:

| Endpoint | Limit |
| --- | --- |
| Candidate registration | 6/hour per IP |
| Login | 20/minute per IP plus account lockout |
| Password reset request | 6/hour per IP |
| Email verification resend | 5/hour per IP |
| Contact form | 5/hour per IP |
| Newsletter subscribe | 5/hour per IP |
| Institution registration | 5/hour per IP |
| Job report | 12/minute per IP |
| Search | 60/minute per IP |
| External click | 60/minute per IP |
| Data export | 3/hour per user |

In production the cache must be Redis. LocMem is acceptable only for a single-process development server and does not coordinate limits across workers.

Contact, newsletter and institution forms include a hidden honeypot field that is added at form initialisation and rejected when populated.

## 6. File upload security

- Accepted documents: PDF, JPG/JPEG, PNG. Accepted images: JPG/JPEG, PNG, WEBP.
- Size limits: 5 MB documents, 2 MB images (configurable).
- Validation checks extension, size, magic bytes and real content:
  - PDFs must start with `%PDF-` and contain `%%EOF` near the end;
  - images are opened and verified with Pillow;
  - images must be at least 32×32 pixels.
- Filenames are replaced with random keys; the original name is stored as metadata only.
- Files are stored outside the public media root and served only by a guarded view.
- Optional ClamAV `INSTREAM` scanning is supported. If `CLAMAV_HOST` is set but the scanner is unreachable, the upload is rejected (fail closed).
- Downloads:
  - require authentication;
  - require a signed token bound to both document and user;
  - expire after `DOCUMENT_DOWNLOAD_LINK_TTL` seconds;
  - are sent as attachments with `nosniff` and no-store caching;
  - are audit-logged.
- Soft deletion removes the physical file and keeps a tombstone record.

## 7. Retired payment surface

FacultyNxtGen is a free academic recruitment platform. The payment runtime has been removed rather than merely hidden.

- `/payments/` is not routed; the `payments` URL namespace and all checkout, order, invoice, refund and webhook endpoints no longer exist.
- `apps.payments` is installed only so migration `0002_remove_payment_models` can drop the legacy plan, order, payment, invoice, refund, advertisement and subscription tables on existing databases. It exposes no models, views, URLs, admin, forms, tasks or services.
- No payment credentials, gateway keys, webhook secrets, GST settings or billing addresses are required for startup or operation.
- Job publication depends only on institution verification and the staff review checklist. There is no paid placement, featured flag or subscription quota in the schema.
- If payment code is ever reintroduced, it must be a new, separately reviewed module with server-side order creation, signature verification, idempotent fulfilment and its own threat model.

## 8. Transport and response headers

Production settings enforce:

- HTTPS redirect (`SECURE_SSL_REDIRECT=True`);
- HSTS for one year with subdomains and preload (review before enabling preload);
- secure session and CSRF cookies;
- `X-Content-Type-Options: nosniff`;
- `X-Frame-Options: DENY` plus CSP `frame-ancestors 'none'`;
- strict-origin-when-cross-origin referrer policy;
- Cross-Origin-Opener-Policy `same-origin`;
- Permissions-Policy disabling camera, microphone, geolocation, USB and interest cohorts.

`SECURE_PROXY_SSL_HEADER` and `USE_X_FORWARDED_HOST` assume a trusted reverse proxy that overwrites forwarded headers. Do not expose Gunicorn directly to the internet.

## 9. Secrets and configuration

- All secrets come from environment variables loaded by `config/settings/env.py`.
- Production refuses to start without a 40+ character `DJANGO_SECRET_KEY`, allowed hosts, CSRF trusted origins and PostgreSQL.
- `.env` is ignored by version control; `.env.example` contains placeholders only.
- Database, Redis, email, Resend, Sentry and ClamAV credentials should be stored in a managed secret store in production.
- Rotate secrets on staff departure, suspected exposure or provider compromise. Rotating `DJANGO_SECRET_KEY` invalidates sessions and signed document links.

## 10. Privacy and data protection

- Candidate documents are private by default and never exposed through `MEDIA_URL`.
- Recruiters see a candidate's CV only when the candidate applies to their vacancy.
- Marketing email requires explicit opt-in; every marketing message includes a signed unsubscribe link.
- Newsletter subscriptions use double opt-in.
- Data export produces a machine-readable archive of the candidate's own data.
- Account deletion creates a reviewable request, removes or anonymises personal data according to the retention policy, and preserves records that must be retained by law.
- Audit logs are retained for 730 days by default; candidate retention is 365 days by default. Both are configurable.
- Logs avoid passwords, OTPs and full document contents. Sentry is configured with `send_default_pii=False`.
- Privacy, terms, disclaimer, cookie preferences and contact routes are public and linked in the footer.

## 11. Audit and monitoring

`AuditLog` records security-relevant actions with actor, action, entity, summary, IP, user agent and metadata. Examples: document download/delete, contact enquiry, institution decisions, job workflow and user moderation.

- Staff can review audit entries in the custom console.
- Sensitive admin registrations are read-only where appropriate.
- Security events go to a dedicated rotating `logs/security.log` and to the console in production.
- Sentry is optional; configure `SENTRY_DSN` and review the sample rate.
- Monitor failed logins, rate-limit 429s, email failures and private-document 403/404 spikes.

## 12. Known residual risks and pre-launch actions

- No live Resend credentials have been exercised in this environment. Verify the sending domain and deliverability before launch.
- ClamAV is optional and disabled unless configured. Enable it in production if untrusted uploads are accepted.
- No WAF or bot-management service is included. Consider one for public traffic.
- CSP allows inline styles; review whether the remaining inline style attributes can be removed.
- SQLite is used locally. Staging and production must run PostgreSQL and the full test suite there, including constraint behaviour.
- Complete an independent penetration test and accessibility audit before processing real candidate data at scale.
- Verify backups, restore drills, private-media permissions and secret rotation procedures.

## 13. Production security checklist

- [ ] `DJANGO_SETTINGS_MODULE=config.settings.production`
- [ ] Strong, unique `DJANGO_SECRET_KEY`
- [ ] `DJANGO_ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` set to real HTTPS hosts
- [ ] PostgreSQL with TLS and least-privilege credentials
- [ ] Redis with authentication/private network
- [ ] `MFA_REQUIRED_FOR_STAFF=True`
- [ ] HTTPS termination and HSTS verified
- [ ] `collectstatic` run; WhiteNoise manifest storage active
- [ ] Private media on a non-public volume with correct ownership
- [ ] ClamAV enabled or a documented acceptance of the residual risk
- [ ] Resend domain, SPF, DKIM and DMARC configured
- [ ] Sentry/alerting configured and tested
- [ ] Backups encrypted, monitored and restore-tested
- [ ] Audit and security log retention configured
- [ ] Free-launch messaging and legal pages reviewed by counsel
- [ ] Dependency and container image scanning in CI
- [ ] Penetration test completed and findings resolved
