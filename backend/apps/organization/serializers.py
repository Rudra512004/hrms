from rest_framework import serializers
from django.db import transaction
from .models import (
    OfficeNetwork, Organization, Department, Designation, Branch,
    WorkingCalendar, WorkingCalendarRule, Team, AttendancePolicy,
    TenantBrandingAndConfig, OrganizationOnboarding,
    OrganizationInvitation, InvitationStatus, EmailDeliveryStatus,
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

class TenantBrandingAndConfigSerializer(serializers.ModelSerializer):
    """
    Serializes all tenant branding, theme, and custom-field-schema configuration.
    Used both inline on OrganizationSerializer (read) and as the standalone
    branding action endpoint (read/write).
    """
    class Meta:
        model = TenantBrandingAndConfig
        fields = [
            'branding_mode', 'selected_palette', 'palette_suggestions', 'manual_overrides',
            'logo_url', 'logo_file', 'favicon_url', 'login_banner_url', 'watermark_url',
            'watermark_opacity', 'primary_color', 'secondary_color',
            'accent_color', 'sidebar_bg_color', 'default_theme_mode',
            'font_family', 'currency_code', 'date_format',
            'enabled_modules_json', 'custom_fields_schema', 'updated_at',
        ]
        read_only_fields = ['updated_at']

    def validate_hex_color_field(self, field_name, value):
        if value:
            from .branding_service import OrganizationBrandingService
            clean_val = value.strip()
            if not OrganizationBrandingService.validate_hex_color(clean_val):
                raise serializers.ValidationError(f"Invalid hex color format for {field_name}. Expected format: #RRGGBB or #RGB.")
            return clean_val
        return value

    def validate_primary_color(self, value):
        return self.validate_hex_color_field('primary_color', value)

    def validate_secondary_color(self, value):
        return self.validate_hex_color_field('secondary_color', value)

    def validate_accent_color(self, value):
        return self.validate_hex_color_field('accent_color', value)

    def validate_sidebar_bg_color(self, value):
        return self.validate_hex_color_field('sidebar_bg_color', value)

    def validate_branding_mode(self, value):
        from .models import BrandingMode
        if value and value not in BrandingMode.values:
            raise serializers.ValidationError(f"Invalid branding mode. Must be one of {BrandingMode.values}.")
        return value

    def validate_watermark_opacity(self, value):
        if value is not None and not (0 <= value <= 1):
            raise serializers.ValidationError('Watermark opacity must be between 0 and 1.')
        return value

    def validate_custom_fields_schema(self, value):
        """Validate that each schema entry has required keys and a supported type."""
        allowed_types = {'text', 'number', 'date', 'boolean', 'select'}
        if not isinstance(value, list):
            raise serializers.ValidationError('custom_fields_schema must be a list.')
        seen_keys = set()
        for idx, entry in enumerate(value):
            if not isinstance(entry, dict):
                raise serializers.ValidationError(f'Entry at index {idx} must be an object.')
            for required_key in ('key', 'label', 'type', 'module'):
                if required_key not in entry:
                    raise serializers.ValidationError(
                        f'Entry at index {idx} is missing required field "{required_key}".'
                    )
            if entry['type'] not in allowed_types:
                raise serializers.ValidationError(
                    f'Entry at index {idx} has unsupported type "{entry["type"]}". '
                    f'Allowed: {sorted(allowed_types)}.'
                )
            if entry['key'] in seen_keys:
                raise serializers.ValidationError(
                    f'Duplicate custom field key "{entry["key"]}" at index {idx}.'
                )
            seen_keys.add(entry['key'])
        return value


class OrganizationSerializer(serializers.ModelSerializer):
    # Embed branding inline on every org read so the frontend can hydrate
    # ThemeContext without an extra round-trip.
    branding = TenantBrandingAndConfigSerializer(read_only=True)

    class Meta:
        model = Organization
        fields = ['id', 'name', 'status', 'created_at', 'updated_at', 'branding']
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


# =============================================================================
# Organization Onboarding Wizard Serializers
# =============================================================================

class OrganizationOnboardingSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    organization_code = serializers.CharField(source='organization.code', read_only=True)
    owner_email = serializers.EmailField(source='owner.email', read_only=True)

    class Meta:
        model = OrganizationOnboarding
        fields = [
            'id', 'organization', 'organization_name', 'organization_code',
            'owner', 'owner_email', 'status', 'current_stage',
            'completed_stages', 'metadata', 'completed_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'organization', 'organization_name', 'organization_code',
            'owner', 'owner_email', 'status', 'current_stage',
            'completed_stages', 'metadata', 'completed_at',
            'created_at', 'updated_at',
        ]


class OnboardingStage1Serializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=True)
    code = serializers.CharField(max_length=50, required=False, allow_blank=True, default='')
    currency_code = serializers.CharField(max_length=10, required=False, default='INR')
    date_format = serializers.CharField(max_length=30, required=False, default='DD/MM/YYYY')
    timezone = serializers.CharField(max_length=50, required=False, default='UTC')

    def validate_name(self, value):
        val = value.strip()
        if not val:
            raise serializers.ValidationError("Organization name cannot be empty.")
        return val


