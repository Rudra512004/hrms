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
    branch_name = serializers.CharField(source='branch.name', read_only=True)

    class Meta:
        model = Employee
        fields = (
            'id', 'email', 'first_name', 'last_name', 'status', 'employee_code', 'personal_email',
            'phone_number', 'address', 'emergency_contact_name', 'emergency_contact_phone',
            'organization', 'branch', 'branch_name', 'department', 'designation', 'reporting_manager',
            'employment_status', 'joining_date', 'exit_date'
        )
        read_only_fields = ('id', 'email', 'first_name', 'last_name', 'status', 'employee_code', 'personal_email', 'employment_status')

    def validate(self, attrs):
        org = attrs.get('organization', getattr(self.instance, 'organization', None))
        branch = attrs.get('branch', getattr(self.instance, 'branch', None))
        dept = attrs.get('department', getattr(self.instance, 'department', None))
        desig = attrs.get('designation', getattr(self.instance, 'designation', None))
        manager = attrs.get('reporting_manager', getattr(self.instance, 'reporting_manager', None))

        if org:
            if branch and branch.organization_id != org.id:
                raise serializers.ValidationError({'branch': 'Branch must belong to the same organization.'})
            if dept and dept.organization_id != org.id:
                raise serializers.ValidationError({'department': 'Department must belong to the same organization.'})
            if desig and desig.organization_id != org.id:
                raise serializers.ValidationError({'designation': 'Designation must belong to the same organization.'})
        else:
            if branch or dept or desig:
                raise serializers.ValidationError('Cannot assign branch, department, or designation without an organization.')

        if manager:
            if self.instance and manager.id == self.instance.id:
                raise serializers.ValidationError({'reporting_manager': 'Employee cannot report to themselves.'})
            if manager.organization_id != (org.id if org else None):
                raise serializers.ValidationError({'reporting_manager': 'Reporting manager must belong to the same organization.'})

        joining_date = attrs.get('joining_date', getattr(self.instance, 'joining_date', None))
        exit_date = attrs.get('exit_date', getattr(self.instance, 'exit_date', None))
        if joining_date and exit_date and exit_date < joining_date:
            raise serializers.ValidationError({'exit_date': 'Exit date cannot be before joining date.'})

        return attrs

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        request = self.context.get('request')
        from apps.authorization.services import AuthorizationService
        if request and request.user.is_authenticated:
            if request.user != instance.user and not AuthorizationService.has_permission(request.user, 'employee.view_sensitive'):
                ret.pop('personal_email', None)
                ret.pop('address', None)
                ret.pop('emergency_contact_name', None)
                ret.pop('emergency_contact_phone', None)
        return ret

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
