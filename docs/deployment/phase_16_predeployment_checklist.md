# Phase 16A — Pre-Deployment Review & Infrastructure Readiness Checklist
# BEYONDSURE HRMS

**Generated:** 2026-10-12  
**Target Environment:** Render Cloud, AWS S3, Managed PostgreSQL, SMTP Provider  
**Audited Working Branch:** `dev2`  
**Integration Branch:** `main`  
**Current HEAD Commit:** `d7fcbe5` — *chore: preserve current HRMS development state*  
**Auditor / Reviewer:** Pre-Deployment Review & Infrastructure Governance

---

## 1. Reviewed Deployment Branch & Release Strategy

### 1.1 Branch Architecture & Environment Mapping
- **Development & Feature Branches:** `dev1` (Backend/APIs/DB), `dev2` (Frontend/Routing/UI).
- **Integration Branch:** `main` (Protected stable trunk).
- **Staging / Preview Environment:** Deployed from `dev2` (or dedicated staging branch) via Render Preview Blueprint.
- **Production Environment:** **MUST deploy strictly from `main`**.

### 1.2 Promotion & PR Review Workflow
1. Feature work on `dev1` or `dev2` is verified locally (Django checks, backend tests, frontend tests, and TypeScript build).
2. Pull Request submitted targeting `main`.
3. Automated GitHub Actions CI workflow triggers on PR:
   - Backend checks (`check`, SQLite in-memory test suite).
   - Frontend validation (`vitest run`, `tsc --noEmit`, `vite build`).
4. Mandatory code review and sign-off by team counterpart (Dev1 reviews Dev2 PRs; Dev2 reviews Dev1 PRs).
5. Merge into `main` using squash or rebase merge.
6. Render Production Web Service & Static Site auto-deploy triggered from `main`.

> [!WARNING]
> In `render.yaml`, `branch: dev2` is currently set for development/staging evaluation. For production deployment, `branch` must be updated to `main` to enforce release governance and prevent unreviewed developer commits from reaching production.

---

## 2. Render Cloud Resources Required

| Resource Type | Resource Name | Purpose | Recommended Plan | Specifications |
| :--- | :--- | :--- | :--- | :--- |
| **PostgreSQL Database** | `beyondsure-postgres` | Multi-tenant persistent relational database | `starter` (or higher) | PostgreSQL 16, persistent SSD, connection pooling enabled. *Avoid `free` plan in production due to 30-day auto-expiry and lack of backups.* |
| **Web Service** | `beyondsure-hrms-backend` | Django REST Framework API server | `starter` / `standard` | Python 3.12, 512 MB+ RAM, Gunicorn WSGI/ASGI, WhiteNoise static file handling. |
| **Static Site** | `beyondsure-hrms-frontend` | React 19 + Vite Single Page Application | `starter` (Static) | Global CDN, SPA rewrite rule (`/* -> /index.html`). |

---

## 3. PostgreSQL Provisioning & Migration Procedure

### 3.1 Provisioning Steps
1. Create Render PostgreSQL instance in the same cloud region as the Web Service (e.g., `oregon` or `frankfurt`) to minimize network latency.
2. Ensure connection string is linked to the backend Web Service via `DATABASE_URL` environment variable using Render's `fromDatabase` directive.
3. Verify connection pooling parameters in Django `settings.py`:
   - `conn_max_age = 600`
   - `conn_health_checks = True`

### 3.2 Automated Release Migration Sequence
During deployment, `backend/build.sh` automatically executes:
```bash
set -o errexit
pip install -r requirements/production.txt
python manage.py collectstatic --no-input
python manage.py migrate --noinput
python manage.py bootstrap_demo_superadmin
```
- Migrations run non-interactively prior to Gunicorn boot.
- If a migration raises an unhandled exception, `build.sh` halts immediately (`set -o errexit`), preventing the unhealthy build from swapping into live traffic.

### 3.3 Zero-Downtime Migration Policy
- **Additive Schema Changes:** Adding nullable columns, new tables, or new indexes can be deployed directly.
- **Destructive / Column Removal Changes:** Must follow a two-phase release:
  1. Release 1: Remove model field references in Django code.
  2. Release 2: Remove the database column via migration once Release 1 is fully active.

---

## 4. Required Environment Variables Specification

*Never commit actual secret values to Git or store them in public repositories. Inject all secrets exclusively via the hosting provider dashboard.*

### 4.1 Backend Web Service Environment Variables

