from rest_framework import serializers
from django.utils import timezone
from .models import AssetCategory, Asset, AssetAssignment, AssetStatus
from apps.organization.models import Branch
from apps.employees.models import Employee, EmploymentStatus


class AssetCategorySerializer(serializers.ModelSerializer):
    asset_count = serializers.SerializerMethodField()

    class Meta:
        model = AssetCategory
        fields = (
            'id', 'organization', 'name', 'code',
            'description', 'is_active', 'asset_count',
            'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'organization', 'asset_count', 'created_at', 'updated_at')

    def get_asset_count(self, obj):
        return obj.assets.count()

    def validate(self, attrs):
        request = self.context.get('request')
        org = getattr(request.user.employee, 'organization', None) if hasattr(request.user, 'employee') else None
        if not org and not request.user.is_superuser:
            raise serializers.ValidationError("User has no associated organization.")

        target_org = org or self.instance.organization if self.instance else org
        name = attrs.get('name')
        code = attrs.get('code')

        qs = AssetCategory.objects.filter(organization=target_org)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)

        if name and qs.filter(name__iexact=name).exists():
            raise serializers.ValidationError({'name': 'Category with this name already exists in your organization.'})
        if code and qs.filter(code__iexact=code).exists():
            raise serializers.ValidationError({'code': 'Category with this code already exists in your organization.'})

        return attrs


class AssetAssignmentSerializer(serializers.ModelSerializer):
    asset_tag = serializers.CharField(source='asset.asset_tag', read_only=True)
    asset_name = serializers.CharField(source='asset.name', read_only=True)
    category_name = serializers.CharField(source='asset.category.name', read_only=True)
    employee_code = serializers.CharField(source='employee.employee_code', read_only=True)
    employee_name = serializers.SerializerMethodField()
    assigned_by_email = serializers.CharField(source='assigned_by.email', read_only=True)

    class Meta:
        model = AssetAssignment
        fields = (
            'id', 'asset', 'asset_tag', 'asset_name', 'category_name',
            'employee', 'employee_code', 'employee_name',
            'allocated_at', 'expected_return_date', 'returned_at',
            'condition_at_allocation', 'condition_at_return',
            'allocation_notes', 'return_notes',
            'assigned_by', 'assigned_by_email', 'is_active',
            'created_at', 'updated_at',
        )
        read_only_fields = fields

    def get_employee_name(self, obj):
        user = obj.employee.user
        return f"{user.first_name} {user.last_name}".strip() or user.email


class AssetListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_code = serializers.CharField(source='category.code', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    current_assignment = serializers.SerializerMethodField()

    class Meta:
        model = Asset
        fields = (
            'id', 'asset_tag', 'name', 'category', 'category_name', 'category_code',
            'branch', 'branch_name', 'serial_number', 'model_number',
            'status', 'status_display', 'purchase_date', 'purchase_cost',
            'warranty_expiry', 'notes', 'current_assignment',
            'created_at', 'updated_at',
        )
        read_only_fields = fields

    def get_current_assignment(self, obj):
        # Use pre-fetched assignment if available
        assignment = next((a for a in getattr(obj, '_prefetched_assignments', []) if a.is_active), None)
        if assignment is None:
            assignment = obj.assignments.filter(is_active=True).select_related('employee__user').first()
        if not assignment:
            return None
        user = assignment.employee.user
        emp_name = f"{user.first_name} {user.last_name}".strip() or user.email
        return {
            'id': assignment.id,
            'employee_id': assignment.employee_id,
            'employee_code': assignment.employee.employee_code,
            'employee_name': emp_name,
            'allocated_at': assignment.allocated_at,
            'expected_return_date': assignment.expected_return_date,
            'condition_at_allocation': assignment.condition_at_allocation,
        }


class AssetDetailSerializer(AssetListSerializer):
    assignment_history = AssetAssignmentSerializer(source='assignments', many=True, read_only=True)

    class Meta(AssetListSerializer.Meta):
        fields = AssetListSerializer.Meta.fields + ('assignment_history',)


class AssetCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = (
            'id', 'asset_tag', 'name', 'category', 'branch',
            'serial_number', 'model_number', 'status',
            'purchase_date', 'purchase_cost', 'warranty_expiry', 'notes',
        )
        read_only_fields = ('id', 'status')

    def validate_asset_tag(self, value):
        tag = value.strip()
        if not tag:
            raise serializers.ValidationError("Asset tag cannot be blank.")
        request = self.context.get('request')
        org_id = None
        if hasattr(request.user, 'employee') and request.user.employee.organization_id:
            org_id = request.user.employee.organization_id
        elif self.instance:
            org_id = self.instance.organization_id

        if org_id:
            qs = Asset.objects.filter(organization_id=org_id, asset_tag__iexact=tag)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError("Asset with this tag already exists in your organization.")
        return tag

    def validate_category(self, value):
        request = self.context.get('request')
        if not request.user.is_superuser and hasattr(request.user, 'employee'):
            if value.organization_id != request.user.employee.organization_id:
                raise serializers.ValidationError("Category does not belong to your organization.")
        return value

    def validate_branch(self, value):
        if value is None:
            return value
        request = self.context.get('request')
        if not request.user.is_superuser and hasattr(request.user, 'employee'):
            if value.organization_id != request.user.employee.organization_id:
                raise serializers.ValidationError("Branch does not belong to your organization.")
        return value


class AssetAssignSerializer(serializers.Serializer):
    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all())
    expected_return_date = serializers.DateField(required=False, allow_null=True)
    condition_at_allocation = serializers.CharField(max_length=50, required=False, default='good')
    allocation_notes = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_employee(self, employee):
        if employee.employment_status == EmploymentStatus.EXITED:
            raise serializers.ValidationError("Cannot assign assets to an exited employee.")
        return employee


class AssetReturnSerializer(serializers.Serializer):
    return_date = serializers.DateField(required=False, default=timezone.now().date)
    condition_at_return = serializers.CharField(max_length=50, required=False, default='good')
    return_notes = serializers.CharField(required=False, allow_blank=True, default='')
    next_status = serializers.ChoiceField(
        choices=[
            (AssetStatus.AVAILABLE, 'Available'),
            (AssetStatus.UNDER_MAINTENANCE, 'Under Maintenance'),
            (AssetStatus.RETIRED, 'Retired'),
        ],
        default=AssetStatus.AVAILABLE,
    )
