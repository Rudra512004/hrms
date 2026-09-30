from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from apps.employees.models import Employee
from apps.authorization.models import Permission, Role, RolePermission, UserRole
from apps.organization.models import Organization, OfficeNetwork, Branch
from apps.accounts.models import TenantOwnerRegistration

from django.core.cache import cache
from unittest.mock import patch

User = get_user_model()

class AuthenticationAPITests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.active_user = User.objects.create_user(email='active@company.com', password='Password123!', status='active')
        self.active_employee = Employee.objects.create(user=self.active_user, employee_code='EMP001')
        self.invited_user = User.objects.create_user(email='invited@company.com', password='Password123!')
        self.invited_employee = Employee.objects.create(user=self.invited_user, employee_code='EMP002')
        self.unprovisioned_user = User.objects.create_user(email='unprovisioned@company.com', password='Password123!', status='active')
        self.login_url = reverse('login')
        self.activate_url = reverse('activate')

    def test_activated_employee_can_log_in(self):
        response = self.client.post(self.login_url, {'email': 'active@company.com', 'password': 'Password123!'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)

    def test_invited_employee_cannot_log_in(self):
        response = self.client.post(self.login_url, {'email': 'invited@company.com', 'password': 'Password123!'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Invalid login credentials or account is not active.', str(response.data))

    def test_personal_email_not_accepted(self):
        response = self.client.post(self.login_url, {'email': 'personal@gmail.com', 'password': 'Password123!'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_hrms_id_not_accepted_as_login(self):
        response = self.client.post(self.login_url, {'email': 'EMP001', 'password': 'Password123!'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_activation_flow(self):
        uid = urlsafe_base64_encode(force_bytes(self.invited_user.pk))
        token = default_token_generator.make_token(self.invited_user)
        response = self.client.post(self.activate_url, {
            'uid': uid,
            'token': token,
            'password': 'NewSecurePassword123!'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.invited_user.refresh_from_db()
        self.assertEqual(self.invited_user.status, 'active')
        self.assertTrue(self.invited_user.check_password('NewSecurePassword123!'))
        login_response = self.client.post(self.login_url, {'email': 'invited@company.com', 'password': 'NewSecurePassword123!'})
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

    def test_activation_token_cannot_be_reused(self):
        uid = urlsafe_base64_encode(force_bytes(self.invited_user.pk))
        token = default_token_generator.make_token(self.invited_user)
        # Activate once
        self.client.post(self.activate_url, {'uid': uid, 'token': token, 'password': 'NewSecurePassword123!'})
        # Try again
        response = self.client.post(self.activate_url, {'uid': uid, 'token': token, 'password': 'AnotherPassword123!'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invalid or expired activation token.", str(response.data))

    def test_already_active_account_cannot_be_activated(self):
        uid = urlsafe_base64_encode(force_bytes(self.active_user.pk))
        token = default_token_generator.make_token(self.active_user)
        response = self.client.post(self.activate_url, {'uid': uid, 'token': token, 'password': 'NewSecurePassword123!'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Account is already active or cannot be activated.", str(response.data))

    def test_malformed_uid(self):
        token = default_token_generator.make_token(self.invited_user)
        response = self.client.post(self.activate_url, {'uid': 'invalid-uid', 'token': token, 'password': 'NewSecurePassword123!'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invalid user UID.", str(response.data))

    def test_weak_password_rejected(self):
        uid = urlsafe_base64_encode(force_bytes(self.invited_user.pk))
        token = default_token_generator.make_token(self.invited_user)
        response = self.client.post(self.activate_url, {'uid': uid, 'token': token, 'password': '123'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)


class TenantOwnerIsolationTests(TestCase):
    """Exercise the real self-service client path across two organizations."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        for codename in (
            'organization.view', 'organization.manage', 'branch.view', 'branch.manage',
            'employee.view', 'employee.create', 'role.view', 'role.assign',
            'permission.view', 'permission.assign',
        ):
            resource, action = codename.split('.')
            Permission.objects.create(name=codename, codename=codename, resource=resource, action=action)

    def _register_verify_and_launch(self, email, organization_name):
        with patch('apps.accounts.views.NotificationService.send_tenant_owner_verification_email', return_value=True):
            response = self.client.post(reverse('tenant-owner-register'), {
                'email': email, 'first_name': 'Client', 'last_name': organization_name,
            })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email=email)
        registration = TenantOwnerRegistration.objects.get(user=user)
        self.assertIsNone(registration.verified_at)

        activation = self.client.post(reverse('activate'), {
            'uid': urlsafe_base64_encode(force_bytes(user.pk)),
            'token': default_token_generator.make_token(user),
            'password': 'VerifiedPassword123!',
        })
        self.assertEqual(activation.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        registration.refresh_from_db()
        self.assertTrue(registration.can_launch_organization)

        self.client.force_authenticate(user=user)
        launch = self.client.post(reverse('tenant-organization-setup'), {
            'name': organization_name,
            'status': 'active',
            'branches': [{'name': f'{organization_name} HQ'}],
            'working_calendar': {'work_days': '0,1,2,3,4'},
        }, format='json')
        self.assertEqual(launch.status_code, status.HTTP_201_CREATED)
        registration.refresh_from_db()
        self.assertFalse(registration.can_launch_organization)
        self.assertIsNotNone(registration.organization_id)
        self.assertFalse(user.is_superuser)
        self.assertFalse(Employee.objects.filter(user=user).exists())
        self.client.force_authenticate(user=None)
        return user, registration.organization

    def test_verified_client_owners_are_isolated_and_can_invite_employees(self):
        owner_a, organization_a = self._register_verify_and_launch('owner-a@example.com', 'Client Alpha')
        owner_b, organization_b = self._register_verify_and_launch('owner-b@example.com', 'Client Beta')
        branch_a = organization_a.branches.get()
        branch_b = organization_b.branches.get()

        self.client.force_authenticate(user=owner_a)
        organizations = self.client.get('/api/v1/organization/organizations/')
        self.assertEqual(organizations.status_code, status.HTTP_200_OK)
        self.assertEqual([item['id'] for item in organizations.data], [organization_a.id])
        self.assertEqual(self.client.get(f'/api/v1/organization/organizations/{organization_b.id}/').status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.post('/api/v1/organization/organizations/', {
            'name': 'Unauthorized second tenant', 'status': 'active',
        }, format='json').status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.post('/api/v1/organization/branches/', {
            'organization': organization_b.id, 'name': 'Unauthorized branch',
        }).status_code, status.HTTP_400_BAD_REQUEST)

        with patch('apps.employees.views.NotificationService.send_employee_onboarding_email', return_value=True) as send_invite:
            invite = self.client.post('/api/v1/employees/management/', {
                'email': 'alpha-employee@example.com', 'first_name': 'Alpha', 'last_name': 'Employee', 'branch': branch_a.id,
            }, format='json')
        self.assertEqual(invite.status_code, status.HTTP_201_CREATED)
        employee = Employee.objects.get(user__email='alpha-employee@example.com')
        self.assertEqual(employee.organization_id, organization_a.id)
        self.assertEqual(send_invite.call_args.kwargs['recipient_email'], 'alpha-employee@example.com')

        # Dynamic RBAC uses the employee's actual User primary key, never the
        # coincidental Employee primary key.
        role_response = self.client.post('/api/v1/authorization/roles/', {
            'name': 'Employee Directory Viewer', 'description': 'Can see the employee directory.',
        }, format='json')
        self.assertEqual(role_response.status_code, status.HTTP_201_CREATED)
        viewer_role_id = role_response.data['id']
        employee_view_permission = Permission.objects.get(codename='employee.view')
        self.assertEqual(self.client.post('/api/v1/authorization/role-permissions/', {
            'role': viewer_role_id, 'permission': employee_view_permission.id,
        }, format='json').status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.client.post('/api/v1/authorization/user-roles/', {
            'user': employee.user_id, 'role': viewer_role_id,
        }, format='json').status_code, status.HTTP_201_CREATED)

        activation = self.client.post(reverse('activate'), {
            'uid': urlsafe_base64_encode(force_bytes(employee.user_id)),
            'token': default_token_generator.make_token(employee.user),
            'password': 'EmployeePassword123!',
        })
        self.assertEqual(activation.status_code, status.HTTP_200_OK)
        employee.user.refresh_from_db()
        self.client.force_authenticate(user=employee.user)
        employee_access = self.client.get('/api/v1/authorization/me/')
        self.assertEqual(employee_access.status_code, status.HTTP_200_OK)
        self.assertIn('employee.view', employee_access.data['permissions'])
        self.assertFalse(employee_access.data['user']['is_superuser'])

        self.client.force_authenticate(user=owner_a)

        employees = self.client.get('/api/v1/employees/management/')
        self.assertEqual(employees.status_code, status.HTTP_200_OK)
        employee_ids = [item['id'] for item in employees.data]
        self.assertIn(employee.id, employee_ids)
        self.assertNotIn(branch_b.id, [item.get('branch') for item in employees.data])

    def test_headless_superadmin_can_update_own_account_profile(self):
        superadmin = User.objects.create_superuser(email='client@example.com', password='Password123!')
        self.client.force_authenticate(user=superadmin)

        response = self.client.patch(reverse('me'), {'first_name': 'Client', 'last_name': 'Admin'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        superadmin.refresh_from_db()
        self.assertEqual(superadmin.get_full_name(), 'Client Admin')
        self.assertFalse(Employee.objects.filter(user=superadmin).exists())

class EmployeeSelfServiceAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        org = Organization.objects.create(name='Org')
        branch = Branch.objects.create(organization=org, name='HQ')
        policy = branch.attendance_policy
        policy.is_office_gps_enabled = False
        policy.is_office_ip_enabled = False
        policy.save()
        self.user = User.objects.create_user(email='employee@company.com', password='Password123!', status='active')
        self.employee = Employee.objects.create(user=self.user, employee_code='EMP001', phone_number='12345', organization=org)

        self.other_user = User.objects.create_user(email='other@company.com', password='Password123!', status='active')
        self.other_employee = Employee.objects.create(user=self.other_user, employee_code='EMP002', organization=org)

        self.client.force_authenticate(user=self.user)
        self.me_url = reverse('employee-me')

        OfficeNetwork.objects.create(branch=branch, name='TestNet', network='127.0.0.0/8', is_active=True)

    def test_can_modify_self_service_fields(self):
        response = self.client.patch(self.me_url, {
            'phone_number': '98765',
            'address': '123 Main St'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.phone_number, '98765')
        self.assertEqual(self.employee.address, '123 Main St')

    def test_cannot_modify_hr_controlled_fields(self):
        response = self.client.patch(self.me_url, {
            'employee_code': 'HACKED001',
            'email': 'hacked@company.com',
            'status': 'inactive'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.employee_code, 'EMP001')
        self.assertEqual(self.employee.user.email, 'employee@company.com')
        self.assertEqual(self.employee.user.status, 'active')

    def test_cannot_idor_modify_other_employee(self):
        # We try to pass another user's ID to see if it modifies them. It shouldn't, because the view uses request.user.employee explicitly.
        response = self.client.patch(self.me_url, {
            'id': self.other_employee.id,
            'phone_number': 'hacked-number'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.other_employee.refresh_from_db()
        self.assertNotEqual(self.other_employee.phone_number, 'hacked-number')
        # It modifies our own instead
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.phone_number, 'hacked-number')

class ProvisioningAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org = Organization.objects.create(name='Org')
        self.hr_user = User.objects.create_user(email='hr@company.com', password='Password123!', status='active')
        self.hr_emp = Employee.objects.create(user=self.hr_user, organization=self.org, employee_code='HR_ADMIN_01')
        self.regular_user = User.objects.create_user(email='regular@company.com', password='Password123!', status='active')
        self.provision_url = reverse('employee-provision')

        self.branch = Branch.objects.create(organization=self.org, name='HQ')
        self.role = Role.objects.create(organization=self.org, name='HR Role')
        self.perm = Permission.objects.create(name='Create Employee', codename='employee.create', resource='employee', action='create')
        RolePermission.objects.create(role=self.role, permission=self.perm)
        UserRole.objects.create(user=self.hr_user, role=self.role)
        OfficeNetwork.objects.create(branch=self.branch, name='TestNet', network='127.0.0.0/8', is_active=True)

    def test_unauthenticated_user_cannot_provision(self):
        response = self.client.post(self.provision_url, {
            'email': 'new@company.com', 'personal_email': 'new.p@gmail.com', 'first_name': 'New', 'last_name': 'Employee', 'employee_code': 'EMP003'
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthorized_user_cannot_provision(self):
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.post(self.provision_url, {
            'email': 'new@company.com', 'personal_email': 'new.p@gmail.com', 'first_name': 'New', 'last_name': 'Employee', 'employee_code': 'EMP003'
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_authorized_user_can_provision(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(self.provision_url, {
            'email': 'new@company.com', 'personal_email': 'new.p@gmail.com', 'first_name': 'New', 'last_name': 'Employee', 'employee_code': 'EMP003'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email='new@company.com').exists())
        self.assertTrue(Employee.objects.filter(employee_code='EMP003').exists())
        # SECURITY: activation token must NEVER appear in the API response
        self.assertNotIn('activation_info', response.data)
        self.assertNotIn('token', response.data)
        # Onboarding email status must always be present
        self.assertIn('onboarding_email_status', response.data)

    @patch('apps.employees.views.NotificationService.send_employee_onboarding_email', return_value=True)
    def test_invitation_defaults_to_work_email(self, send_invite):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(self.provision_url, {
            'email': 'work-email@company.com', 'first_name': 'Work', 'last_name': 'Email', 'employee_code': 'EMP007'
        })

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['onboarding_email_status'], 'sent')
        self.assertEqual(send_invite.call_args.kwargs['recipient_email'], 'work-email@company.com')

    def test_duplicate_employee_code_rejected(self):
        User.objects.create_user(email='existing@company.com', password='Password123!')
        Employee.objects.create(user=User.objects.get(email='existing@company.com'), employee_code='EMP005')
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(self.provision_url, {
            'email': 'new@company.com', 'first_name': 'New', 'last_name': 'Employee', 'employee_code': 'EMP005'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("An employee with this code already exists.", str(response.data))

    def test_duplicate_email_rejected(self):
        self.client.force_authenticate(user=self.hr_user)
        response = self.client.post(self.provision_url, {
            'email': 'hr@company.com', 'first_name': 'New', 'last_name': 'Employee', 'employee_code': 'EMP006'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("A user with this email already exists.", str(response.data))

class HTTPStatusMatrixTests(TestCase):
    def setUp(self):
        from rest_framework.test import APIClient
        self.client = APIClient()
        from apps.organization.models import Organization, OfficeNetwork
        org = Organization.objects.create(name='MatrixOrg')
        branch = Branch.objects.create(organization=org, name='MatrixHQ')
        policy = branch.attendance_policy
        policy.is_office_gps_enabled = False
        policy.is_office_ip_enabled = False
        policy.save()
        self.active_user = User.objects.create_user(email='matrix_active@company.com', password='Password123!', status='active')
        self.employee = Employee.objects.create(user=self.active_user, employee_code='MAT001', organization=org)

        self.deactivated_user = User.objects.create_user(email='matrix_deact@company.com', password='Password123!', status='inactive')
        self.deactivated_employee = Employee.objects.create(user=self.deactivated_user, employee_code='MAT002', organization=org)

        self.superadmin = User.objects.create_user(email='matrix_super@company.com', password='Password123!', status='active', is_superuser=True)
        self.super_employee = Employee.objects.create(user=self.superadmin, employee_code='MAT003', organization=org)

        OfficeNetwork.objects.create(branch=branch, name='MatrixNet', network='127.0.0.0/8', is_active=True)

    def get_token(self, user):
        from rest_framework.authtoken.models import Token
        token, _ = Token.objects.get_or_create(user=user)
        return token.key

    def test_missing_credentials(self):
        response = self.client.get(reverse('employee-me'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_credentials(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token invalidtoken')
        response = self.client.get(reverse('employee-me'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_deactivated_user(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.get_token(self.deactivated_user))
        response = self.client.get(reverse('employee-me'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_active_user_without_rbac(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.get_token(self.active_user))
        response = self.client.post(reverse('employee-provision'), {})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_active_employee_external_ip_without_wfh(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.get_token(self.active_user))
        # Simulate external IP by modifying REMOTE_ADDR
        response = self.client.get(reverse('employee-me'), REMOTE_ADDR='8.8.8.8')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_active_employee_approved_wfh(self):
        from apps.employees.models import WFHRequest
        from django.utils import timezone
        import datetime
        now = timezone.now()
        WFHRequest.objects.create(
            employee=self.employee,
            status='approved',
            start_at=now - datetime.timedelta(days=1),
            end_at=now + datetime.timedelta(days=1)
        )
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.get_token(self.active_user))
        response = self.client.get(reverse('employee-me'), REMOTE_ADDR='8.8.8.8')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_superadmin_external_ip(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.get_token(self.superadmin))
        response = self.client.get(reverse('employee-me'), REMOTE_ADDR='8.8.8.8')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_active_valid_token(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.get_token(self.superadmin))
        response = self.client.get(reverse('employee-me'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_reactivated_user(self):
        token_key = self.get_token(self.deactivated_user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + token_key)
        # Should be 401 while deactivated
        response = self.client.get(reverse('employee-me'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Reactivate
        self.deactivated_user.status = 'active'
        self.deactivated_user.save()

        # In order for this not to fail with 403 due to network, we can give them WFH or make them superadmin, or just run it without external IP
        # Default test client has no REMOTE_ADDR unless specified, which means it evaluates as local/office by default!
        response = self.client.get(reverse('employee-me'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ChangePasswordAPITests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='testuser@company.com',
            password='CurrentStrongPassword123!',
            status='active'
        )
        self.employee = Employee.objects.create(user=self.user, employee_code='EMP999')
        from rest_framework.authtoken.models import Token
        self.token = Token.objects.create(user=self.user)
        self.url = reverse('password_change')

    def test_unauthenticated_cannot_change_password(self):
        response = self.client.post(self.url, {
            'old_password': 'CurrentStrongPassword123!',
            'new_password': 'NewStrongPassword456!',
            'confirm_password': 'NewStrongPassword456!'
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_user_can_change_password(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        response = self.client.post(self.url, {
            'old_password': 'CurrentStrongPassword123!',
            'new_password': 'NewStrongPassword456!',
            'confirm_password': 'NewStrongPassword456!'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewStrongPassword456!'))

    def test_change_password_fails_with_incorrect_old_password(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        response = self.client.post(self.url, {
            'old_password': 'WrongPassword123!',
            'new_password': 'NewStrongPassword456!',
            'confirm_password': 'NewStrongPassword456!'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('old_password', response.data)

    def test_change_password_fails_with_mismatched_confirmation(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        response = self.client.post(self.url, {
            'old_password': 'CurrentStrongPassword123!',
            'new_password': 'NewStrongPassword456!',
            'confirm_password': 'DifferentPassword456!'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('confirm_password', response.data)

    def test_change_password_fails_if_same_as_old(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        response = self.client.post(self.url, {
            'old_password': 'CurrentStrongPassword123!',
            'new_password': 'CurrentStrongPassword123!',
            'confirm_password': 'CurrentStrongPassword123!'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('new_password', response.data)
