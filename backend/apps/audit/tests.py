from django.test import TestCase
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.employees.models import Employee
from apps.audit.models import AuditLog
from apps.authorization.models import Permission, UserPermissionGrant
from django.core import mail

User = get_user_model()

class OnboardingAuditTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.super_user = User.objects.create_superuser(email='super@company.com', password='password123!')
        self.super_employee = Employee.objects.create(user=self.super_user, employee_code='SUP001', personal_email='super.personal@test.com')
        
        self.normal_user = User.objects.create_user(email='normal@company.com', password='password123!')
        self.normal_employee = Employee.objects.create(user=self.normal_user, employee_code='NORM001', personal_email='normal.personal@test.com')
        self.normal_user.status = 'active'
        self.normal_user.save()

        p1, _ = Permission.objects.get_or_create(codename='employee.create', resource='employee', action='create', name='Create Employee')
        p2, _ = Permission.objects.get_or_create(codename='audit.view', resource='audit', action='view', name='View Audit')
        
        UserPermissionGrant.objects.create(user=self.super_user, permission=p1)
        UserPermissionGrant.objects.create(user=self.super_user, permission=p2)

    def test_onboarding_email_provisioning(self):
        self.client.force_authenticate(user=self.super_user)
        
        data = {
            'email': 'new@company.com',
            'personal_email': 'new.personal@gmail.com',
            'first_name': 'New',
            'last_name': 'User',
            'employee_code': 'NEW001'
        }
        response = self.client.post('/api/v1/employees/management/', data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['onboarding_email_status'], 'sent')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Welcome to HRMS', mail.outbox[0].subject)
        
        # Test audit log
        audit_log = AuditLog.objects.filter(action='employee_created').first()
        self.assertIsNotNone(audit_log)
        self.assertEqual(audit_log.actor, self.super_user)
        
        # Duplicate email
        response = self.client.post('/api/v1/employees/management/', data)
        self.assertEqual(response.status_code, 400)

    def test_audit_log_access(self):
        self.client.force_authenticate(user=self.normal_user)
        response = self.client.get('/api/v1/audit-logs/')
        self.assertEqual(response.status_code, 403)
        
        self.client.force_authenticate(user=self.super_user)
        response = self.client.get('/api/v1/audit-logs/')
        self.assertEqual(response.status_code, 200)
