import os
from decimal import Decimal
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string
from django.conf import settings
from apps.organization.models import Branch, Department, Designation, Team
from .models import Employee, EmploymentStatus, EmployeeLifecycleEvent, EmployeeDocument, DocumentType, DocumentStatus

User = get_user_model()

class EmployeeSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    status = serializers.CharField(source='user.status', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    team_name = serializers.CharField(source='team.name', read_only=True)
    designation_name = serializers.CharField(source='designation.name', read_only=True)

    class Meta:
        model = Employee
        fields = (
            'id', 'email', 'first_name', 'last_name', 'status', 'employee_code', 'personal_email',
            'phone_number', 'address', 'emergency_contact_name', 'emergency_contact_phone',
            'organization', 'branch', 'branch_name', 'department', 'department_name',
            'team', 'team_name',
            'designation', 'designation_name', 'reporting_manager',
            'employment_status', 'joining_date', 'exit_date', 'resignation_date',
            'exit_reason', 'notice_period_start', 'notice_period_end'
        )
        read_only_fields = (
            'id', 'email', 'first_name', 'last_name', 'status', 'employee_code',
            'personal_email', 'employment_status', 'exit_date', 'resignation_date'
        )

    def validate(self, attrs):
        org = attrs.get('organization', getattr(self.instance, 'organization', None))
        branch = attrs.get('branch', getattr(self.instance, 'branch', None))
        dept = attrs.get('department', getattr(self.instance, 'department', None))
        desig = attrs.get('designation', getattr(self.instance, 'designation', None))
        manager = attrs.get('reporting_manager', getattr(self.instance, 'reporting_manager', None))

        team = attrs.get('team', getattr(self.instance, 'team', None))

        if org:
            if branch and branch.organization_id != org.id:
                raise serializers.ValidationError({'branch': 'Branch must belong to the same organization.'})
            if dept and dept.branch.organization_id != org.id:
                raise serializers.ValidationError({'department': 'Department must belong to the same organization.'})
            if branch and dept and dept.branch_id != branch.id:
                raise serializers.ValidationError({'department': 'Department must belong to the same branch as the employee.'})
            if team and team.department_id != getattr(dept, 'id', None):
                raise serializers.ValidationError({'team': 'Team must belong to the same department as the employee.'})
            if team and not team.is_active and getattr(self.instance, 'employment_status', EmploymentStatus.ACTIVE) not in [EmploymentStatus.INACTIVE, EmploymentStatus.EXITED]:
                raise serializers.ValidationError({'team': 'Cannot assign an inactive team to an active employee.'})
            if desig and desig.organization_id != org.id:
                raise serializers.ValidationError({'designation': 'Designation must belong to the same organization.'})
        else:
            if branch or dept or team or desig:
                raise serializers.ValidationError('Cannot assign branch, department, team, or designation without an organization.')

        if self.instance:
            if branch and getattr(self.instance, 'branch', None) and branch != self.instance.branch:
                raise serializers.ValidationError({'branch': 'Branch transfer must be done through the dedicated transfer workflow.'})
            if dept and getattr(self.instance, 'department', None) and dept != self.instance.department:
                raise serializers.ValidationError({'department': 'Department transfer must be done through the dedicated transfer workflow.'})
            # Prevent team changes that cross department boundaries
            if team and getattr(self.instance, 'department', None) and team.department != self.instance.department:
                raise serializers.ValidationError({'team': 'Cross-department team assignment must be done through the dedicated transfer workflow.'})

        if manager:
            if self.instance and manager.id == self.instance.id:
                raise serializers.ValidationError({'reporting_manager': 'Employee cannot report to themselves.'})
            if manager.organization_id != (org.id if org else None):
                raise serializers.ValidationError({'reporting_manager': 'Reporting manager must belong to the same organization.'})

            from apps.employees.models import EmploymentStatus
            if manager.employment_status in [EmploymentStatus.INACTIVE, EmploymentStatus.EXITED]:
                raise serializers.ValidationError({'reporting_manager': 'Reporting manager must be an active employee.'})

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
    employee_code = serializers.CharField(max_length=50, required=False, allow_blank=True)
    personal_email = serializers.EmailField(required=False, allow_null=True, allow_blank=True)

    team = serializers.PrimaryKeyRelatedField(queryset=Team.objects.all(), required=False, allow_null=True)
    department = serializers.PrimaryKeyRelatedField(queryset=Department.objects.all(), required=False, allow_null=True)
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all(), required=False, allow_null=True)
    designation = serializers.PrimaryKeyRelatedField(queryset=Designation.objects.all(), required=False, allow_null=True)
    reporting_manager = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all(), required=False, allow_null=True)
    role = serializers.IntegerField(required=False, allow_null=True)

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
        from .utils import generate_next_employee_code
        from django.db import IntegrityError, transaction
        from apps.organization.models import Organization

        request = self.context.get('request')
        org = None
        if request and request.user.is_authenticated:
            if hasattr(request.user, 'employee') and request.user.employee and request.user.employee.organization_id:
                org = request.user.employee.organization
            elif request.user.is_superuser:
                org_id = self.initial_data.get('organization') if hasattr(self, 'initial_data') else None
                if org_id:
                    org = Organization.objects.filter(id=org_id).first()
                if not org and hasattr(request.user, 'employee') and request.user.employee and request.user.employee.organization_id:
                    org = request.user.employee.organization
                if not org:
                    org = Organization.objects.first()
                if not org:
                    org, _ = Organization.objects.get_or_create(name='Default Organization')

        if not org:
            raise serializers.ValidationError({'organization': 'Cannot provision employee without a valid organization.'})

        try:
            with transaction.atomic():
                employee_code = validated_data.get('employee_code')
                if not employee_code:
                    employee_code = generate_next_employee_code()
                user = User.objects.create_user(
                    email=validated_data['email'],
                    first_name=validated_data['first_name'],
                    last_name=validated_data['last_name'],
                )

                team = validated_data.get('team')
                department = validated_data.get('department')
                branch = validated_data.get('branch')
                designation = validated_data.get('designation')
                reporting_manager = validated_data.get('reporting_manager')

                if team:
                    department = team.department
                    branch = department.branch
                    if branch.organization_id != org.id:
                        raise serializers.ValidationError({'team': 'Team belongs to a different organization.'})

                # If no team is provided, we can fallback to department/branch if it's a valid temporary state
                # but ensure they belong to the correct org
                if branch and branch.organization_id != org.id:
                    raise serializers.ValidationError({'branch': 'Branch must belong to the same organization.'})
                if department and department.branch.organization_id != org.id:
                    raise serializers.ValidationError({'department': 'Department must belong to the same organization.'})
                if branch and department and department.branch_id != branch.id:
                    raise serializers.ValidationError({'department': 'Department must belong to the specified branch.'})

                # Verify scope authorization
                if not request.user.is_superuser:
                    from apps.authorization.services import AuthorizationService
                    has_access = False

                    if AuthorizationService.has_permission(request.user, 'employee.create', branch_id=None, global_only=True):
                        has_access = True
                    else:
                        authorized_branches = AuthorizationService.get_authorized_branches(request.user, 'employee.create')
                        if branch and branch in authorized_branches:
                            has_access = True
                        else:
                            authorized_teams = AuthorizationService.get_authorized_teams(request.user, 'employee.create')
                            if team and team in authorized_teams:
                                has_access = True

                    if not has_access:
                        if not branch and not team:
                            raise serializers.ValidationError({'non_field_errors': 'You must specify an authorized branch or team.'})
                        raise serializers.ValidationError({'non_field_errors': 'You do not have permission to provision employees into this organizational unit.'})

                if designation and designation.organization_id != org.id:
                    raise serializers.ValidationError({'designation': 'Designation must belong to the same organization.'})
                if reporting_manager and reporting_manager.organization_id != org.id:
                    raise serializers.ValidationError({'reporting_manager': 'Reporting manager must belong to the same organization.'})

                from apps.employees.models import EmploymentStatus
                if reporting_manager and reporting_manager.employment_status in [EmploymentStatus.INACTIVE, EmploymentStatus.EXITED]:
                    raise serializers.ValidationError({'reporting_manager': 'Reporting manager must be an active employee.'})

                if team and not team.is_active:
                    raise serializers.ValidationError({'team': 'Cannot assign an inactive team.'})

                employee = Employee.objects.create(
                    user=user,
                    organization=org,
                    branch=branch,
                    department=department,
                    team=team,
                    designation=designation,
                    reporting_manager=reporting_manager,
                    employee_code=employee_code,
                    personal_email=validated_data.get('personal_email')
                )

                # Handle Role assignment
                role_id = validated_data.get('role')
                if role_id:
                    from apps.authorization.models import Role, UserRole
                    role = Role.objects.filter(id=role_id, organization=org).first()
                    if not role:
                        raise serializers.ValidationError({'role': 'Role does not exist in this organization.'})
                    if role.name == 'Super Admin' and not request.user.is_superuser:
                        raise serializers.ValidationError({'role': 'Cannot assign Super Admin role.'})
                    # We check if requester can manage roles, but here we assume provisioning implies they have employee.create
                    # We should also ensure they have 'role.assign' or similar if that's a requirement, but for now we assign it
                    # based on their ability to provision. Wait, user said: "Verify: requester can assign the role".
                    from apps.authorization.services import AuthorizationService
                    if not AuthorizationService.has_permission(request.user, 'role.manage') and not request.user.is_superuser:
                         raise serializers.ValidationError({'role': 'You do not have permission to assign roles.'})
                    UserRole.objects.create(user=user, role=role)

                return employee
        except IntegrityError as e:
            raise serializers.ValidationError(f"Failed to create employee due to database constraint: {str(e)}")

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


