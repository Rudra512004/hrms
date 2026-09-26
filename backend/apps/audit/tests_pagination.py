from unittest.mock import patch
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.organization.models import Organization, Branch
from apps.employees.models import Employee
from apps.authorization.models import Permission, UserPermissionGrant
from apps.audit.models import AuditLog

User = get_user_model()

class AuditLogPaginationTests(TestCase):
    def setUp(self):
        self.patcher = patch('apps.authorization.permissions.IsNetworkAllowed.has_permission', return_value=True)
        self.patcher.start()
        self.client = APIClient()

        self.org1 = Organization.objects.create(name='Audit Org 1')
        self.org2 = Organization.objects.create(name='Audit Org 2')

        # Superuser
        self.superuser = User.objects.create_superuser(email='super@audit.com', password='password123')
        self.super_emp = Employee.objects.create(
            user=self.superuser, organization=self.org1, employee_code='SUP-AUD'
        )

        # Authorized Auditor for Org 1
        self.auditor_user = User.objects.create_user(email='auditor@audit.com', password='password123', status='active')
        self.auditor_emp = Employee.objects.create(
            user=self.auditor_user, organization=self.org1, employee_code='AUD-01'
        )

        perm_audit, _ = Permission.objects.get_or_create(
            codename='audit.view', resource='audit', action='view', defaults={'name': 'View Audit Logs'}
        )
        UserPermissionGrant.objects.create(user=self.auditor_user, permission=perm_audit)
        UserPermissionGrant.objects.create(user=self.superuser, permission=perm_audit)

        # Unauthorized User
        self.unauth_user = User.objects.create_user(email='unauth@audit.com', password='password123', status='active')
        Employee.objects.create(
            user=self.unauth_user, organization=self.org1, employee_code='UNAUTH-01'
        )

        # Create 25 audit logs for Org 1
        for i in range(25):
            AuditLog.objects.create(
                organization=self.org1,
                actor=self.superuser,
                action='employee_created' if i % 2 == 0 else 'role_assigned',
                target_type='Employee',
                target_id=str(100 + i),
                ip_address='127.0.0.1'
            )

        # Create 5 audit logs for Org 2
        for j in range(5):
            AuditLog.objects.create(
                organization=self.org2,
                actor=self.superuser,
                action='branch_created',
                target_type='Branch',
                target_id=str(200 + j),
                ip_address='127.0.0.1'
            )

        self.url = '/api/v1/audit-logs/'

    def tearDown(self):
        self.patcher.stop()

    def test_unpaginated_request_returns_array(self):
        self.client.force_authenticate(user=self.superuser)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIsInstance(res.data, list)
        self.assertEqual(len(res.data), 30)

    def test_paginate_true_returns_standard_drf_envelope(self):
        self.client.force_authenticate(user=self.superuser)
        res = self.client.get(f'{self.url}?paginate=true')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIsInstance(res.data, dict)
        self.assertIn('count', res.data)
        self.assertIn('next', res.data)
        self.assertIn('previous', res.data)
        self.assertIn('results', res.data)
        self.assertEqual(res.data['count'], 30)
        self.assertEqual(len(res.data['results']), 20)

    def test_page_and_page_size_query_params(self):
        self.client.force_authenticate(user=self.superuser)
        res = self.client.get(f'{self.url}?paginate=true&page=2&page_size=10')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['count'], 30)
        self.assertEqual(len(res.data['results']), 10)

    def test_filters_with_and_without_pagination(self):
        self.client.force_authenticate(user=self.superuser)
        # Filter action unpaginated
        res_unpaginated = self.client.get(f'{self.url}?action=branch_created')
        self.assertEqual(res_unpaginated.status_code, status.HTTP_200_OK)
        self.assertIsInstance(res_unpaginated.data, list)
        self.assertEqual(len(res_unpaginated.data), 5)

        # Filter action paginated
        res_paginated = self.client.get(f'{self.url}?paginate=true&action=branch_created')
        self.assertEqual(res_paginated.status_code, status.HTTP_200_OK)
        self.assertIsInstance(res_paginated.data, dict)
        self.assertEqual(res_paginated.data['count'], 5)
        self.assertEqual(len(res_paginated.data['results']), 5)

    def test_authorization_scope_preserved(self):
        # Unauthorized user rejected with 403
        self.client.force_authenticate(user=self.unauth_user)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # Auditor for Org 1 only sees Org 1 logs (25 logs)
        self.client.force_authenticate(user=self.auditor_user)
        res_auditor = self.client.get(f'{self.url}?paginate=true')
        self.assertEqual(res_auditor.status_code, status.HTTP_200_OK)
        self.assertEqual(res_auditor.data['count'], 25)
