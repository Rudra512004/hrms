from django.test import TestCase
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.organization.models import Organization, Branch, OfficeNetwork
from apps.employees.models import Employee, ApprovalDelegation, LetterRequest
from apps.authorization.models import Role, UserRole, Permission, RolePermission
import datetime

User = get_user_model()

class Phase7Tests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org = Organization.objects.create(name="Phase 7 Org")
        self.branch = Branch.objects.create(organization=self.org, name="Main Branch")
        OfficeNetwork.objects.create(branch=self.branch, name="Office", network="127.0.0.1/32", is_active=True)
        self.user = User.objects.create_user(email="emp@example.com", password="password", status='active')
        self.hr_user = User.objects.create_user(email="hr@example.com", password="password", status='active')
        self.emp = Employee.objects.create(user=self.user, organization=self.org, branch=self.branch, employee_code="E001")
        self.hr_emp = Employee.objects.create(user=self.hr_user, organization=self.org, branch=self.branch, employee_code="H001")
        
        hr_role = Role.objects.create(organization=self.org, name="HR", is_active=True)
        for codename in ['employee.manage', 'employee.view', 'organization.view']:
            p, _ = Permission.objects.get_or_create(codename=codename, defaults={'name': codename, 'resource': 'employee', 'action': codename, 'is_active': True})
            RolePermission.objects.create(role=hr_role, permission=p)
        UserRole.objects.create(user=self.hr_user, role=hr_role, scope='organization')
        
        emp_role = Role.objects.create(organization=self.org, name="EMP", is_active=True)
        UserRole.objects.create(user=self.user, role=emp_role, scope='organization')

    def test_org_chart(self):
        self.client.force_authenticate(user=self.hr_user)
        res = self.client.get(f'/api/v1/organization/organizations/{self.org.id}/org-chart/')
        self.assertEqual(res.status_code, 200)

    def test_approval_delegation(self):
        self.client.force_authenticate(user=self.user)
        res = self.client.post('/api/v1/employees/approval-delegations/', {
            'delegate': self.hr_user.id,
            'valid_from': datetime.date.today().isoformat(),
            'delegate_types': ['leave']
        }, format='json')
        self.assertEqual(res.status_code, 201)
        
    def test_letter_request(self):
        self.client.force_authenticate(user=self.user)
        res = self.client.post('/api/v1/employees/letter-requests/', {
            'employee': self.emp.id,
            'letter_type': 'BONAFIDE',
            'reason': 'Bank account'
        })
        self.assertEqual(res.status_code, 201)
        req_id = res.data['id']
        
        # HR approves
        self.client.force_authenticate(user=self.hr_user)
        res2 = self.client.patch(f'/api/v1/employees/letter-requests/{req_id}/', {'status': 'APPROVED'})
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.data['status'], 'ISSUED')

    def test_announcement_acknowledgement(self):
        from apps.notifications.models import Announcement
        ann = Announcement.objects.create(
            organization=self.org,
            title='Policy Update',
            body='Please read and acknowledge the updated handbook.',
            is_published=True,
            published_at=datetime.datetime.now(datetime.timezone.utc),
            requires_acknowledgement=True,
            created_by=self.hr_user
        )

        # Employee checks announcements
        self.client.force_authenticate(user=self.user)
        res = self.client.get('/api/v1/employees/me/announcements/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)
        self.assertFalse(res.data[0]['is_acknowledged'])

        # Employee acknowledges
        ack_res = self.client.post(f'/api/v1/announcements/{ann.id}/acknowledge/')
        self.assertEqual(ack_res.status_code, 200)
        self.assertTrue(ack_res.data['created'])

        # Duplicate acknowledgement returns created=False
        ack_res2 = self.client.post(f'/api/v1/announcements/{ann.id}/acknowledge/')
        self.assertEqual(ack_res2.status_code, 200)
        self.assertFalse(ack_res2.data['created'])

        # Check employee announcement status is now acknowledged
        res_after = self.client.get('/api/v1/employees/me/announcements/')
        self.assertTrue(res_after.data[0]['is_acknowledged'])

    def test_dashboard_celebrations(self):
        self.client.force_authenticate(user=self.user)
        res = self.client.get('/api/v1/dashboard/celebrations/')
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.data, list)

