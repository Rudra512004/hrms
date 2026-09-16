from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from apps.organization.models import Organization, Branch, OfficeNetwork
from apps.employees.models import Employee, EmploymentStatus, WFHRequest
from apps.authorization.models import Role, Permission, RolePermission, UserRole
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


class TenantWFHAndProvisioningSecurityTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Organizations
        self.org_a = Organization.objects.create(name='Org Alpha')
        self.org_b = Organization.objects.create(name='Org Beta')

        # Office networks (to satisfy IsNetworkAllowed for local testing)
        self.branch_a = Branch.objects.create(organization=self.org_a, name='HQ Alpha')
        self.branch_b = Branch.objects.create(organization=self.org_b, name='HQ Beta')
        OfficeNetwork.objects.create(branch=self.branch_a, name='Net A', network='127.0.0.1/32', is_active=True)
        OfficeNetwork.objects.create(branch=self.branch_b, name='Net B', network='127.0.0.1/32', is_active=True)

        # Permissions
        perm_codes = ['wfh.view', 'wfh.approve', 'wfh.reject', 'wfh.cancel', 'employee.create', 'employee.view']
        perms = {}
        for code in perm_codes:
            res, act = code.split('.')
            p, _ = Permission.objects.get_or_create(
                codename=code,
                defaults={'name': code, 'resource': res, 'action': act}
            )
            perms[code] = p

        # Users & Employees in Org A
        self.admin_a = User.objects.create_user(email='admin_a@alpha.local', password='Password123!', status='active')
        self.emp_profile_admin_a = Employee.objects.create(
            user=self.admin_a, organization=self.org_a, employee_code='EMP-A-001', employment_status=EmploymentStatus.ACTIVE
        )
        role_a = Role.objects.create(organization=self.org_a, name='Admin Role A')
        for p in perms.values():
            RolePermission.objects.create(role=role_a, permission=p)
        UserRole.objects.create(user=self.admin_a, role=role_a)

        self.user_emp_a = User.objects.create_user(email='emp_a@alpha.local', password='Password123!', status='active')
        self.emp_profile_a = Employee.objects.create(
            user=self.user_emp_a, organization=self.org_a, employee_code='EMP-A-002', employment_status=EmploymentStatus.ACTIVE
        )

        # Users & Employees in Org B
        self.admin_b = User.objects.create_user(email='admin_b@beta.local', password='Password123!', status='active')
        self.emp_profile_admin_b = Employee.objects.create(
            user=self.admin_b, organization=self.org_b, employee_code='EMP-B-001', employment_status=EmploymentStatus.ACTIVE
        )
        role_b = Role.objects.create(organization=self.org_b, name='Admin Role B')
        for p in perms.values():
            RolePermission.objects.create(role=role_b, permission=p)
        UserRole.objects.create(user=self.admin_b, role=role_b)

        self.user_emp_b = User.objects.create_user(email='emp_b@beta.local', password='Password123!', status='active')
        self.emp_profile_b = Employee.objects.create(
            user=self.user_emp_b, organization=self.org_b, employee_code='EMP-B-002', employment_status=EmploymentStatus.ACTIVE
        )

        # WFH requests
        now = timezone.now()
        self.wfh_a = WFHRequest.objects.create(
            employee=self.emp_profile_a,
            start_at=now + timedelta(days=1),
            end_at=now + timedelta(days=2),
            reason='Org A request',
            status='pending'
        )
        self.wfh_b = WFHRequest.objects.create(
            employee=self.emp_profile_b,
            start_at=now + timedelta(days=1),
            end_at=now + timedelta(days=2),
            reason='Org B request',
            status='pending'
        )

    # --- WFH Request Isolation Tests ---

    def test_wfh_list_is_scoped_to_organization(self):
        """Admin A with wfh.view only sees Org A WFH requests."""
        self.client.force_authenticate(user=self.admin_a)
        resp = self.client.get('/api/v1/employees/wfh-requests/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = [item['id'] for item in resp.data]
        self.assertIn(self.wfh_a.id, ids)
        self.assertNotIn(self.wfh_b.id, ids)

    def test_wfh_retrieve_idor_blocked(self):
        """Admin A cannot retrieve Org B WFH request (returns 404)."""
        self.client.force_authenticate(user=self.admin_a)
        resp = self.client.get(f'/api/v1/employees/wfh-requests/{self.wfh_b.id}/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_wfh_approve_cross_tenant_blocked(self):
        """Admin A cannot approve Org B WFH request (returns 404)."""
        self.client.force_authenticate(user=self.admin_a)
        resp = self.client.post(f'/api/v1/employees/wfh-requests/{self.wfh_b.id}/approve/', {
            'reviewer_comment': 'Malicious cross-tenant approval'
        })
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.wfh_b.refresh_from_db()
        self.assertEqual(self.wfh_b.status, 'pending')

    def test_wfh_reject_cross_tenant_blocked(self):
        """Admin A cannot reject Org B WFH request (returns 404)."""
        self.client.force_authenticate(user=self.admin_a)
        resp = self.client.post(f'/api/v1/employees/wfh-requests/{self.wfh_b.id}/reject/', {
            'reviewer_comment': 'Malicious cross-tenant rejection'
        })
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.wfh_b.refresh_from_db()
        self.assertEqual(self.wfh_b.status, 'pending')

    def test_wfh_cancel_cross_tenant_blocked(self):
        """Admin A cannot cancel Org B WFH request (returns 404)."""
        self.client.force_authenticate(user=self.admin_a)
        resp = self.client.post(f'/api/v1/employees/wfh-requests/{self.wfh_b.id}/cancel/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.wfh_b.refresh_from_db()
        self.assertEqual(self.wfh_b.status, 'pending')

    # --- Employee Provisioning Tenant Isolation Tests ---

    def test_employee_provisioning_binds_to_creator_organization(self):
        """Provisioning an employee via ProvisionEmployeeView automatically binds them to Org A."""
        self.client.force_authenticate(user=self.admin_a)
        resp = self.client.post('/api/v1/employees/', {
            'email': 'new_recruit_a@alpha.local',
            'first_name': 'New',
            'last_name': 'Recruit',
            'personal_email': 'personal_a@test.local'
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        new_emp_id = resp.data['employee']['id']
        new_emp = Employee.objects.get(id=new_emp_id)
        self.assertEqual(new_emp.organization, self.org_a)

        # Admin A can see the new recruit
        list_resp_a = self.client.get('/api/v1/employees/management/')
        self.assertEqual(list_resp_a.status_code, status.HTTP_200_OK)
        ids_a = [e['id'] for e in list_resp_a.data]
        self.assertIn(new_emp.id, ids_a)

        # Admin B cannot see the new recruit
        self.client.force_authenticate(user=self.admin_b)
        list_resp_b = self.client.get('/api/v1/employees/management/')
        self.assertEqual(list_resp_b.status_code, status.HTTP_200_OK)
        ids_b = [e['id'] for e in list_resp_b.data]
        self.assertNotIn(new_emp.id, ids_b)

    def test_wfh_same_tenant_retrieve_approve_reject_cancel(self):
        """Admin A can retrieve, approve, reject, and cancel same-tenant WFH requests."""
        self.client.force_authenticate(user=self.admin_a)

        # 1. Retrieve same-tenant
        ret_resp = self.client.get(f'/api/v1/employees/wfh-requests/{self.wfh_a.id}/')
        self.assertEqual(ret_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(ret_resp.data['id'], self.wfh_a.id)

        # 2. Approve same-tenant
        appr_resp = self.client.post(f'/api/v1/employees/wfh-requests/{self.wfh_a.id}/approve/', {
            'reviewer_comment': 'Approved by Admin A'
        })
        self.assertEqual(appr_resp.status_code, status.HTTP_200_OK)
        self.wfh_a.refresh_from_db()
        self.assertEqual(self.wfh_a.status, 'approved')

        # 3. Reject same-tenant
        wfh_a2 = WFHRequest.objects.create(
            employee=self.emp_profile_a,
            start_at=timezone.now() + timedelta(days=3),
            end_at=timezone.now() + timedelta(days=4),
            reason='Org A second request',
            status='pending'
        )
        rej_resp = self.client.post(f'/api/v1/employees/wfh-requests/{wfh_a2.id}/reject/', {
            'reviewer_comment': 'Rejected by Admin A'
        })
        self.assertEqual(rej_resp.status_code, status.HTTP_200_OK)
        wfh_a2.refresh_from_db()
        self.assertEqual(wfh_a2.status, 'rejected')

        # 4. Cancel same-tenant
        wfh_a3 = WFHRequest.objects.create(
            employee=self.emp_profile_a,
            start_at=timezone.now() + timedelta(days=5),
            end_at=timezone.now() + timedelta(days=6),
            reason='Org A third request',
            status='pending'
        )
        canc_resp = self.client.post(f'/api/v1/employees/wfh-requests/{wfh_a3.id}/cancel/')
        self.assertEqual(canc_resp.status_code, status.HTTP_200_OK)
        wfh_a3.refresh_from_db()
        self.assertEqual(wfh_a3.status, 'cancelled')

    def test_tenant_admin_cannot_choose_other_organization(self):
        """Even if Admin A explicitly supplies organization=org_b, employee is bound to org_a."""
        self.client.force_authenticate(user=self.admin_a)
        resp = self.client.post('/api/v1/employees/', {
            'email': 'spoofed_org@alpha.local',
            'first_name': 'Spoof',
            'last_name': 'Attempt',
            'organization': self.org_b.id,
            'personal_email': 'spoof@test.local'
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        new_emp = Employee.objects.get(id=resp.data['employee']['id'])
        self.assertEqual(new_emp.organization, self.org_a)
        self.assertNotEqual(new_emp.organization, self.org_b)

    def test_superuser_organization_selection_is_authorized(self):
        """Superuser can explicitly select the organization when provisioning."""
        superuser = User.objects.create_superuser(
            email='root@system.local', password='Password123!', status='active'
        )
        self.client.force_authenticate(user=superuser)

        resp = self.client.post('/api/v1/employees/', {
            'email': 'super_recruit@beta.local',
            'first_name': 'Super',
            'last_name': 'Recruit',
            'organization': self.org_b.id,
            'personal_email': 'super_recruit@test.local'
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        new_emp = Employee.objects.get(id=resp.data['employee']['id'])
        self.assertEqual(new_emp.organization, self.org_b)

    def test_orphan_employee_creation_blocked_without_organization(self):
        """ProvisionEmployeeSerializer rejects creation if organization cannot be resolved."""
        from apps.employees.serializers import ProvisionEmployeeSerializer
        # User without an employee/organization profile
        unscoped_user = User.objects.create_user(email='unscoped@system.local', password='Password123!', status='active')

        class MockRequest:
            user = unscoped_user

        serializer = ProvisionEmployeeSerializer(
            data={
                'email': 'orphan@system.local',
                'first_name': 'Orphan',
                'last_name': 'Candidate',
            },
            context={'request': MockRequest()}
        )
        self.assertTrue(serializer.is_valid())
        with self.assertRaises(Exception):
            serializer.save()