class OnboardingStage2Serializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=True)
    code = serializers.CharField(max_length=50, required=False, allow_blank=True, default='')
    address_line1 = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
    address_line2 = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
    city = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    state = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    country = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    postal_code = serializers.CharField(max_length=20, required=False, allow_blank=True, default='')
    timezone = serializers.CharField(max_length=50, required=False, default='UTC')
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, allow_null=True)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, allow_null=True)
    radius = serializers.FloatField(required=False, default=100.0)

    def validate_radius(self, value):
        if value < 100.0:
            raise serializers.ValidationError("Branch radius must be at least 100.0 meters.")
        return value


class OnboardingDepartmentInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=True)
    code = serializers.CharField(max_length=50, required=False, allow_blank=True, default='')
    description = serializers.CharField(required=False, allow_blank=True, default='')


class OnboardingDesignationInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=True)
    code = serializers.CharField(max_length=50, required=False, allow_blank=True, default='')
    level = serializers.IntegerField(required=False, allow_null=True, min_value=1)


class OnboardingStage3Serializer(serializers.Serializer):
    departments = OnboardingDepartmentInputSerializer(many=True, required=True)
    designations = OnboardingDesignationInputSerializer(many=True, required=True)

    def validate_departments(self, value):
        if not value:
            raise serializers.ValidationError("At least one department is required for stage 3.")
        names = [d['name'].strip().lower() for d in value if d.get('name')]
        if len(names) != len(set(names)):
            raise serializers.ValidationError("Duplicate department names are not allowed.")
        return value

    def validate_designations(self, value):
        if not value:
            raise serializers.ValidationError("At least one designation is required for stage 3.")
        names = [d['name'].strip().lower() for d in value if d.get('name')]
        if len(names) != len(set(names)):
            raise serializers.ValidationError("Duplicate designation names are not allowed.")
        return value


class OnboardingHolidayInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=True)
    date = serializers.DateField(required=True)
    holiday_type = serializers.CharField(max_length=50, required=False, allow_blank=True, default='public')


class OnboardingStage4Serializer(serializers.Serializer):
    work_days = serializers.CharField(max_length=50, required=True)
    recurring_rules = WorkingCalendarRuleSerializer(many=True, required=False, default=list)
    holidays = OnboardingHolidayInputSerializer(many=True, required=False, default=list)

    def validate_work_days(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("work_days cannot be empty.")
        try:
            days = [int(d.strip()) for d in value.split(',')]
            if not all(0 <= d <= 6 for d in days):
                raise serializers.ValidationError("Work days must be between 0 (Monday) and 6 (Sunday).")
            if len(days) != len(set(days)):
                raise serializers.ValidationError("Duplicate work days are not allowed.")
        except serializers.ValidationError:
            raise
        except Exception:
            raise serializers.ValidationError("Invalid format. Use comma-separated integers, e.g. '0,1,2,3,4'.")
        return value


class OnboardingShiftInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=False, default='General Shift')
    code = serializers.CharField(max_length=50, required=False, allow_blank=True, default='GEN')
    start_time = serializers.TimeField(required=True)
    end_time = serializers.TimeField(required=True)
    grace_period_minutes = serializers.IntegerField(required=False, default=15, min_value=0)
    work_days = serializers.CharField(max_length=50, required=False, default='0,1,2,3,4')


