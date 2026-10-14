# Gmail API OAuth Email Delivery Implementation Report

## Executive Summary
This document summarizes the implementation and verification of platform email delivery via the Google Gmail API using OAuth 2.0 with the `https://www.googleapis.com/auth/gmail.send` scope. The implementation preserves full backward compatibility with the existing `NotificationService` and Django's standard `send_mail()` / `EmailMessage` abstractions, while ensuring production-grade security, token encryption at rest, tenant isolation, and zero token exposure to the frontend.

---

## 1. Files Changed & Added

### Modified Existing Files
1. [`backend/apps/notifications/models.py`](file:///d:/hrms/hrms/backend/apps/notifications/models.py)
   - Imported `PlatformEmailCredential` from `.gmail_models` to ensure standard Django model discovery and migration tracking.
2. [`backend/config/settings.py`](file:///d:/hrms/hrms/backend/config/settings.py)
   - Added configuration settings read from environment variables:
     - `GOOGLE_OAUTH_CLIENT_ID`
     - `GOOGLE_OAUTH_CLIENT_SECRET`
     - `GOOGLE_OAUTH_REDIRECT_URI`
     - `PLATFORM_EMAIL_ADDRESS`
     - `GMAIL_ENCRYPTION_KEY`
3. [`backend/config/urls.py`](file:///d:/hrms/hrms/backend/config/urls.py)
   - Registered `path('api/v1/auth/', include('apps.notifications.gmail_urls'))` under the API v1 auth route namespace.
4. [`backend/requirements/base.txt`](file:///d:/hrms/hrms/backend/requirements/base.txt)
   - Added `cryptography` dependency for Fernet symmetric encryption.

### Newly Created Files
1. [`backend/apps/notifications/gmail_models.py`](file:///d:/hrms/hrms/backend/apps/notifications/gmail_models.py)
   - Defines `PlatformEmailCredential` model with Fernet-encrypted refresh token storage and helper methods (`set_refresh_token`, `get_refresh_token`, `mark_used`, `get_active_credential`).
2. [`backend/apps/notifications/gmail_backend.py`](file:///d:/hrms/hrms/backend/apps/notifications/gmail_backend.py)
   - Subclasses Django's `BaseEmailBackend` (`GmailAPIEmailBackend`). Refreshes access tokens via Google OAuth token endpoint, constructs RFC 2822 MIME messages (supporting plain text and HTML multipart), and sends via `https://gmail.googleapis.com/gmail/v1/users/me/messages/send`.
3. [`backend/apps/notifications/gmail_views.py`](file:///d:/hrms/hrms/backend/apps/notifications/gmail_views.py)
   - Implements `GmailAuthorizeView` and `GmailCallbackView` with cryptographically secure session-bound CSRF state, superuser authorization enforcement, authorized email matching, and error handling.
4. [`backend/apps/notifications/gmail_urls.py`](file:///d:/hrms/hrms/backend/apps/notifications/gmail_urls.py)
   - URL routing for `google/authorize/` and `google/callback/`.
5. [`backend/apps/notifications/migrations/0007_platformemailcredential.py`](file:///d:/hrms/hrms/backend/apps/notifications/migrations/0007_platformemailcredential.py)
   - Database migration establishing table `notifications_platformemailcredential`.
6. [`backend/apps/notifications/tests_gmail.py`](file:///d:/hrms/hrms/backend/apps/notifications/tests_gmail.py)
   - Comprehensive test suite covering OAuth state validation, callback handling, encryption/decryption round-tripping, token refresh failure/revocation, MIME structure construction, and `NotificationService` integration.

---

## 2. Models and Migrations Added

### Model: `PlatformEmailCredential` (`apps.notifications.gmail_models`)
- `id`: BigAutoField (primary key)
- `email`: `EmailField` — The Gmail address authorized as platform sender.
- `encrypted_refresh_token`: `TextField` — Fernet-encrypted OAuth2 refresh token at rest.
- `token_scope`: `CharField(max_length=255)` — Default `https://www.googleapis.com/auth/gmail.send`.
- `is_active`: `BooleanField(default=True)` — Whether this credential is the active platform sender.
- `authorized_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=SET_NULL, null=True, blank=True)` — Superuser audit trace.
- `authorized_at`: `DateTimeField(null=True, blank=True)` — Timestamp of authorization completion.
- `last_used_at`: `DateTimeField(null=True, blank=True)` — Timestamp of last email dispatch.
- `created_at` / `updated_at`: `DateTimeField(auto_now_add=True / auto_now=True)`

### Migration: `notifications.0007_platformemailcredential`
- Applied cleanly to PostgreSQL database.

---

## 3. Exact Authorization and Callback Routes

| Method | Endpoint | Permission | Description |
|---|---|---|---|
| `GET` | `/api/v1/auth/google/authorize/` | `IsAuthenticated` + `is_superuser=True` | Generates CSRF state token, binds state to user session, and returns the Google OAuth consent URL. |
| `GET` | `/api/v1/auth/google/callback/` | `IsAuthenticated` + `is_superuser=True` | Validates session CSRF state, exchanges authorization code for tokens, verifies authorized Gmail address against `PLATFORM_EMAIL_ADDRESS`, encrypts refresh token, and stores credential in DB. |

---

## 4. API Contracts

### Endpoint 1: Initiate OAuth Flow
- **URL**: `GET /api/v1/auth/google/authorize/`
- **Headers**: `Authorization: Token <superuser_token>`
- **Response (200 OK)**:
  ```json
  {
    "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?client_id=...&redirect_uri=https%3A%2F%2Fbeyondsure-hrms-backend.onrender.com%2Fapi%2Fv1%2Fauth%2Fgoogle%2Fcallback%2F&response_type=code&scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fgmail.send+openid+email&access_type=offline&prompt=consent&state=<session_csrf_state>",
    "detail": "Redirect the browser to the authorization_url to complete OAuth."
  }
  ```
- **Error Responses**:
  - `401 Unauthorized`: Missing or invalid session/token.
  - `403 Forbidden`: Authenticated user is not platform superuser (`request.user.is_superuser is False`).
  - `500 Internal Server Error`: `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, or `GOOGLE_OAUTH_REDIRECT_URI` missing.

### Endpoint 2: Handle OAuth Callback
- **URL**: `GET /api/v1/auth/google/callback/?code=<code>&state=<state>`
- **Query Parameters**:
  - `code` (string, required): Authorization code issued by Google.
  - `state` (string, required): Cryptographic state generated during authorization.
- **Headers**: Session cookie or `Authorization: Token <superuser_token>`.
- **Response (200 OK)**:
  ```json
  {
    "detail": "Gmail API authorization successful.",
    "email": "noreply@beyondsure.com",
    "scope": "https://www.googleapis.com/auth/gmail.send"
  }
  ```
- **Error Responses**:
  - `400 Bad Request`: Missing `code` or `state`, error response from Google, or no refresh token returned.
  - `403 Forbidden`: CSRF state mismatch, session user mismatch, regular user, or authorized email mismatch with `PLATFORM_EMAIL_ADDRESS`.
  - `502 Bad Gateway`: Upstream Google token exchange or userinfo request failure.

---

## 5. Required Render Environment Variable Names
The following environment variables must be configured in Render dashboard for `beyondsure-hrms-backend`:

| Variable Name | Required | Description |
|---|---|---|
| `EMAIL_BACKEND` | Optional | Set to `apps.notifications.gmail_backend.GmailAPIEmailBackend` to activate Gmail API delivery. |
| `GOOGLE_OAUTH_CLIENT_ID` | Yes | Google Cloud OAuth 2.0 Web Client ID (`*.apps.googleusercontent.com`). |
| `GOOGLE_OAUTH_CLIENT_SECRET` | Yes | Google Cloud OAuth 2.0 Client Secret. |
| `GOOGLE_OAUTH_REDIRECT_URI` | Yes | Must be `https://beyondsure-hrms-backend.onrender.com/api/v1/auth/google/callback/`. |
| `PLATFORM_EMAIL_ADDRESS` | Yes | Authorized platform sending address (e.g. `noreply@beyondsure.com`). |
| `GMAIL_ENCRYPTION_KEY` | Recommended | Dedicated 256-bit secret string for Fernet encryption key derivation (defaults to `SECRET_KEY` if omitted). |

---

## 6. Required Google Cloud Settings
In the Google Cloud Console (under APIs & Services):
1. **OAuth Consent Screen**:
   - Publishing Status: "Testing" (add operator email as Test User) or "In Production" (internal/verified).
   - Scopes requested:
     - `https://www.googleapis.com/auth/gmail.send`
     - `openid`
     - `email`
2. **OAuth 2.0 Client ID (Web Application)**:
   - **Authorized redirect URIs**:
     - `https://beyondsure-hrms-backend.onrender.com/api/v1/auth/google/callback/`
     - `http://localhost:8000/api/v1/auth/google/callback/` (for local development/testing)

---

## 7. Verification Tests Run & Results

| Test Suite | Tests Run | Result | Key Capabilities Verified |
|---|---|---|---|
| `apps.notifications.tests_gmail` | 29 | **29/29 PASSED (OK)** | Superuser authorization restrictions, CSRF state verification, Google error handling, code exchange, authorized email validation, refresh token Fernet roundtrip & wrong-key resilience, token refresh failure handling, RFC 2822 MIME generation, batch dispatch, and NotificationService integration. |
| `apps.notifications` (full) | 48 | **48/48 PASSED (OK)** | In-app notifications, announcement delivery, acknowledgment tracking, API serializers/views, and Gmail OAuth integration. |
| `apps.accounts` (full) | 49 | **49/49 PASSED (OK)** | Super Admin verification tokens, expiry & single-use enforcement, password reset token expiry & privacy, authentication & session security. |
| `apps.organization.tests_invitations` | 14 | **14/14 PASSED (OK)** | Organization admin invitation workflow, token creation, acceptance, and role assignment. |

---

## 8. Security Limitations & Human Setup Required
- **No plaintext token storage**: Refresh tokens are encrypted at rest with Fernet.
- **Zero frontend token exposure**: All authorization code exchanges occur strictly server-side; tokens are never transmitted to the browser or client-side application.
- **Human Setup Required**:
  1. Add the Render environment variables listed in Section 5.
  2. Ensure the redirect URI in Google Cloud Console matches `https://beyondsure-hrms-backend.onrender.com/api/v1/auth/google/callback/`.
  3. A platform superuser must log in and trigger `GET /api/v1/auth/google/authorize/`, visit the returned `authorization_url` to consent, and complete the one-time OAuth link.
