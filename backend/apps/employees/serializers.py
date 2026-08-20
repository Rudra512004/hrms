from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string
from .models import Employee

User = get_user_model()

class EmployeeSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    status = serializers.CharField(source='user.status', read_only=True)

    class Meta:
        model = Employee
        fields = (
            'id', 'email', 'first_name', 'last_name', 'status', 'employee_code', 'personal_email',
            'phone_number', 'address', 'emergency_contact_name', 'emergency_contact_phone'
        )
        read_only_fields = ('id', 'email', 'first_name', 'last_name', 'status', 'employee_code', 'personal_email')

class ProvisionEmployeeSerializer(serializers.Serializer):
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    employee_code = serializers.CharField(max_length=50)
    personal_email = serializers.EmailField()

    def validate_email(self, value):
        value = User.objects.normalize_email(value)
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_personal_email(self, value):
        if Employee.objects.filter(personal_email=value).exists():
            raise serializers.ValidationError("An employee with this personal email already exists.")
        return value

    def validate_employee_code(self, value):
        if Employee.objects.filter(employee_code=value).exists():
            raise serializers.ValidationError("An employee with this code already exists.")
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data['email'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
        )

        employee = Employee.objects.create(
            user=user,
            employee_code=validated_data['employee_code'],
            personal_email=validated_data.get('personal_email')
        )
        return employee

from .models import WFHRequest

class WFHRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = WFHRequest
        fields = ['id', 'employee', 'start_at', 'end_at', 'reason', 'status', 'requested_at', 'reviewed_by', 'reviewed_at', 'reviewer_comment']
        read_only_fields = ['id', 'employee', 'status', 'requested_at', 'reviewed_by', 'reviewed_at', 'reviewer_comment']

    def validate(self, attrs):
        start_at = attrs.get('start_at')
        end_at = attrs.get('end_at')
        if start_at and end_at and start_at >= end_at:
            raise serializers.ValidationError({"end_at": "End date must be after start date."})
        return attrs

class WFHRequestReviewSerializer(serializers.Serializer):
    reviewer_comment = serializers.CharField(required=False, allow_blank=True)
