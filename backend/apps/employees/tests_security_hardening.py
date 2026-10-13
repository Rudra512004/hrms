from datetime import date, timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.authorization.models import Permission, Role, RolePermission, ScopeChoices, UserRole
from apps.employees.models import (
    Employee,
    EmployeeDependent,
    EmployeeEducation,
    EmployeePriorExperience,
    EmployeeStatutoryAndBank,
)
from apps.organization.models import Organization

User = get_user_model()


class SecurityHardeningTests(TestCase):
    """
    Automated security verification suite for BeyondSure HRMS:
    1. Token TTL Expiration & Safe Logout
    2. Employee Statutory & Bank Details IDOR Protection
    3. Employee Profile Sub-resources (Dependents, Education, Prior Experience) IDOR Protection
    4. Data Import File Validation (File types and file size)
    5. Security Headers (X-Frame-Options, X-Content-Type-Options)
    """

    def setUp(self):
        self.network_patch = patch('apps.authorization.permissions.IsNetworkAllowed.has_permission', return_value=True)
        self.network_patch.start()

        self.client = APIClient()
        self.org = Organization.objects.create(name='Acme Corp')

        # Admin user with full employee permissions
        self.admin_user = User.objects.create_user(
            email='admin@acme.com', password='AdminPassword123!', status='active'
        )
        self.admin_employee = Employee.objects.create(
            user=self.admin_user, employee_code='EMP_ADM', organization=self.org
        )
        self.admin_role = Role.objects.create(organization=self.org, name='HR Admin')
        for perm_code in [
            'employee.view', 'employee.manage', 'employee.manage_statutory', 'employee.view_statutory',
            'data_import.view', 'data_import.execute'
        ]:
            resource, action = perm_code.split('.')
            perm, _ = Permission.objects.get_or_create(
                codename=perm_code, defaults={'name': perm_code, 'resource': resource, 'action': action}
            )
            RolePermission.objects.get_or_create(role=self.admin_role, permission=perm)
        UserRole.objects.create(user=self.admin_user, role=self.admin_role, scope=ScopeChoices.ORGANIZATION)

        # Employee A (standard employee, no admin permissions)
        self.user_a = User.objects.create_user(
            email='user_a@acme.com', password='UserAPassword123!', status='active'
        )
        self.emp_a = Employee.objects.create(
            user=self.user_a, employee_code='EMP_A', organization=self.org
        )

        # Employee B (standard employee, no admin permissions)
        self.user_b = User.objects.create_user(
            email='user_b@acme.com', password='UserBPassword123!', status='active'
        )
        self.emp_b = Employee.objects.create(
            user=self.user_b, employee_code='EMP_B', organization=self.org
        )

    def tearDown(self):
        self.network_patch.stop()

    # -------------------------------------------------------------------------
    # 1. Token TTL Expiration & Safe Logout Tests
    # -------------------------------------------------------------------------
    def test_expired_token_rejected_with_401(self):
        """Tokens older than TOKEN_TTL_HOURS must be rejected with 401."""
        token, _ = Token.objects.get_or_create(user=self.user_a)
        # Manually backdate the created timestamp past the 24-hour TTL
        Token.objects.filter(pk=token.pk).update(
            created=timezone.now() - timedelta(hours=25)
        )

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        response = self.client.get(reverse('employee-statutory-list'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('Token has expired', response.data.get('detail', ''))

    def test_active_token_accepted(self):
        """Tokens within TOKEN_TTL_HOURS must authenticate successfully."""
        token, _ = Token.objects.get_or_create(user=self.user_a)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        response = self.client.get(reverse('employee-statutory-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_login_rotates_expired_token(self):
        """Logging in when an expired token exists rotates it and returns a new token."""
        old_token, _ = Token.objects.get_or_create(user=self.user_a)
        Token.objects.filter(pk=old_token.pk).update(
            created=timezone.now() - timedelta(hours=25)
        )
        old_key = old_token.key

        response = self.client.post(
            reverse('login'),
            {'email': 'user_a@acme.com', 'password': 'UserAPassword123!'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        new_key = response.data.get('token')
        self.assertNotEqual(old_key, new_key)
        self.assertFalse(Token.objects.filter(key=old_key).exists())
        self.assertTrue(Token.objects.filter(key=new_key, user=self.user_a).exists())

    def test_safe_logout_idempotency(self):
        """Logout must delete the token and remain safe/idempotent even if token is already gone."""
        token, _ = Token.objects.get_or_create(user=self.user_a)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        response = self.client.post(reverse('logout'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Token.objects.filter(user=self.user_a).exists())

        # Second logout call must return 200 without crashing with 500
        self.client.force_authenticate(user=self.user_a)
        response2 = self.client.post(reverse('logout'))
        self.assertEqual(response2.status_code, status.HTTP_200_OK)

    # -------------------------------------------------------------------------
    # 2. Statutory and Bank Details IDOR Tests
    # -------------------------------------------------------------------------
    def test_statutory_and_bank_idor_isolation(self):
        """
        Non-admin employees must not be able to list, view, or update other
        employees' sensitive statutory and bank details.
        """
        # Create bank details for Employee A
        stat_a = EmployeeStatutoryAndBank.objects.create(
            employee=self.emp_a,
            bank_name='Bank of A',
            account_number='111122223333',
            ifsc_code='BANK0001234',
            pan_number='ABCDE1234F',
            uan_number='100000000001'
        )

        # Authenticate as Employee B
        self.client.force_authenticate(user=self.user_b)

        # Employee B listing statutory records must only see their own (empty), NOT A's
        list_response = self.client.get(reverse('employee-statutory-list'))
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        results = list_response.data if isinstance(list_response.data, list) else list_response.data.get('results', [])
        for item in results:
            self.assertNotEqual(item.get('id'), stat_a.id)
            self.assertNotEqual(item.get('bank_name'), 'Bank of A')

        # Employee B attempting direct retrieval of A's record must be rejected with 404
        detail_response = self.client.get(
            reverse('employee-statutory-detail', kwargs={'pk': stat_a.pk})
        )
        self.assertEqual(detail_response.status_code, status.HTTP_404_NOT_FOUND)

        # Employee B attempting to update A's record must be rejected with 404
        update_response = self.client.patch(
            reverse('employee-statutory-detail', kwargs={'pk': stat_a.pk}),
            {'bank_name': 'Attacker Bank'}
        )
        self.assertEqual(update_response.status_code, status.HTTP_404_NOT_FOUND)
        stat_a.refresh_from_db()
        self.assertEqual(stat_a.bank_name, 'Bank of A')

        # Admin user CAN view A's statutory details
        self.client.force_authenticate(user=self.admin_user)
        admin_response = self.client.get(
            reverse('employee-statutory-detail', kwargs={'pk': stat_a.pk})
        )
        self.assertEqual(admin_response.status_code, status.HTTP_200_OK)
        self.assertEqual(admin_response.data.get('bank_name'), 'Bank of A')

    # -------------------------------------------------------------------------
    # 3. Employee Profile Sub-resources IDOR Tests
    # -------------------------------------------------------------------------
    def test_dependents_idor_isolation(self):
        """Non-admin employees must not be able to list, view, or modify other employees' dependents."""
        dep_a = EmployeeDependent.objects.create(
            employee=self.emp_a,
            full_name='Dependent Child A',
            relationship='Child'
        )

        # Employee B listing dependents must not see A's dependent
        self.client.force_authenticate(user=self.user_b)
        list_response = self.client.get(reverse('employee-dependents-list'))
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        results = list_response.data if isinstance(list_response.data, list) else list_response.data.get('results', [])
        for item in results:
            self.assertNotEqual(item.get('id'), dep_a.id)

        # Employee B trying to view or edit A's dependent directly
        detail_response = self.client.get(reverse('employee-dependents-detail', kwargs={'pk': dep_a.pk}))
        self.assertEqual(detail_response.status_code, status.HTTP_404_NOT_FOUND)

        update_response = self.client.patch(
            reverse('employee-dependents-detail', kwargs={'pk': dep_a.pk}),
            {'full_name': 'Modified By B'}
        )
        self.assertEqual(update_response.status_code, status.HTTP_404_NOT_FOUND)
        dep_a.refresh_from_db()
        self.assertEqual(dep_a.full_name, 'Dependent Child A')

    def test_education_idor_isolation(self):
        """Non-admin employees must not be able to list, view, or modify other employees' education records."""
        edu_a = EmployeeEducation.objects.create(
            employee=self.emp_a,
            degree='B.Tech',
            institution='Tech University',
            completion_year=2020
        )

        self.client.force_authenticate(user=self.user_b)
        detail_response = self.client.get(reverse('employee-education-detail', kwargs={'pk': edu_a.pk}))
        self.assertEqual(detail_response.status_code, status.HTTP_404_NOT_FOUND)

        update_response = self.client.patch(
            reverse('employee-education-detail', kwargs={'pk': edu_a.pk}),
            {'degree': 'Forged Degree'}
        )
        self.assertEqual(update_response.status_code, status.HTTP_404_NOT_FOUND)
        edu_a.refresh_from_db()
        self.assertEqual(edu_a.degree, 'B.Tech')

    def test_prior_experience_idor_isolation(self):
        """Non-admin employees must not be able to list, view, or modify other employees' prior experience."""
        exp_a = EmployeePriorExperience.objects.create(
            employee=self.emp_a,
            employer_name='Previous Tech Ltd',
            designation='Engineer',
            start_date=date(2021, 1, 1),
            end_date=date(2023, 1, 1)
        )

        self.client.force_authenticate(user=self.user_b)
        detail_response = self.client.get(reverse('employee-experience-detail', kwargs={'pk': exp_a.pk}))
        self.assertEqual(detail_response.status_code, status.HTTP_404_NOT_FOUND)

        update_response = self.client.patch(
            reverse('employee-experience-detail', kwargs={'pk': exp_a.pk}),
            {'employer_name': 'Attacker Corp'}
        )
        self.assertEqual(update_response.status_code, status.HTTP_404_NOT_FOUND)
        exp_a.refresh_from_db()
        self.assertEqual(exp_a.employer_name, 'Previous Tech Ltd')

    # -------------------------------------------------------------------------
    # 4. Data Import File Validation Tests
    # -------------------------------------------------------------------------
    def test_data_import_rejects_executable_and_script_files(self):
        """Data import upload must reject non-CSV/script files."""
        self.client.force_authenticate(user=self.admin_user)
        malicious_file = SimpleUploadedFile(
            'malicious.py',
            b'import os; os.system("echo hacked")',
            content_type='text/x-python'
        )
        response = self.client.post(
            reverse('data-import-jobs-list'),
            {'template_key': 'employees', 'file': malicious_file},
            format='multipart'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('file', response.data)
        self.assertIn('not allowed', str(response.data['file']))

    def test_data_import_rejects_oversized_files(self):
        """Data import upload must reject files exceeding MAX_IMPORT_FILE_SIZE."""
        self.client.force_authenticate(user=self.admin_user)
        large_size = 10 * 1024 * 1024 + 1024
        oversized_file = SimpleUploadedFile(
            'large.csv',
            b'0' * large_size,
            content_type='text/csv'
        )
        response = self.client.post(
            reverse('data-import-jobs-list'),
            {'template_key': 'employees', 'file': oversized_file},
            format='multipart'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('file', response.data)
        self.assertIn('exceeds the maximum allowed limit', str(response.data['file']))

    def test_data_import_accepts_valid_csv(self):
        """Data import upload must accept valid CSV file within size limit."""
        self.client.force_authenticate(user=self.admin_user)
        valid_csv = SimpleUploadedFile(
            'employees.csv',
            b'First Name,Last Name,Email\nJohn,Doe,john.doe@example.com\n',
            content_type='text/csv'
        )
        response = self.client.post(
            reverse('data-import-jobs-list'),
            {'template_key': 'employees', 'file': valid_csv},
            format='multipart'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data.get('status'), 'pending')

    # -------------------------------------------------------------------------
    # 5. Security Headers Tests
    # -------------------------------------------------------------------------
    def test_security_headers_present_in_responses(self):
        """Responses must include X-Frame-Options: DENY and X-Content-Type-Options: nosniff."""
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(reverse('employee-statutory-list'))
        self.assertEqual(response.headers.get('X-Frame-Options'), 'DENY')
        self.assertEqual(response.headers.get('X-Content-Type-Options'), 'nosniff')

    # -------------------------------------------------------------------------
    # 6. Additional Defense-in-Depth Tests
    # -------------------------------------------------------------------------
    def test_duplicate_statutory_creation_rejected(self):
        """Attempting to create another statutory record when one exists returns 400."""
        self.client.force_authenticate(user=self.admin_user)
        EmployeeStatutoryAndBank.objects.create(
            employee=self.emp_a, bank_name='First Bank'
        )
        response = self.client.post(
            reverse('employee-statutory-list'),
            {'employee': self.emp_a.id, 'bank_name': 'Duplicate Bank'}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already exist', str(response.data))

    def test_cross_tenant_statutory_access_blocked_for_admin(self):
        """Admin in Org 1 cannot view or modify statutory records for Employee in Org 2."""
        org2 = Organization.objects.create(name='Other Tenant')
        user_c = User.objects.create_user(email='c@other.com', password='Password123!', status='active')
        emp_c = Employee.objects.create(user=user_c, employee_code='EMP_C', organization=org2)
        stat_c = EmployeeStatutoryAndBank.objects.create(employee=emp_c, bank_name='Org 2 Bank')

        # Admin of Org 1 attempts to access Org 2 employee's record
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(
            reverse('employee-statutory-detail', kwargs={'pk': stat_c.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Admin of Org 1 attempts to update Org 2 employee's record
        update_response = self.client.patch(
            reverse('employee-statutory-detail', kwargs={'pk': stat_c.pk}),
            {'bank_name': 'Hacked Org 2 Bank'}
        )
        self.assertEqual(update_response.status_code, status.HTTP_404_NOT_FOUND)
        stat_c.refresh_from_db()
        self.assertEqual(stat_c.bank_name, 'Org 2 Bank')

    def test_password_change_invalidates_old_token(self):
        """Changing password revokes old auth token and issues a new one."""
        token, _ = Token.objects.get_or_create(user=self.user_a)
        old_key = token.key

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {old_key}')
        response = self.client.post(reverse('password_change'), {
            'old_password': 'UserAPassword123!',
            'new_password': 'BrandNewPassword123!',
            'confirm_password': 'BrandNewPassword123!'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        new_key = response.data.get('token')
        self.assertNotEqual(old_key, new_key)
        self.assertFalse(Token.objects.filter(key=old_key).exists())

        # Old token cannot be used anymore
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {old_key}')
        denied_response = self.client.get(reverse('employee-statutory-list'))
        self.assertEqual(denied_response.status_code, status.HTTP_401_UNAUTHORIZED)

