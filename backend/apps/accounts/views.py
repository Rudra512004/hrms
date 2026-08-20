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