class EmployeeLifecycleEventSerializer(serializers.ModelSerializer):
    from_department_name = serializers.CharField(source='from_department.name', read_only=True)
    to_department_name = serializers.CharField(source='to_department.name', read_only=True)
    from_branch_name = serializers.CharField(source='from_branch.name', read_only=True)
    to_branch_name = serializers.CharField(source='to_branch.name', read_only=True)
    from_designation_name = serializers.CharField(source='from_designation.name', read_only=True)
    to_designation_name = serializers.CharField(source='to_designation.name', read_only=True)
    created_by_email = serializers.CharField(source='created_by.email', read_only=True)
    event_type_display = serializers.CharField(source='get_event_type_display', read_only=True)

    class Meta:
        model = EmployeeLifecycleEvent
        fields = (
            'id', 'employee', 'event_type', 'event_type_display',
            'from_status', 'to_status',
            'from_department', 'from_department_name', 'to_department', 'to_department_name',
            'from_branch', 'from_branch_name', 'to_branch', 'to_branch_name',
            'from_designation', 'from_designation_name', 'to_designation', 'to_designation_name',
            'effective_date', 'reason', 'created_by', 'created_by_email', 'created_at'
        )
        read_only_fields = fields


class EmployeeTransferSerializer(serializers.Serializer):
    team = serializers.PrimaryKeyRelatedField(
        queryset=Team.objects.all(), required=False, allow_null=True
    )
    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(), required=False, allow_null=True
    )
    branch = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.all(), required=False, allow_null=True
    )
    effective_date = serializers.DateField(required=True)
    reason = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, attrs):
        team = attrs.get('team')
        dept = attrs.get('department')
        branch = attrs.get('branch')

        if not team and not dept and not branch:
            raise serializers.ValidationError("At least one of team, department or branch must be specified for transfer.")

        if team:
            if not team.is_active:
                raise serializers.ValidationError({'team': 'Cannot transfer to an inactive team.'})
            if dept and dept != team.department:
                raise serializers.ValidationError({'department': 'Contradictory payload: Department does not match the Team\'s department.'})
            if branch and branch != team.department.branch:
                raise serializers.ValidationError({'branch': 'Contradictory payload: Branch does not match the Team\'s branch.'})

            attrs['department'] = team.department
            attrs['branch'] = team.department.branch
        elif dept:
            if branch and branch != dept.branch:
                raise serializers.ValidationError({'branch': 'Contradictory payload: Branch does not match the Department\'s branch.'})
            attrs['branch'] = dept.branch

        return attrs
