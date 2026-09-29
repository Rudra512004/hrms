from rest_framework import serializers
from django.db import transaction
from .models import (
    OfficeNetwork, Organization, Department, Designation, Branch,
    WorkingCalendar, WorkingCalendarRule, Team, AttendancePolicy
)

class WorkingCalendarRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkingCalendarRule
        fields = ['id', 'weekday', 'occurrence', 'is_working']
        read_only_fields = ['id']

    def validate_weekday(self, value):
        if value is None or not (0 <= value <= 6):
            raise serializers.ValidationError("Weekday must be an integer between 0 (Monday) and 6 (Sunday).")
        return value

    def validate_occurrence(self, value):
        if value is None or not (1 <= value <= 5):
            raise serializers.ValidationError("Occurrence must be an integer between 1 and 5.")
        return value

    def validate(self, attrs):
        weekday = attrs.get('weekday')
        occurrence = attrs.get('occurrence')
        if weekday is not None and not (0 <= weekday <= 6):
            raise serializers.ValidationError({'weekday': "Weekday must be between 0 and 6."})
        if occurrence is not None and not (1 <= occurrence <= 5):
            raise serializers.ValidationError({'occurrence': "Occurrence must be between 1 and 5."})
        return attrs


class WorkingCalendarSerializer(serializers.ModelSerializer):
    recurring_rules = WorkingCalendarRuleSerializer(many=True, required=False)

    class Meta:
        model = WorkingCalendar
        fields = ['id', 'branch', 'work_days', 'recurring_rules']
        read_only_fields = ['id', 'branch']

    def validate_work_days(self, value):
        if value is not None:
            if not value.strip():
                raise serializers.ValidationError("work_days cannot be empty.")
            try:
                days = [int(d.strip()) for d in value.split(',')]
                if not all(0 <= d <= 6 for d in days):
                    raise serializers.ValidationError("Work days must be between 0 and 6.")
                if len(days) != len(set(days)):
                    raise serializers.ValidationError("Duplicate work days are not allowed.")
            except Exception:
                raise serializers.ValidationError("Invalid format. Use comma separated integers (e.g. '0,1,2,3,4').")
        return value

    def validate_recurring_rules(self, value):
        seen = set()
        for idx, rule in enumerate(value):
            wd = rule.get('weekday')
            occ = rule.get('occurrence')
            if wd is None or not (0 <= wd <= 6):
                raise serializers.ValidationError(
                    f"Rule at index {idx}: weekday must be an integer between 0 (Monday) and 6 (Sunday)."
                )
            if occ is None or not (1 <= occ <= 5):
                raise serializers.ValidationError(
                    f"Rule at index {idx}: occurrence must be an integer between 1 and 5."
                )
            key = (wd, occ)
            if key in seen:
                raise serializers.ValidationError(
                    f"Duplicate recurring rule for weekday {wd} and occurrence {occ}."
                )
            seen.add(key)
        return value

    @transaction.atomic
    def update(self, instance, validated_data):
        recurring_rules_data = validated_data.pop('recurring_rules', None)

        if 'work_days' in validated_data:
            instance.work_days = validated_data['work_days']
            instance.clean()
            instance.save()

        if recurring_rules_data is not None:
            # Full validation complete: replace existing rules atomically
            instance.recurring_rules.all().delete()
            for rule_data in recurring_rules_data:
                rule = WorkingCalendarRule(working_calendar=instance, **rule_data)
                rule.full_clean()
                rule.save()

        return instance


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

class AttendancePolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendancePolicy
        fields = [
            'id', 'branch', 'is_office_gps_enabled', 'is_office_ip_enabled',
            'is_wfh_enabled', 'wfh_bypasses_office_restrictions', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'branch', 'created_at', 'updated_at']

class BranchSerializer(serializers.ModelSerializer):
    attendance_policy = AttendancePolicySerializer(required=False)
    working_calendar = WorkingCalendarSerializer(required=False)

    class Meta:
        model = Branch
        fields = [
            'id', 'organization', 'name', 'address', 'latitude', 'longitude', 'radius',
            'is_active', 'attendance_policy', 'working_calendar', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'organization', 'created_at', 'updated_at']

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        try:
            ret['working_calendar'] = {
                'id': instance.working_calendar.id,
                'work_days': instance.working_calendar.work_days
            }
        except Exception:
            ret['working_calendar'] = {'work_days': '0,1,2,3,4'}
        try:
            ret['attendance_policy'] = {
                'id': instance.attendance_policy.id,
                'is_office_gps_enabled': instance.attendance_policy.is_office_gps_enabled,
                'is_office_ip_enabled': instance.attendance_policy.is_office_ip_enabled,
                'is_wfh_enabled': instance.attendance_policy.is_wfh_enabled,
                'wfh_bypasses_office_restrictions': instance.attendance_policy.wfh_bypasses_office_restrictions
            }
        except Exception:
            pass
        return ret

    def create(self, validated_data):
        ap_data = validated_data.pop('attendance_policy', None)
        wc_data = validated_data.pop('working_calendar', None)
        instance = super().create(validated_data)

        if ap_data:
            policy, _ = AttendancePolicy.objects.get_or_create(branch=instance)
            for attr, val in ap_data.items():
                setattr(policy, attr, val)
            policy.save()

        if wc_data:
            wc, _ = WorkingCalendar.objects.get_or_create(branch=instance)
            for attr, val in wc_data.items():
                setattr(wc, attr, val)
            wc.save()

        return instance

    def update(self, instance, validated_data):
        ap_data = validated_data.pop('attendance_policy', None)
        wc_data = validated_data.pop('working_calendar', None)
        instance = super().update(instance, validated_data)

        if ap_data:
            policy, _ = AttendancePolicy.objects.get_or_create(branch=instance)
            for attr, val in ap_data.items():
                setattr(policy, attr, val)
            policy.save()

        if wc_data:
            wc, _ = WorkingCalendar.objects.get_or_create(branch=instance)
            for attr, val in wc_data.items():
                setattr(wc, attr, val)
            wc.save()

        return instance
