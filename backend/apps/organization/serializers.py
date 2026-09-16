from rest_framework import serializers
from .models import OfficeNetwork, Organization, Department, Designation, Branch, WorkingCalendar, Team

class WorkingCalendarSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkingCalendar
        fields = ['id', 'branch', 'work_days']
        read_only_fields = ['id', 'branch']

    def validate_work_days(self, value):
        # Ensure only 0-6 are used, comma separated
        try:
            days = [int(d.strip()) for d in value.split(',')]
            if not all(0 <= d <= 6 for d in days):
                raise serializers.ValidationError("Work days must be between 0 and 6.")
            if len(days) != len(set(days)):
                raise serializers.ValidationError("Duplicate work days are not allowed.")
        except Exception:
            raise serializers.ValidationError("Invalid format. Use comma separated integers (e.g. '0,1,2,3,4').")
        return value


from django.db import transaction

class OrganizationSetupSerializer(serializers.ModelSerializer):
    branches = serializers.ListField(
        child=serializers.DictField(), write_only=True, required=False
    )
    working_calendar = serializers.DictField(write_only=True, required=False)
    attendance_policy = serializers.DictField(write_only=True, required=False)

    class Meta:
        model = Organization
        fields = ['id', 'name', 'status', 'working_calendar', 'attendance_policy', 'branches']
        read_only_fields = ['id']

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        # We can no longer embed working_calendar directly on organization since it is branch-scoped.
        return ret

    @transaction.atomic
    def create(self, validated_data):
        wc_data = validated_data.pop('working_calendar', {})
        ap_data = validated_data.pop('attendance_policy', {})
        branches_data = validated_data.pop('branches', [])

        org = Organization.objects.create(**validated_data)

        from django.core.exceptions import ValidationError
        try:
            from .models import Branch
            for branch_data in branches_data:
                network_data = branch_data.pop('network', None)
                branch = Branch.objects.create(organization=org, **branch_data)

                # Update auto-provisioned Branch configurations
                if wc_data:
                    wc = branch.working_calendar
                    for attr, value in wc_data.items():
                        setattr(wc, attr, value)
                    wc.save()

                if ap_data:
                    ap = branch.attendance_policy
                    for attr, value in ap_data.items():
                        setattr(ap, attr, value)
                    ap.save()

                if network_data:
                    from .models import OfficeNetwork
                    OfficeNetwork.objects.create(branch=branch, **network_data)
        except ValidationError as e:
            if hasattr(e, 'message_dict'):
                raise serializers.ValidationError(e.message_dict)
            raise serializers.ValidationError(e.messages)

        return org

    @transaction.atomic
    def update(self, instance, validated_data):
        # We don't handle working_calendar/attendance_policy updates on the Org setup endpoint anymore.
        validated_data.pop('working_calendar', None)
        validated_data.pop('attendance_policy', None)
        validated_data.pop('branches', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        return instance

class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ['id', 'name', 'status', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'branch', 'name', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'branch', 'created_at', 'updated_at']

class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ['id', 'department', 'name', 'description', 'is_active', 'manager', 'created_at', 'updated_at']
        read_only_fields = ['id', 'department', 'created_at', 'updated_at']

    def validate(self, attrs):
        manager = attrs.get('manager')
        # During creation, department is set by perform_create, so it's not in attrs.
        # But during update it might be. The instance has department.
        department = self.instance.department if self.instance else self.context.get('view').kwargs.get('department_pk') or getattr(self, '_department_context', None)
        
        # We need department from the view for creation.
        # Actually, if we get department from the URL or view... Wait, perform_create sets it.
        # Let's just check if manager and department are available.
        if not department and self.context.get('view') and hasattr(self.context['view'], 'kwargs'):
            pass # We handle this by fetching department from view context if needed, but wait! perform_create validates serializer first.
            
        # The best way is to let the model clean or just validate manager if we have enough context.
        # But the user asked to: "Fix TeamSerializer to raise serializers.ValidationError instead of unhandled Django ValidationError for invalid manager context."
        
        # Let's extract department from instance or perform_create data.
        # In perform_create: `serializer.save(department=dept)` happens AFTER `serializer.is_valid()`.
        # So we can't reliably check department in serializer validation during POST unless it's in initial_data or kwargs.
        request = self.context.get('request')
        if request and request.method == 'POST':
            dept_id = request.data.get('department')
            if dept_id:
                from apps.organization.models import Department
                department = Department.objects.filter(id=dept_id).first()

        if manager and department:
            if manager.branch_id != department.branch_id:
                raise serializers.ValidationError({"manager": "Team manager must belong to the same branch as the team's department."})
        return attrs

class DesignationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Designation
        fields = ['id', 'organization', 'name', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'organization', 'created_at', 'updated_at']

class OfficeNetworkSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfficeNetwork
        fields = ['id', 'branch', 'name', 'network', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'branch', 'created_at', 'updated_at']

class BranchSerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        ret = super().to_representation(instance)
        try:
            ret['working_calendar'] = {'work_days': instance.working_calendar.work_days}
        except:
            ret['working_calendar'] = {'work_days': '0,1,2,3,4'}
        try:
            ret['attendance_policy'] = {
                'is_office_gps_enabled': instance.attendance_policy.is_office_gps_enabled,
                'is_office_ip_enabled': instance.attendance_policy.is_office_ip_enabled,
                'is_wfh_enabled': instance.attendance_policy.is_wfh_enabled,
                'wfh_bypasses_office_restrictions': instance.attendance_policy.wfh_bypasses_office_restrictions
            }
        except:
            pass
        return ret

    class Meta:
        model = Branch
        fields = ['id', 'organization', 'name', 'address', 'latitude', 'longitude', 'radius', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'organization', 'created_at', 'updated_at']