class EmployeePromotionSerializer(serializers.Serializer):
    designation = serializers.PrimaryKeyRelatedField(
        queryset=Designation.objects.all(), required=True
    )
    effective_date = serializers.DateField(required=True)
    reason = serializers.CharField(required=False, allow_blank=True, default='')
    new_basic_salary = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True, min_value=Decimal('0.00')
    )


class EmployeeExitSerializer(serializers.Serializer):
    exit_type = serializers.ChoiceField(
        choices=['resignation', 'termination', 'end_of_contract', 'retirement', 'other'],
        default='resignation'
    )
    exit_date = serializers.DateField(required=True)
    exit_reason = serializers.CharField(required=False, allow_blank=True, default='')
    resignation_date = serializers.DateField(required=False, allow_null=True)
    notice_period_start = serializers.DateField(required=False, allow_null=True)
    notice_period_end = serializers.DateField(required=False, allow_null=True)
    set_notice_status = serializers.BooleanField(default=False)

    def validate(self, attrs):
        start = attrs.get('notice_period_start')
        end = attrs.get('notice_period_end')
        res_date = attrs.get('resignation_date')
        exit_date = attrs.get('exit_date')
        if start and end and end < start:
            raise serializers.ValidationError({'notice_period_end': 'Notice period end cannot be before start.'})
        if res_date and exit_date and exit_date < res_date:
            raise serializers.ValidationError({'exit_date': 'Exit date cannot be before resignation date.'})
        return attrs


# ── Employee Document Serializers ──────────────────────────────────────────────

ALLOWED_DOCUMENT_EXTENSIONS = {'.pdf', '.png', '.jpg', '.jpeg', '.doc', '.docx'}

