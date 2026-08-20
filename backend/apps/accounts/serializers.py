from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from django.utils.http import urlsafe_base64_decode
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    employee_code = serializers.CharField(source='employee.employee_code', read_only=True, default=None)

    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name', 'status', 'is_staff', 'is_superuser', 'created_at', 'updated_at', 'employee_code')
        read_only_fields = fields

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data.get('email')
        password = data.get('password')

        if email and password:
            user = authenticate(request=self.context.get('request'), username=email, password=password)
            if not user:
                raise serializers.ValidationError('Invalid login credentials or account is not active.')
            if user.status != 'active':
                raise serializers.ValidationError('Account is not active.')
        else:
            raise serializers.ValidationError('Must include "email" and "password".')

        data['user'] = user
        return data

class ActivateSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        try:
            uid = urlsafe_base64_decode(data['uid']).decode()
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError("Invalid user UID.")

        if not default_token_generator.check_token(user, data['token']):
            raise serializers.ValidationError("Invalid or expired activation token.")

        if user.status != 'invited':
            raise serializers.ValidationError("Account is already active or cannot be activated.")

        try:
            validate_password(data['password'], user=user)
        except ValidationError as e:
            raise serializers.ValidationError({"password": list(e.messages)})

        data['user'] = user
        return data

    def save(self):
        user = self.validated_data['user']
        user.set_password(self.validated_data['password'])
        user.status = 'active'
        user.save()
        return user


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": ["Passwords do not match."]})

        try:
            uid = urlsafe_base64_decode(data['uid']).decode()
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError("Invalid user UID.")

        if not default_token_generator.check_token(user, data['token']):
            raise serializers.ValidationError("Invalid or expired reset token.")

        if user.status != 'active':
            raise serializers.ValidationError("Account is not active.")

        try:
            validate_password(data['new_password'], user=user)
        except ValidationError as e:
            raise serializers.ValidationError({"new_password": list(e.messages)})

        data['user'] = user
        return data

    def save(self):
        user = self.validated_data['user']
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user
