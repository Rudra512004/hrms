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
            'id', 'email', 'first_name', 'last_name', 'status', 'employee_code',
            'phone_number', 'address', 'emergency_contact_name', 'emergency_contact_phone'
        )
        read_only_fields = ('id', 'email', 'first_name', 'last_name', 'status', 'employee_code')

class ProvisionEmployeeSerializer(serializers.Serializer):
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    employee_code = serializers.CharField(max_length=50)

    def validate_email(self, value):
        value = User.objects.normalize_email(value)
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
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
            employee_code=validated_data['employee_code']
        )
        return employee