# Explicit deny-list of dangerous extensions as a secondary safety net
BLOCKED_EXTENSIONS = {
    '.exe', '.sh', '.bat', '.cmd', '.py', '.js', '.html', '.htm', '.php',
    '.vbs', '.ps1', '.rb', '.pl', '.jar', '.msi', '.dll', '.so', '.out',
    '.bin', '.run', '.com', '.pif', '.scr', '.reg', '.hta', '.cpl', '.inf',
}


class EmployeeDocumentSerializer(serializers.ModelSerializer):
    """Read-only representation of an uploaded document (no file binary)."""
    document_type_display = serializers.CharField(source='get_document_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    uploaded_by_email = serializers.CharField(source='uploaded_by.email', read_only=True)

    class Meta:
        model = EmployeeDocument
        fields = (
            'id', 'employee', 'document_type', 'document_type_display',
            'document_name', 'file_size', 'mime_type', 'description',
            'expiry_date', 'status', 'status_display',
            'uploaded_at', 'uploaded_by', 'uploaded_by_email',
        )
        read_only_fields = fields


class EmployeeDocumentUploadSerializer(serializers.Serializer):
    """Write serializer — validates file before accepting the upload."""
    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all())
    document_type = serializers.ChoiceField(choices=DocumentType.choices, default=DocumentType.OTHER)
    document_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True, default='')
    expiry_date = serializers.DateField(required=False, allow_null=True)
    file = serializers.FileField()

    def validate_file(self, file):
        # 1. Size check
        max_size = getattr(settings, 'MAX_DOCUMENT_UPLOAD_SIZE', 5 * 1024 * 1024)
        if file.size > max_size:
            raise serializers.ValidationError(
                f"File size {file.size} bytes exceeds the maximum allowed {max_size} bytes (5 MB)."
            )

        # 2. Extension — allow-list only
        ext = os.path.splitext(file.name)[-1].lower()
        if ext not in ALLOWED_DOCUMENT_EXTENSIONS:
            raise serializers.ValidationError(
                f"File type '{ext}' is not allowed. Accepted types: {', '.join(sorted(ALLOWED_DOCUMENT_EXTENSIONS))}."
            )

        # 3. Secondary deny-list guard
        if ext in BLOCKED_EXTENSIONS:
            raise serializers.ValidationError(
                f"File type '{ext}' is explicitly blocked for security reasons."
            )

        return file

    def validate_document_name(self, value):
        # Sanitize against path-traversal sequences
        if value:
            value = value.replace('..', '').replace('/', '').replace('\\', '').strip()
        return value

    def create(self, validated_data):
        file = validated_data['file']
        employee = validated_data['employee']

        # Fall back to the original filename if document_name not provided
        doc_name = validated_data.get('document_name') or os.path.basename(file.name)
        # Sanitize the fallback name too
        doc_name = doc_name.replace('..', '').replace('/', '').replace('\\', '').strip()

        document = EmployeeDocument.objects.create(
            employee=employee,
            document_type=validated_data.get('document_type', DocumentType.OTHER),
            document_name=doc_name,
            file=file,
            file_size=file.size,
            mime_type=getattr(file, 'content_type', ''),
            description=validated_data.get('description', ''),
            expiry_date=validated_data.get('expiry_date'),
            uploaded_by=self.context.get('request').user if self.context.get('request') else None,
        )
        return document

class EmployeeSelfServiceSerializer(serializers.ModelSerializer):
    """
    Dedicated serializer for the /api/v1/employees/me/ endpoint to prevent mass-assignment
    of HR-controlled organizational and identity fields by regular employees.
    """
    email = serializers.EmailField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    status = serializers.CharField(source='user.status', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    designation_name = serializers.CharField(source='designation.name', read_only=True)

    class Meta:
        model = Employee
        fields = (
            'id', 'email', 'first_name', 'last_name', 'status', 'employee_code', 'personal_email',
            'phone_number', 'address', 'emergency_contact_name', 'emergency_contact_phone',
            'organization', 'branch', 'branch_name', 'department', 'department_name',
            'designation', 'designation_name', 'reporting_manager',
            'employment_status', 'joining_date', 'exit_date', 'resignation_date',
            'exit_reason', 'notice_period_start', 'notice_period_end'
        )
        # All organizational/HR fields are read-only.
        # Only genuinely employee-editable fields (phone, address, emergency contacts) are writable.
        read_only_fields = (
            'id', 'email', 'first_name', 'last_name', 'status', 'employee_code', 'personal_email',
            'organization', 'branch', 'department', 'designation', 'reporting_manager',
            'employment_status', 'joining_date', 'exit_date', 'resignation_date',
            'exit_reason', 'notice_period_start', 'notice_period_end'
        )
