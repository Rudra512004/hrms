from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import TokenAuthentication as DRFTokenAuthentication
from rest_framework.exceptions import AuthenticationFailed

class TokenAuthentication(DRFTokenAuthentication):
    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)

        # Explicitly check the persistent status field to guarantee
        # that deactivated users with old tokens are rejected at the authentication layer.
        if user.status != 'active':
            raise AuthenticationFailed('User inactive or deleted.')

        # Enforce token TTL expiration
        token_ttl_hours = getattr(settings, 'TOKEN_TTL_HOURS', 24)
        if token_ttl_hours is not None:
            expiry_time = token.created + timedelta(hours=token_ttl_hours)
            if timezone.now() > expiry_time:
                token.delete()
                raise AuthenticationFailed('Token has expired. Please log in again.')

        return user, token
