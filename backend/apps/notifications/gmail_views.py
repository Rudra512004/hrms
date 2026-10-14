"""
Gmail API OAuth2 views for platform email authorization.

Provides two endpoints:
  GET  /api/v1/auth/google/authorize/  — Initiates the OAuth flow
  GET  /api/v1/auth/google/callback/   — Handles the OAuth callback

Security:
  - Only platform superusers (is_superuser=True) can initiate the flow.
  - CSRF state parameter is generated cryptographically and validated.
  - State is bound to the requesting user's session.
  - Authorization code is exchanged server-side; tokens never reach the frontend.
  - Refresh tokens are encrypted before database storage.
"""

import hashlib
import json
import logging
import secrets
import urllib.parse
import urllib.request

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

# Gmail API OAuth configuration
GOOGLE_AUTH_URI = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URI = 'https://oauth2.googleapis.com/token'
GOOGLE_USERINFO_URI = 'https://www.googleapis.com/oauth2/v3/userinfo'
GMAIL_SEND_SCOPE = 'https://www.googleapis.com/auth/gmail.send'
USERINFO_EMAIL_SCOPE = 'openid email'


def _get_oauth_config():
    """Retrieve OAuth client configuration from Django settings."""
    client_id = getattr(settings, 'GOOGLE_OAUTH_CLIENT_ID', '')
    client_secret = getattr(settings, 'GOOGLE_OAUTH_CLIENT_SECRET', '')
    redirect_uri = getattr(settings, 'GOOGLE_OAUTH_REDIRECT_URI', '')

    if not all([client_id, client_secret, redirect_uri]):
        return None
    return {
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri,
    }


