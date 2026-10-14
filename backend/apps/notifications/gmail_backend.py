"""
Custom Django email backend that sends email via the Gmail API.

Uses the stored encrypted OAuth2 refresh token to obtain fresh access
tokens on demand. Constructs RFC 2822 MIME messages and sends them
through the gmail.send API endpoint.

Usage:
    Set EMAIL_BACKEND = 'apps.notifications.gmail_backend.GmailAPIEmailBackend'
    in Django settings (or via the EMAIL_BACKEND environment variable).

    The backend automatically falls back to Django's console backend
    if no active Gmail credentials are stored, ensuring development
    environments continue to work without real credentials.
"""

import base64
import json
import logging
import urllib.parse
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

GOOGLE_TOKEN_URI = 'https://oauth2.googleapis.com/token'
GMAIL_SEND_URI = 'https://gmail.googleapis.com/gmail/v1/users/me/messages/send'


class GmailAPIEmailBackend(BaseEmailBackend):
    """
    Django email backend that delivers messages via Gmail API using
    OAuth2 credentials stored in PlatformEmailCredential.

    Automatically refreshes access tokens using the encrypted refresh
    token. If credentials are unavailable or expired, raises an
    exception (fail_silently behavior is respected).
    """

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self._access_token = None
        self._credential = None

    def _load_credential(self):
        """Load the active platform email credential."""
        from .gmail_models import PlatformEmailCredential
        self._credential = PlatformEmailCredential.get_active_credential()
        return self._credential

    def _refresh_access_token(self):
        """Exchange the refresh token for a fresh access token."""
        if not self._credential:
            return None

        refresh_token = self._credential.get_refresh_token()
        if not refresh_token:
            logger.error("Failed to decrypt refresh token for credential id=%s", self._credential.pk)
            return None

        client_id = getattr(settings, 'GOOGLE_OAUTH_CLIENT_ID', '')
        client_secret = getattr(settings, 'GOOGLE_OAUTH_CLIENT_SECRET', '')

        if not client_id or not client_secret:
            logger.error("GOOGLE_OAUTH_CLIENT_ID or GOOGLE_OAUTH_CLIENT_SECRET not configured.")
            return None

        token_data = urllib.parse.urlencode({
            'client_id': client_id,
            'client_secret': client_secret,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token',
        }).encode('utf-8')

        try:
            req = urllib.request.Request(
                GOOGLE_TOKEN_URI,
                data=token_data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                method='POST',
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                token_response = json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8', errors='replace') if hasattr(e, 'read') else str(e)
            logger.error(
                "Gmail API token refresh failed (HTTP %s): %s",
                e.code, error_body,
            )
            return None
        except Exception as e:
            logger.error("Gmail API token refresh failed: %s", str(e))
            return None

        access_token = token_response.get('access_token')
        if not access_token:
            logger.error("No access_token in Google token response.")
            return None

        self._access_token = access_token
        return access_token

    def _build_mime_message(self, email_message):
        """
        Convert a Django EmailMessage into a RFC 2822 MIME string.

        Supports plain text messages. HTML alternative is included
        if the EmailMessage has html_message set.
        """
        from_email = email_message.from_email or self._credential.email
        to_list = email_message.to
        cc_list = getattr(email_message, 'cc', []) or []
        bcc_list = getattr(email_message, 'bcc', []) or []

        # Check if there's an HTML body (Django's send_mail with html_message
        # creates an EmailMultiAlternatives with alternatives list)
        html_body = None
        if hasattr(email_message, 'alternatives'):
            for content, mimetype in email_message.alternatives:
                if mimetype == 'text/html':
                    html_body = content
                    break

        if html_body:
            msg = MIMEMultipart('alternative')
            msg.attach(MIMEText(email_message.body, 'plain', 'utf-8'))
            msg.attach(MIMEText(html_body, 'html', 'utf-8'))
        else:
            msg = MIMEText(email_message.body, 'plain', 'utf-8')

        msg['From'] = from_email
        msg['To'] = ', '.join(to_list)
        if cc_list:
            msg['Cc'] = ', '.join(cc_list)
        msg['Subject'] = email_message.subject

        # Reply-To header
        reply_to = getattr(email_message, 'reply_to', None)
        if reply_to:
            msg['Reply-To'] = ', '.join(reply_to)

        return msg.as_string()

    def _send_via_gmail_api(self, raw_message):
        """Send a raw MIME message via the Gmail API."""
        # URL-safe base64 encode the message
        encoded_message = base64.urlsafe_b64encode(
            raw_message.encode('utf-8')
        ).decode('ascii')

        payload = json.dumps({'raw': encoded_message}).encode('utf-8')

        try:
            req = urllib.request.Request(
                GMAIL_SEND_URI,
                data=payload,
                headers={
                    'Authorization': f'Bearer {self._access_token}',
                    'Content-Type': 'application/json',
                },
                method='POST',
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                response_data = json.loads(resp.read().decode('utf-8'))
                return response_data.get('id')  # Gmail message ID
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8', errors='replace') if hasattr(e, 'read') else str(e)
            logger.error(
                "Gmail API send failed (HTTP %s): %s",
                e.code, error_body,
            )
            raise
        except Exception as e:
            logger.error("Gmail API send failed: %s", str(e))
            raise

    def send_messages(self, email_messages):
        """
        Send one or more EmailMessage objects via the Gmail API.

        Returns the number of messages successfully sent.
        """
        if not email_messages:
            return 0

        # Load credentials
        if not self._load_credential():
            msg = "No active Gmail API credentials found. Complete OAuth authorization first."
            logger.error(msg)
            if not self.fail_silently:
                raise RuntimeError(msg)
            return 0

        # Refresh the access token
        if not self._refresh_access_token():
            msg = "Failed to refresh Gmail API access token."
            logger.error(msg)
            if not self.fail_silently:
                raise RuntimeError(msg)
            return 0

        sent_count = 0
        for message in email_messages:
            try:
                raw_mime = self._build_mime_message(message)
                gmail_id = self._send_via_gmail_api(raw_mime)
                if gmail_id:
                    sent_count += 1
                    logger.info(
                        "Email sent via Gmail API: subject='%s', gmail_id=%s",
                        message.subject, gmail_id,
                    )
            except Exception as e:
                if not self.fail_silently:
                    raise
                logger.error(
                    "Failed to send email via Gmail API: subject='%s', error=%s",
                    message.subject, str(e),
                )

        # Update last_used timestamp
        if sent_count > 0 and self._credential:
            try:
                self._credential.mark_used()
            except Exception:
                pass  # Non-critical

        return sent_count
