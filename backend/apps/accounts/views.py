from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authtoken.models import Token
from .serializers import LoginSerializer, UserSerializer, ActivateSerializer
from apps.authorization.permissions import IsNetworkAllowed
from apps.audit.services import AuditService
from rest_framework.exceptions import ValidationError

class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        try:
            serializer = LoginSerializer(data=request.data, context={'request': request})
            serializer.is_valid(raise_exception=True)
            user = serializer.validated_data['user']
            token, created = Token.objects.get_or_create(user=user)

            AuditService.log(
                action='login_success',
                actor=user,
                target_type='user',
                target_id=user.id,
                request=request
            )

            return Response({
                'token': token.key,
                'user': UserSerializer(user).data
            }, status=status.HTTP_200_OK)
        except ValidationError as e:
            AuditService.log(
                action='login_failure',
                metadata={'email': request.data.get('email')},
                request=request
            )
            raise e

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        AuditService.log(
            action='logout',
            actor=request.user,
            target_type='user',
            target_id=request.user.id,
            request=request
        )
        request.user.auth_token.delete()
        return Response({'detail': 'Successfully logged out.'}, status=status.HTTP_200_OK)

class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

class ActivateView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = ActivateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        AuditService.log(
            action='account_activation',
            actor=user,
            target_type='user',
            target_id=user.id,
            request=request
        )
        return Response({'detail': 'Account successfully activated.'}, status=status.HTTP_200_OK)

from rest_framework.throttling import AnonRateThrottle
from django.contrib.auth import get_user_model
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from apps.notifications.services import NotificationService
from .serializers import PasswordResetRequestSerializer, PasswordResetConfirmSerializer

User = get_user_model()

class PasswordResetThrottle(AnonRateThrottle):
    rate = '5/hour'

class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetThrottle]

    def post(self, request, *args, **kwargs):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        try:
            user = User.objects.get(email=email)
            if user.status == 'active':
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                token = default_token_generator.make_token(user)
                NotificationService.send_password_reset_email(
                    email=user.email,
                    first_name=user.first_name,
                    uid=uid,
                    token=token
                )

                AuditService.log(
                    action='password_reset_requested',
                    actor=user,
                    target_type='user',
                    target_id=user.id,
                    request=request
                )
        except User.DoesNotExist:
            pass

        return Response(
            {'detail': 'If an account is associated with this email, password reset instructions have been sent.'},
            status=status.HTTP_200_OK
        )

class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetThrottle]

    def post(self, request, *args, **kwargs):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Delete existing authentication tokens for security
        Token.objects.filter(user=user).delete()

        AuditService.log(
            action='password_reset_completed',
            actor=user,
            target_type='user',
            target_id=user.id,
            request=request
        )

        return Response({'detail': 'Password has been successfully reset.'}, status=status.HTTP_200_OK)