class GmailAuthorizeView(APIView):
    """
    GET /api/v1/auth/google/authorize/

    Initiates the Google OAuth2 authorization flow for Gmail API access.
    Generates a CSRF state token, stores it in the user's session, and
    returns the Google authorization URL for the frontend to redirect to.

    Only platform superusers may initiate this flow.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Only superusers may authorize the platform email sender
        if not request.user.is_superuser:
            return JsonResponse(
                {'detail': 'Only platform administrators can configure email delivery.'},
                status=403,
            )

        config = _get_oauth_config()
        if not config:
            return JsonResponse(
                {'detail': 'Google OAuth client is not configured. Set GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET, and GOOGLE_OAUTH_REDIRECT_URI.'},
                status=500,
            )

        # Generate cryptographic CSRF state
        state = secrets.token_urlsafe(32)

        # Bind state to the current session
        request.session['gmail_oauth_state'] = state
        request.session['gmail_oauth_user_id'] = request.user.pk
        request.session.modified = True

        # Build the Google OAuth authorization URL
        params = urllib.parse.urlencode({
            'client_id': config['client_id'],
            'redirect_uri': config['redirect_uri'],
            'response_type': 'code',
            'scope': f'{GMAIL_SEND_SCOPE} {USERINFO_EMAIL_SCOPE}',
            'access_type': 'offline',
            'prompt': 'consent',
            'state': state,
        })

        auth_url = f'{GOOGLE_AUTH_URI}?{params}'

        return JsonResponse({
            'authorization_url': auth_url,
            'detail': 'Redirect the browser to the authorization_url to complete OAuth.',
        })


class GmailCallbackView(APIView):
    """
    GET /api/v1/auth/google/callback/?code=...&state=...

    Handles the OAuth2 callback from Google. Validates the CSRF state,
    exchanges the authorization code for tokens, encrypts the refresh
    token, and stores it in the database.

    Security:
    - State parameter must match the session-stored value.
    - Authorization code is exchanged server-side via HTTPS POST.
    - Only the refresh token is stored (encrypted); access tokens are transient.
    - The authorized Gmail address is verified via the userinfo endpoint.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        error = request.query_params.get('error')
        if error:
            logger.warning("Gmail OAuth callback received error: %s", error)
            return JsonResponse(
                {'detail': f'Authorization denied: {error}'},
                status=400,
            )

        code = request.query_params.get('code')
        state = request.query_params.get('state')

        if not code or not state:
            return JsonResponse(
                {'detail': 'Missing authorization code or state parameter.'},
                status=400,
            )

        # Validate CSRF state
        expected_state = request.session.get('gmail_oauth_state')
        expected_user_id = request.session.get('gmail_oauth_user_id')

        if not expected_state or state != expected_state:
            logger.warning(
                "Gmail OAuth state mismatch. Expected=%s, Received=%s",
                expected_state, state,
            )
            return JsonResponse(
                {'detail': 'Invalid state parameter. Please restart the authorization flow.'},
                status=403,
            )

        if expected_user_id != request.user.pk:
            logger.warning(
                "Gmail OAuth user mismatch. Session user=%s, Request user=%s",
                expected_user_id, request.user.pk,
            )
            return JsonResponse(
                {'detail': 'Session user mismatch. Please restart the authorization flow.'},
                status=403,
            )

        # Only superusers may complete the flow
        if not request.user.is_superuser:
            return JsonResponse(
                {'detail': 'Only platform administrators can configure email delivery.'},
                status=403,
            )

        # Clear the state from session (single-use)
        request.session.pop('gmail_oauth_state', None)
        request.session.pop('gmail_oauth_user_id', None)
        request.session.modified = True

        config = _get_oauth_config()
        if not config:
            return JsonResponse(
                {'detail': 'Google OAuth client is not configured.'},
                status=500,
            )

        # Exchange authorization code for tokens
        token_data = urllib.parse.urlencode({
            'code': code,
            'client_id': config['client_id'],
            'client_secret': config['client_secret'],
            'redirect_uri': config['redirect_uri'],
            'grant_type': 'authorization_code',
        }).encode('utf-8')

        try:
            token_request = urllib.request.Request(
                GOOGLE_TOKEN_URI,
                data=token_data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                method='POST',
            )
            with urllib.request.urlopen(token_request, timeout=15) as resp:
                token_response = json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            logger.error("Failed to exchange authorization code: %s", str(e))
            return JsonResponse(
                {'detail': 'Failed to exchange authorization code with Google.'},
                status=502,
            )

        access_token = token_response.get('access_token')
        refresh_token = token_response.get('refresh_token')

        if not refresh_token:
            return JsonResponse(
                {'detail': 'No refresh token received. Revoke app access in Google account settings and retry with prompt=consent.'},
                status=400,
            )

        if not access_token:
            return JsonResponse(
                {'detail': 'No access token received from Google.'},
                status=502,
            )

        # Fetch the authorized email address via userinfo
        try:
            userinfo_request = urllib.request.Request(
                GOOGLE_USERINFO_URI,
                headers={'Authorization': f'Bearer {access_token}'},
                method='GET',
            )
            with urllib.request.urlopen(userinfo_request, timeout=10) as resp:
                userinfo = json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            logger.error("Failed to fetch Google userinfo: %s", str(e))
            return JsonResponse(
                {'detail': 'Failed to verify the authorized email address.'},
                status=502,
            )

        authorized_email = userinfo.get('email', '')
        if not authorized_email:
            return JsonResponse(
                {'detail': 'Could not determine the authorized Gmail address.'},
                status=400,
            )

        # Validate against the configured platform sender
        expected_email = getattr(settings, 'PLATFORM_EMAIL_ADDRESS', '')
        if expected_email and authorized_email.lower() != expected_email.lower():
            logger.warning(
                "Authorized email %s does not match PLATFORM_EMAIL_ADDRESS %s",
                authorized_email, expected_email,
            )
            return JsonResponse(
                {'detail': f'The authorized email ({authorized_email}) does not match the configured platform sender ({expected_email}). Authorize the correct account.'},
                status=403,
            )

        # Store encrypted credentials
        from .gmail_models import PlatformEmailCredential

        # Deactivate all existing credentials
        PlatformEmailCredential.objects.filter(is_active=True).update(is_active=False)

        credential = PlatformEmailCredential(
            email=authorized_email,
            token_scope=GMAIL_SEND_SCOPE,
            is_active=True,
            authorized_by=request.user,
            authorized_at=timezone.now(),
        )
        credential.set_refresh_token(refresh_token)
        credential.save()

        logger.info(
            "Gmail API credentials stored for %s by superuser %s",
            authorized_email, request.user.email,
        )

        return JsonResponse({
            'detail': 'Gmail API authorization successful.',
            'email': authorized_email,
            'scope': GMAIL_SEND_SCOPE,
        })
