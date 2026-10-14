"""
Encrypted platform email credential storage for Gmail API OAuth.

Refresh tokens are encrypted at rest using Fernet symmetric encryption
derived from a dedicated GMAIL_ENCRYPTION_KEY environment variable
(falling back to DJANGO_SECRET_KEY). This avoids plaintext token storage
and is safe for Render's ephemeral filesystem since data lives in PostgreSQL.
"""

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)


def _get_fernet():
    """Derive a Fernet instance from the configured encryption key."""
    raw_key = getattr(settings, 'GMAIL_ENCRYPTION_KEY', '') or settings.SECRET_KEY
    # Derive a 32-byte key via SHA-256, then base64-encode for Fernet
    digest = hashlib.sha256(raw_key.encode('utf-8')).digest()
    fernet_key = base64.urlsafe_b64encode(digest)
    return Fernet(fernet_key)


class PlatformEmailCredential(models.Model):
    """
    Stores encrypted Gmail API OAuth credentials for the platform sender.

    Only one active credential row should exist at any time. The refresh
    token is encrypted using Fernet before storage. Access tokens are
    transient and refreshed on demand — they are NOT persisted.
    """

    email = models.EmailField(
        help_text="The Gmail address authorized as the platform sender."
    )
    encrypted_refresh_token = models.TextField(
        help_text="Fernet-encrypted OAuth2 refresh token."
    )
    token_scope = models.CharField(
        max_length=255,
        default='https://www.googleapis.com/auth/gmail.send',
        help_text="OAuth scope granted during authorization."
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this credential is the active platform sender."
    )
    authorized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        help_text="The superuser who completed the OAuth flow."
    )
    authorized_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the OAuth authorization was completed."
    )
    last_used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the credential was last used to send an email."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Platform Email Credential"
        verbose_name_plural = "Platform Email Credentials"

    def __str__(self):
        status = "active" if self.is_active else "inactive"
        return f"{self.email} ({status})"

    def set_refresh_token(self, plaintext_token):
        """Encrypt and store a refresh token."""
        fernet = _get_fernet()
        self.encrypted_refresh_token = fernet.encrypt(
            plaintext_token.encode('utf-8')
        ).decode('utf-8')

    def get_refresh_token(self):
        """Decrypt and return the stored refresh token."""
        if not self.encrypted_refresh_token:
            return None
        fernet = _get_fernet()
        try:
            return fernet.decrypt(
                self.encrypted_refresh_token.encode('utf-8')
            ).decode('utf-8')
        except InvalidToken:
            logger.error(
                "Failed to decrypt refresh token for credential id=%s. "
                "The encryption key may have changed.",
                self.pk,
            )
            return None

    def mark_used(self):
        """Update last_used_at timestamp."""
        self.last_used_at = timezone.now()
        self.save(update_fields=['last_used_at', 'updated_at'])

    @classmethod
    def get_active_credential(cls):
        """Return the single active platform email credential, or None."""
        return cls.objects.filter(is_active=True).order_by('-authorized_at').first()