class OnboardingAttendancePolicyInputSerializer(serializers.Serializer):
    is_office_gps_enabled = serializers.BooleanField(required=False, default=True)
    is_office_ip_enabled = serializers.BooleanField(required=False, default=False)
    is_wfh_enabled = serializers.BooleanField(required=False, default=False)
    wfh_bypasses_office_restrictions = serializers.BooleanField(required=False, default=True)


class OnboardingOfficeNetworkInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255, required=True)
    network = serializers.CharField(max_length=50, required=True)
    description = serializers.CharField(required=False, allow_blank=True, default='')


class OnboardingStage5Serializer(serializers.Serializer):
    shift = OnboardingShiftInputSerializer(required=True)
    attendance_policy = OnboardingAttendancePolicyInputSerializer(required=False, default=dict)
    office_network = OnboardingOfficeNetworkInputSerializer(required=False, allow_null=True, default=None)


class OnboardingStage6Serializer(serializers.Serializer):
    assignment_type = serializers.ChoiceField(
        choices=['self', 'invite'],
        required=False,
        default='self',
    )
    confirm = serializers.BooleanField(required=False, default=False)
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    email = serializers.EmailField(required=False)

    def validate(self, data):
        assignment_type = data.get('assignment_type', 'self')
        if assignment_type == 'self':
            if not data.get('confirm'):
                raise serializers.ValidationError({
                    'confirm': "Confirmation of administrative role assignment is required to proceed."
                })
        elif assignment_type == 'invite':
            email = data.get('email')
            first_name = data.get('first_name')
            if not email:
                raise serializers.ValidationError({'email': ["This field is required."]})
            email = email.strip().lower()
            data['email'] = email
            if not first_name or not first_name.strip():
                raise serializers.ValidationError({'first_name': ["This field is required."]})
            data['first_name'] = first_name.strip()
            if 'last_name' in data and data['last_name']:
                data['last_name'] = data['last_name'].strip()

            # Prevent self-invite via Option B
            request = self.context.get('request')
            if request and getattr(request, 'user', None) and request.user.is_authenticated:
                if request.user.email and request.user.email.strip().lower() == email:
                    raise serializers.ValidationError({
                        'email': ["To assign yourself, choose 'Assign myself' (Option A)."]
                    })
        return data


class OrganizationInvitationSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source='role.name', read_only=True)
    role_slug = serializers.CharField(source='role.slug', read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    organization_code = serializers.CharField(source='organization.code', read_only=True)

    class Meta:
        model = OrganizationInvitation
        fields = [
            'id', 'email', 'first_name', 'last_name', 'status',
            'email_delivery_status', 'email_delivery_error', 'email_sent_at',
            'expires_at', 'resend_count', 'created_at', 'role_name', 'role_slug',
            'organization_name', 'organization_code'
        ]
        read_only_fields = fields


class OrganizationInvitationAcceptSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)
    password = serializers.CharField(required=False, write_only=True)
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)

    def validate_token(self, value):
        token = value.strip()
        if not token:
            raise serializers.ValidationError("Invitation token is required.")
        return token


class OnboardingDraftSerializer(serializers.Serializer):
    stage = serializers.IntegerField(min_value=1, max_value=7, required=True)
    data = serializers.DictField(required=True)

    def validate_data(self, value):
        from .models import validate_onboarding_metadata
        from django.core.exceptions import ValidationError as DjangoValidationError
        try:
            validate_onboarding_metadata(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.messages if hasattr(e, 'messages') else str(e))
        return value

