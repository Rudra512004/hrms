from rest_framework.authentication import TokenAuthentication as DRFTokenAuthentication
from rest_framework.exceptions import AuthenticationFailed

class TokenAuthentication(DRFTokenAuthentication):
    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)

        # Explicitly check the persistent status field to guarantee
        # that deactivated users with old tokens are rejected at the authentication layer.
        if user.status != 'active':
            raise AuthenticationFailed('User inactive or deleted.')

        return user, token