| Variable Name | Required Value / Source | Secret? | Description |
| :--- | :--- | :---: | :--- |
| `DJANGO_DEBUG` | `False` | No | Disables debug mode and detailed tracebacks. |
| `DJANGO_SECRET_KEY` | High-entropy random string (min 50 chars) | **YES** | Cryptographic signing key for sessions, tokens, and CSRF. |
| `DATABASE_URL` | Auto-populated by Render Blueprint | **YES** | Connection URI for Managed PostgreSQL. |
| `DJANGO_ALLOWED_HOSTS` | `.onrender.com,api.yourdomain.com` | No | Permitted HTTP Host headers. |
| `DJANGO_CORS_ALLOWED_ORIGINS`| `https://app.yourdomain.com` (leave empty for default `.onrender.com`) | No | Whitelisted CORS browser origins. |
| `DJANGO_CSRF_TRUSTED_ORIGINS`| `https://app.yourdomain.com` (leave empty for default `.onrender.com`) | No | Whitelisted CSRF trusted origins. |
| `FRONTEND_URL` | Auto-populated by Render Blueprint (`host` property) | No | Canonical frontend URL for links and CORS. |
| `RENDER_EXTERNAL_HOSTNAME`| Auto-injected by Render | No | Backend service public hostname. |
| `DEMO_SUPERADMIN_EMAIL` | e.g., `admin@beyondsure.com` | **YES** | Initial bootstrap administrator email. |
| `DEMO_SUPERADMIN_PASSWORD` | Strong password (min 14 chars) | **YES** | Initial bootstrap administrator password. |
| `AWS_ACCESS_KEY_ID` | IAM service user Access Key ID | **YES** | AWS credential for S3 document storage. |
| `AWS_SECRET_ACCESS_KEY` | IAM service user Secret Access Key | **YES** | AWS credential for S3 document storage. |
| `AWS_STORAGE_BUCKET_NAME`| e.g., `beyondsure-hrms-documents` | No | S3 private bucket name. |
| `AWS_S3_REGION_NAME` | e.g., `ap-south-1` or `us-east-1` | No | S3 bucket region. |
| `EMAIL_BACKEND` | `django.core.mail.backends.smtp.EmailBackend` | No | Django email backend for transactional emails. |
| `EMAIL_HOST` | e.g., `smtp.sendgrid.net` or `email-smtp.us-east-1.amazonaws.com` | No | SMTP provider hostname. |
| `EMAIL_PORT` | `587` | No | SMTP port (STARTTLS). |
| `EMAIL_USE_TLS` | `True` | No | Enforces TLS transport security for emails. |
| `EMAIL_HOST_USER` | Provider SMTP username / API key identifier | **YES** | SMTP authentication identity. |
| `EMAIL_HOST_PASSWORD` | Provider SMTP password / API token | **YES** | SMTP authentication secret. |
| `DEFAULT_FROM_EMAIL` | e.g., `notifications@beyondsure.com` | No | Outgoing email address from verified domain. |

### 4.2 Frontend Static Site Environment Variables

| Variable Name | Required Value / Source | Secret? | Description |
| :--- | :--- | :---: | :--- |
| `VITE_API_BASE_URL` | Auto-populated by Render Blueprint (`host` property) or `https://api.yourdomain.com` | No | API base URL injected into client bundle at build time. |

---

## 5. Private S3 & Least-Privilege IAM Configuration

### 5.1 S3 Bucket Hardening
- **Bucket Name:** `beyondsure-hrms-documents` (globally unique).
- **Public Access Block:** **Enabled on all 4 settings** (BlockPublicAcls, IgnorePublicAcls, BlockPublicPolicy, RestrictPublicBuckets).
- **Default Encryption:** Server-Side Encryption with Amazon S3 managed keys (SSE-S3 / AES256) or AWS KMS.
- **Bucket Versioning:** Recommended for disaster recovery of sensitive employee records.

