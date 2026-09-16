from rest_framework import serializers
from .models import OfficeNetwork, Organization, Department, Designation, Branch, WorkingCalendar

class WorkingCalendarSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkingCalendar
        fields = ['id', 'organization', 'work_days']
        read_only_fields = ['id', 'organization']

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
    working_calendar = serializers.DictField(write_only=True, required=False)
    attendance_policy = serializers.DictField(write_only=True, required=False)
    primary_office = serializers.DictField(write_only=True, required=False)
    primary_network = serializers.DictField(write_only=True, required=False)

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
        model = Organization
        fields = ['id', 'name', 'status', 'working_calendar', 'attendance_policy', 'primary_office', 'primary_network']

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

    @transaction.atomic
    def create(self, validated_data):
        wc_data = validated_data.pop('working_calendar', {})
        ap_data = validated_data.pop('attendance_policy', {})
        office_data = validated_data.pop('primary_office', None)
        network_data = validated_data.pop('primary_network', None)

        # Organization is created, post_save will auto-provision default WorkingCalendar & AttendancePolicy
        org = Organization.objects.create(**validated_data)

        # Update auto-provisioned WorkingCalendar
        if wc_data:
            from .models import WorkingCalendar
            wc = org.working_calendar
            for attr, value in wc_data.items():
                setattr(wc, attr, value)
            wc.save()

        # Update auto-provisioned AttendancePolicy
        if ap_data:
            from .models import AttendancePolicy
            ap = org.attendance_policy
            for attr, value in ap_data.items():
                setattr(ap, attr, value)
            ap.save()

        from django.core.exceptions import ValidationError
        try:
            # Create Primary Branch
            if office_data:
                from .models import Branch
                Branch.objects.create(organization=org, **office_data)

            # Create Primary Network
            if network_data:
                from .models import OfficeNetwork
                OfficeNetwork.objects.create(organization=org, **network_data)
        except ValidationError as e:
            # Re-raise as DRF ValidationError to return 400 instead of 500
            if hasattr(e, 'message_dict'):
                raise serializers.ValidationError(e.message_dict)
            raise serializers.ValidationError(e.messages)

        return org

    @transaction.atomic
    def update(self, instance, validated_data):
        wc_data = validated_data.pop('working_calendar', None)
        ap_data = validated_data.pop('attendance_policy', None)
        # We don't handle branch/network in edit wizard via the setup endpoint, they have their own endpoints.
        # Or we can just ignore them here.
        validated_data.pop('primary_office', None)
        validated_data.pop('primary_network', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if wc_data is not None:
            wc = instance.working_calendar
            for attr, value in wc_data.items():
                setattr(wc, attr, value)
            wc.save()

        if ap_data is not None:
            ap = instance.attendance_policy
            for attr, value in ap_data.items():
                setattr(ap, attr, value)
            ap.save()

        return instance

class OrganizationSerializer(serializers.ModelSerializer):
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
        model = Organization
        fields = ['id', 'name', 'status', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

class DepartmentSerializer(serializers.ModelSerializer):
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
        model = Department
        fields = ['id', 'organization', 'name', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'organization', 'created_at', 'updated_at']

class DesignationSerializer(serializers.ModelSerializer):
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
        model = Designation
        fields = ['id', 'organization', 'name', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'organization', 'created_at', 'updated_at']

class OfficeNetworkSerializer(serializers.ModelSerializer):
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
        model = OfficeNetwork
        fields = ['id', 'organization', 'name', 'network', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'organization', 'created_at', 'updated_at']

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