### 5.2 IAM Least-Privilege Policy
Create a dedicated IAM user `beyondsure-hrms-s3-app` and attach only the following inline policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowHRMSBucketOperations",
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket"
      ],
      "Resource": "arn:aws:s3:::beyondsure-hrms-documents"
    },
    {
      "Sid": "AllowHRMSObjectOperations",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::beyondsure-hrms-documents/*"
    }
  ]
}
```

---

## 6. SMTP & Sender-Domain Verification

To ensure invitations, password resets, and approval notices are not flagged as spam:

1. **Domain Ownership & Provider Selection:** SendGrid, AWS SES, or Mailgun.
2. **DNS Records Required on Sending Domain (`beyondsure.com`):**
   - **SPF Record (TXT):**
     `v=spf1 include:sendgrid.net ~all`
   - **DKIM Records (CNAME):**
     Two to three CNAME records provided by the SMTP vendor.
   - **DMARC Record (TXT):**
     `_dmarc.beyondsure.com` -> `v=DMARC1; p=quarantine; rua=mailto:dmarc-reports@beyondsure.com`
3. **Sender Verification:** The email address configured in `DEFAULT_FROM_EMAIL` must match the verified sending domain.

---

## 7. DNS & TLS Configuration

1. **Custom Domain Setup:**
   - **Frontend App:** `app.beyondsure.com`
     - CNAME record pointing to Render Static Site URL (e.g., `beyondsure-hrms-frontend.onrender.com`).
   - **Backend API:** `api.beyondsure.com`
     - CNAME record pointing to Render Web Service URL (e.g., `beyondsure-hrms-backend.onrender.com`).
2. **Managed TLS:**
   - Render automatically provisions and renews Let's Encrypt certificates for custom domains.
3. **Application Verification:**
   - Add `api.beyondsure.com` to `DJANGO_ALLOWED_HOSTS`.
   - Add `https://app.beyondsure.com` to `DJANGO_CORS_ALLOWED_ORIGINS` and `DJANGO_CSRF_TRUSTED_ORIGINS`.

---

## 8. Initial Administrator Provisioning & Credential Rotation

1. **Bootstrap Execution:**
   - On the first deployment, `backend/build.sh` invokes `python manage.py bootstrap_demo_superadmin`.
   - Creates the superuser using `DEMO_SUPERADMIN_EMAIL` and `DEMO_SUPERADMIN_PASSWORD`.
   - Assigns zero employee profiles (headless superuser) to maintain clean RBAC separation.
2. **Verification:**
   - Log into `https://app.beyondsure.com` using the bootstrap superuser credentials.
   - Confirm access to System Administration, Organization setup, and RBAC screens.
3. **Credential Rotation Procedure:**
   - Immediately navigate to User Profile / Security and change the Super Admin password.
   - Once the administrator account is confirmed active, **remove `DEMO_SUPERADMIN_PASSWORD` from the Render Dashboard environment variables** to ensure the secret is not retained in cloud configuration.
   - Subsequent deployments will verify the existing user idempotently without modifying the rotated password.

---

## 9. Comprehensive Production Smoke Test Checklist

Execute these 10 end-to-end verification tests immediately after cloud provisioning:

| Test ID | Area | Verification Steps | Expected Result | Verified? |
| :---: | :--- | :--- | :--- | :---: |
| **ST-01** | **Health Check** | Send `GET /health/` to backend API. | HTTP 200 `{"status": "ok", "database": "ok"}`. | [ ] |
| **ST-02** | **Static Delivery** | Access root `https://app.beyondsure.com/`. Inspect Network tab. | HTTP 200, assets served with gzip/brotli, React UI mounts cleanly. | [ ] |
| **ST-03** | **Authentication** | Log in with rotated Super Admin credentials via `/api/v1/auth/login/`. | HTTP 200 with auth token; stored in `localStorage`; dashboard loaded. | [ ] |
| **ST-04** | **Tenant Isolation** | Create a new organization and invite a client owner. | Organization created; client owner isolated from other tenant data. | [ ] |
| **ST-05** | **Dynamic RBAC** | Assign custom role with limited permissions (e.g., `leave.view`, no `leave.approve`). | User can view leaves but cannot approve (HTTP 403 on approve endpoint). | [ ] |
| **ST-06** | **Attendance Flow** | Clock in employee via `/api/v1/attendance/check-in/` with valid geofence IP. | Attendance record created; external IP without WFH is blocked (HTTP 403). | [ ] |
| **ST-07** | **Leave Lifecycle** | Submit leave request -> approve as manager -> verify balance. | Balance deducted, status updated to approved, notification generated. | [ ] |
| **ST-08** | **Payroll Generation**| Execute payroll run for test pay period. | Pay run generated; line items computed; payslips rendered. | [ ] |
| **ST-09** | **Private Documents**| Upload PDF (< 5 MB) to employee profile. Attempt download as unauthorized user and authorized user. | File saved to S3. Unauthorized user receives HTTP 403/404. Authorized user receives pre-signed S3 URL. | [ ] |
| **ST-10** | **Email Notifications**| Trigger password reset request via email. | Transactional email received with valid reset token; SPF/DKIM pass. | [ ] |

---

## 10. Backup, Restore & Rollback Procedures

### 10.1 Backup Policy
1. **Automated Daily Snapshots:** Maintained by Render Managed PostgreSQL with point-in-time recovery.
2. **Pre-Release Manual Backup Command:**
   ```bash
   pg_dump -Fc -v -d "$DATABASE_URL" -f "hrms_pre_release_$(date +%Y%m%d_%H%M%S).dump"
   ```

### 10.2 Database Restore Procedure
In the event of catastrophic data corruption:
```bash
pg_restore --clean --no-acl --no-owner -d "$DATABASE_URL" "hrms_pre_release_<timestamp>.dump"
```

### 10.3 Application Rollback Procedure
1. In Render Dashboard, navigate to **Deploys**.
2. Select the previous stable deploy and click **Rollback to this deploy**.
3. If database schema was modified additively, the previous codebase will function without issue.
4. If a migration needs to be rolled back, run via Render One-Off Shell:
   ```bash
   python manage.py migrate <app_name> <previous_migration_name>
   ```

---

## 11. Evidence Required Before Declaring Production Ready

Production readiness **CANNOT** be claimed without the following tangible evidence:

- [ ] Render Web Service and Static Site build logs showing exit code 0.
- [ ] Database migration log showing all migrations applied cleanly on PostgreSQL 16.
- [ ] Live HTTP response from `https://api.yourdomain.com/health/` returning HTTP 200 with `database: ok`.
- [ ] S3 bucket object created and retrieved via pre-signed URL.
- [ ] Transactional test email received in an actual inbox with passing SPF and DKIM headers.
- [ ] Successful completion of all 10 smoke tests in Section 9 signed off by an authorized engineer.
