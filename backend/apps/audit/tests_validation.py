"""
Comprehensive validation tests for onboarding notifications and audit logging.

Covers:
- personal_email persistence, duplicate rejection, invalid rejection
- onboarding response structure (no secret leak)
- onboarding email content contains activation link
- activation/login full flow
- deactivated account → 401
- audit log entries for all required actions
- audit API permission matrix (superadmin, audit.view user, normal, unauthenticated)
- audit records are read-only via API (no PUT/PATCH/DELETE)
"""
import re
import datetime
from django.test import TestCase
from django.core import mail
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.employees.models import Employee
from apps.audit.models import AuditLog
from apps.authorization.models import Permission, UserPermissionGrant, Role, UserRole
from apps.organization.models import Organization, OfficeNetwork
from apps.leaves.models import LeaveType, LeaveBalance

User = get_user_model()

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def make_org():
    org, _ = Organization.objects.get_or_create(name='TestOrg', defaults={})
    return org


def make_office_network(org):
    """Allow 127.0.0.0/8 so test client (127.0.0.1) passes IsNetworkAllowed."""
    net, _ = OfficeNetwork.objects.get_or_create(
        organization=org, name='Localhost',
        defaults={'network': '127.0.0.0/8', 'is_active': True}
    )
    return net


def make_permission(codename, resource='', action=''):
    if not resource and '.' in codename:
        resource, action = codename.split('.', 1)
    p, _ = Permission.objects.get_or_create(
        codename=codename,
        defaults={'name': codename, 'resource': resource, 'action': action}
    )
    return p


def grant(user, codename):
    p = make_permission(codename)
    UserPermissionGrant.objects.get_or_create(user=user, permission=p)


# --------------------------------------------------------------------------- #
# 1. Onboarding email & security
# --------------------------------------------------------------------------- #

class OnboardingEmailSecurityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        org = make_org()
        make_office_network(org)
        self.admin = User.objects.create_superuser(email='admin@co.com', password='Admin1234!')
        Employee.objects.create(user=self.admin, employee_code='ADM001', personal_email='admin.personal@ext.com')
        grant(self.admin, 'employee.create')

    def test_personal_email_persisted(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post('/api/v1/employees/management/', {
            'email': 'emp1@co.com',
            'personal_email': 'emp1.personal@gmail.com',
            'first_name': 'Emp', 'last_name': 'One', 'employee_code': 'EMP_V01'
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        emp = Employee.objects.get(employee_code='EMP_V01')
        self.assertEqual(emp.personal_email, 'emp1.personal@gmail.com')

    def test_duplicate_personal_email_rejected(self):
        self.client.force_authenticate(user=self.admin)
        self.client.post('/api/v1/employees/management/', {
            'email': 'emp2@co.com', 'personal_email': 'shared.personal@gmail.com',
            'first_name': 'Emp', 'last_name': 'Two', 'employee_code': 'EMP_V02'
        })
        resp = self.client.post('/api/v1/employees/management/', {
            'email': 'emp3@co.com', 'personal_email': 'shared.personal@gmail.com',
            'first_name': 'Emp', 'last_name': 'Three', 'employee_code': 'EMP_V03'
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('personal email', str(resp.data).lower())

    def test_invalid_email_rejected(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post('/api/v1/employees/management/', {
            'email': 'emp4@co.com', 'personal_email': 'not-an-email',
            'first_name': 'Emp', 'last_name': 'Four', 'employee_code': 'EMP_V04'
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_response_never_contains_secret(self):
        """Activation token/uid must NEVER appear in the API response body."""
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post('/api/v1/employees/management/', {
            'email': 'emp5@co.com', 'personal_email': 'emp5.personal@gmail.com',
            'first_name': 'Emp', 'last_name': 'Five', 'employee_code': 'EMP_V05'
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertNotIn('activation_info', resp.data)
        self.assertNotIn('token', resp.data)
        self.assertIn('onboarding_email_status', resp.data)

    def test_onboarding_email_contains_activation_link(self):
        """The email body must contain a URL with uid and token query params."""
        self.client.force_authenticate(user=self.admin)
        self.client.post('/api/v1/employees/management/', {
            'email': 'emp6@co.com', 'personal_email': 'emp6.personal@gmail.com',
            'first_name': 'Emp', 'last_name': 'Six', 'employee_code': 'EMP_V06'
        })
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertIn('uid=', body)
        self.assertIn('token=', body)
        self.assertIn('activate', body.lower())

    def test_token_not_in_audit_metadata(self):
        """AuditLog metadata must not contain token or password."""
        self.client.force_authenticate(user=self.admin)
        self.client.post('/api/v1/employees/management/', {
            'email': 'emp7@co.com', 'personal_email': 'emp7.personal@gmail.com',
            'first_name': 'Emp', 'last_name': 'Seven', 'employee_code': 'EMP_V07'
        })
        for log in AuditLog.objects.all():
            meta_str = str(log.metadata)
            self.assertNotIn('token', meta_str.lower())
            self.assertNotIn('password', meta_str.lower())


# --------------------------------------------------------------------------- #
# 2. Activation & Login flow
# --------------------------------------------------------------------------- #

class ActivationLoginFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        org = make_org()
        make_office_network(org)
        self.admin = User.objects.create_superuser(email='admin2@co.com', password='Admin1234!')
        Employee.objects.create(user=self.admin, employee_code='ADM002', personal_email='admin2.personal@ext.com')
        grant(self.admin, 'employee.create')

    def _provision_and_get_activation_params(self, email, personal_email, code):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post('/api/v1/employees/management/', {
            'email': email, 'personal_email': personal_email,
            'first_name': 'Test', 'last_name': 'User', 'employee_code': code
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        uid_match = re.search(r'uid=([^&\s]+)', body)
        token_match = re.search(r'token=([^&\s]+)', body)
        self.assertIsNotNone(uid_match, f"uid not found in email body:\n{body}")
        self.assertIsNotNone(token_match, f"token not found in email body:\n{body}")
        mail.outbox.clear()
        self.client.force_authenticate(user=None)
        return uid_match.group(1), token_match.group(1)

    def test_activation_and_login(self):
        uid, token = self._provision_and_get_activation_params(
            'newact@co.com', 'newact.personal@gmail.com', 'ACT001'
        )
        resp = self.client.post('/api/v1/auth/activate/', {
            'uid': uid, 'token': token, 'password': 'SecurePass1234!'
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)

        resp = self.client.post('/api/v1/auth/login/', {
            'email': 'newact@co.com', 'password': 'SecurePass1234!'
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertIn('token', resp.data)
        self.assertNotIn('password', str(resp.data))
        # audit log for activation
        self.assertTrue(AuditLog.objects.filter(action='account_activation').exists())

    def test_deactivated_account_returns_401(self):
        uid, token = self._provision_and_get_activation_params(
            'deact@co.com', 'deact.personal@gmail.com', 'DEACT001'
        )
        self.client.post('/api/v1/auth/activate/', {
            'uid': uid, 'token': token, 'password': 'SecurePass1234!'
        })
        resp = self.client.post('/api/v1/auth/login/', {
            'email': 'deact@co.com', 'password': 'SecurePass1234!'
        })
        auth_token = resp.data['token']

        user = User.objects.get(email='deact@co.com')
        user.status = 'inactive'
        user.save()

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {auth_token}')
        resp = self.client.get('/api/v1/employees/me/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        self.client.credentials()


# --------------------------------------------------------------------------- #
# 3. Audit coverage
# --------------------------------------------------------------------------- #

class AuditCoverageTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org = make_org()
        make_office_network(self.org)

        self.admin = User.objects.create_superuser(email='admin3@co.com', password='Admin3Pass!')
        Employee.objects.create(user=self.admin, employee_code='ADM003', personal_email='admin3.personal@ext.com')

        # Second user for WFH approve (can't approve own request)
        self.approver = User.objects.create_superuser(email='approver@co.com', password='Approver123!')
        Employee.objects.create(user=self.approver, employee_code='APR001', personal_email='approver.personal@ext.com')

        for codename in [
            'employee.create', 'employee.status',
            'role.assign', 'role.revoke', 'role.view',
            'permission.assign', 'permission.revoke', 'permission.view',
            'wfh.request', 'wfh.approve', 'wfh.reject', 'wfh.cancel', 'wfh.view',
            'leave.request', 'leave.approve', 'leave.reject', 'leave.cancel', 'leave.view',
            'audit.view',
        ]:
            grant(self.admin, codename)
            grant(self.approver, codename)

        self.client.force_authenticate(user=self.admin)

    def _provision(self, email, personal_email, code):
        resp = self.client.post('/api/v1/employees/management/', {
            'email': email, 'personal_email': personal_email,
            'first_name': 'Cov', 'last_name': 'Test', 'employee_code': code
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        mail.outbox.clear()
        return Employee.objects.get(employee_code=code)

    def test_employee_creation_audit(self):
        AuditLog.objects.all().delete()
        self._provision('cov1@co.com', 'cov1.personal@gmail.com', 'COV001')
        log = AuditLog.objects.filter(action='employee_created').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.actor, self.admin)
        self.assertEqual(log.target_type, 'employee')
        self.assertIsNotNone(log.timestamp)

    def test_employee_activate_deactivate_audit(self):
        emp = self._provision('cov2@co.com', 'cov2.personal@gmail.com', 'COV002')
        # provisioning sets status to 'invited' — activate
        AuditLog.objects.all().delete()
        resp = self.client.post(f'/api/v1/employees/management/{emp.id}/activate/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertTrue(AuditLog.objects.filter(action='employee_activated').exists())

        AuditLog.objects.all().delete()
        resp = self.client.post(f'/api/v1/employees/management/{emp.id}/deactivate/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertTrue(AuditLog.objects.filter(action='employee_deactivated').exists())

    def test_role_assign_revoke_audit(self):
        emp = self._provision('cov3@co.com', 'cov3.personal@gmail.com', 'COV003')
        role, _ = Role.objects.get_or_create(
            organization=self.org, name='TestRole', defaults={'description': ''}
        )

        AuditLog.objects.all().delete()
        resp = self.client.post('/api/v1/authorization/user-roles/', {
            'user': emp.user.id, 'role': role.id
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        log = AuditLog.objects.filter(action='role_assigned').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.metadata.get('role_name'), 'TestRole')
        self.assertNotIn('token', str(log.metadata))

        user_role_id = resp.data['id']
        AuditLog.objects.all().delete()
        resp = self.client.post(f'/api/v1/authorization/user-roles/{user_role_id}/revoke/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertTrue(AuditLog.objects.filter(action='role_revoked').exists())

    def test_permission_grant_revoke_audit(self):
        emp = self._provision('cov4@co.com', 'cov4.personal@gmail.com', 'COV004')
        perm = make_permission('test.permission')

        AuditLog.objects.all().delete()
        resp = self.client.post('/api/v1/authorization/user-permissions/', {
            'user': emp.user.id, 'permission': perm.id
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        log = AuditLog.objects.filter(action='permission_granted').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.metadata.get('codename'), 'test.permission')

        grant_id = resp.data['id']
        AuditLog.objects.all().delete()
        resp = self.client.post(f'/api/v1/authorization/user-permissions/{grant_id}/revoke/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertTrue(AuditLog.objects.filter(action='permission_revoked').exists())

    def test_wfh_lifecycle_audit(self):
        """WFH create/approve/reject/cancel all produce audit entries."""
        now = datetime.datetime.utcnow()

        def dt(delta_days, hour=9):
            d = now + datetime.timedelta(days=delta_days)
            return d.replace(hour=hour).strftime('%Y-%m-%dT%H:%M:%SZ')

        # --- create (admin creates their own WFH) ---
        AuditLog.objects.all().delete()
        resp = self.client.post('/api/v1/employees/wfh-requests/', {
            'start_at': dt(1, 9), 'end_at': dt(1, 17), 'reason': 'Test WFH'
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertTrue(AuditLog.objects.filter(action='wfh_request_created').exists())
        wfh_id = resp.data['id']

        # --- approve (done by the approver, not the owner) ---
        self.client.force_authenticate(user=self.approver)
        AuditLog.objects.all().delete()
        resp = self.client.post(f'/api/v1/employees/wfh-requests/{wfh_id}/approve/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertTrue(AuditLog.objects.filter(action='wfh_request_approved').exists())

        # --- back to admin for more creates ---
        self.client.force_authenticate(user=self.admin)

        # --- reject ---
        resp2 = self.client.post('/api/v1/employees/wfh-requests/', {
            'start_at': dt(2, 9), 'end_at': dt(2, 17), 'reason': 'WFH 2'
        })
        wfh2_id = resp2.data['id']
        self.client.force_authenticate(user=self.approver)
        AuditLog.objects.all().delete()
        resp = self.client.post(f'/api/v1/employees/wfh-requests/{wfh2_id}/reject/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertTrue(AuditLog.objects.filter(action='wfh_request_rejected').exists())

        # --- cancel (owner cancels their own pending request) ---
        self.client.force_authenticate(user=self.admin)
        resp3 = self.client.post('/api/v1/employees/wfh-requests/', {
            'start_at': dt(3, 9), 'end_at': dt(3, 17), 'reason': 'WFH 3'
        })
        wfh3_id = resp3.data['id']
        AuditLog.objects.all().delete()
        resp = self.client.post(f'/api/v1/employees/wfh-requests/{wfh3_id}/cancel/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertTrue(AuditLog.objects.filter(action='wfh_request_cancelled').exists())

    def test_attendance_checkin_checkout_audit(self):
        AuditLog.objects.all().delete()
        resp = self.client.post('/api/v1/attendance/check-in/')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertTrue(AuditLog.objects.filter(action='check-in').exists())

        AuditLog.objects.all().delete()
        resp = self.client.post('/api/v1/attendance/check-out/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertTrue(AuditLog.objects.filter(action='check-out').exists())

    def test_leave_lifecycle_audit(self):
        """Leave create/approve/reject/cancel all produce audit entries."""
        lt = LeaveType.objects.create(
            organization=self.org,
            name='Annual',
            annual_allocation=20,
            is_active=True
        )
        LeaveBalance.objects.create(
            employee=self.admin.employee, leave_type=lt, allocated=20, used=0
        )
        LeaveBalance.objects.create(
            employee=self.approver.employee, leave_type=lt, allocated=20, used=0
        )
        today = datetime.date.today()

        def ds(delta):
            return str(today + datetime.timedelta(days=delta))

        # --- create (as admin) ---
        self.client.force_authenticate(user=self.admin)
        AuditLog.objects.all().delete()
        resp = self.client.post('/api/v1/leaves/requests/', {
            'leave_type': lt.id, 'start_date': ds(5), 'end_date': ds(6), 'reason': 'Vacation'
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertTrue(AuditLog.objects.filter(action='leave_request_created').exists())
        lr_id = resp.data['id']

        # --- approve (by approver) ---
        self.client.force_authenticate(user=self.approver)
        AuditLog.objects.all().delete()
        resp = self.client.post(f'/api/v1/leaves/requests/{lr_id}/approve/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertTrue(AuditLog.objects.filter(action='leave_request_approved').exists())

        # --- reject ---
        self.client.force_authenticate(user=self.admin)
        resp2 = self.client.post('/api/v1/leaves/requests/', {
            'leave_type': lt.id, 'start_date': ds(10), 'end_date': ds(11), 'reason': 'More leave'
        })
        self.assertEqual(resp2.status_code, status.HTTP_201_CREATED, resp2.data)
        lr2_id = resp2.data['id']
        self.client.force_authenticate(user=self.approver)
        AuditLog.objects.all().delete()
        resp = self.client.post(f'/api/v1/leaves/requests/{lr2_id}/reject/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertTrue(AuditLog.objects.filter(action='leave_request_rejected').exists())

        # --- cancel (owner cancels their own pending request) ---
        self.client.force_authenticate(user=self.admin)
        resp3 = self.client.post('/api/v1/leaves/requests/', {
            'leave_type': lt.id, 'start_date': ds(15), 'end_date': ds(16), 'reason': 'Cancel this'
        })
        self.assertEqual(resp3.status_code, status.HTTP_201_CREATED, resp3.data)
        lr3_id = resp3.data['id']
        AuditLog.objects.all().delete()
        resp = self.client.post(f'/api/v1/leaves/requests/{lr3_id}/cancel/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertTrue(AuditLog.objects.filter(action='leave_request_cancelled').exists())


# --------------------------------------------------------------------------- #
# 4. Audit API permission matrix
class AuditAPIPermissionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        org = make_org()
        make_office_network(org)

        # Superadmin
        self.super_user = User.objects.create_superuser(email='super@co.com', password='Super1234!')
        Employee.objects.create(user=self.super_user, employee_code='SUPER01', personal_email='super.personal@ext.com')
        grant(self.super_user, 'audit.view')

        # Authorized user
        self.auth_user = User.objects.create_user(email='authuser@co.com', password='Auth1234!')
        Employee.objects.create(user=self.auth_user, employee_code='AUTH01', personal_email='authuser.personal@ext.com')
        self.auth_user.status = 'active'
        self.auth_user.save()
        grant(self.auth_user, 'audit.view')

        # Normal user — no audit.view
        self.normal_user = User.objects.create_user(email='normal@co.com', password='Normal1234!')
        Employee.objects.create(user=self.normal_user, employee_code='NORM01', personal_email='normal.personal@ext.com')
        self.normal_user.status = 'active'
        self.normal_user.save()

        AuditLog.objects.create(
            actor=self.super_user, action='test_action', target_type='user', target_id='1'
        )

    def test_superadmin_can_read_audit_logs(self):
        self.client.force_authenticate(user=self.super_user)
        resp = self.client.get('/api/v1/audit-logs/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(resp.data), 1)
        log = resp.data[0]
        self.assertIn('actor', log)
        self.assertIn('action', log)
        self.assertIn('timestamp', log)
        self.assertIn('target_type', log)
        self.assertIn('metadata', log)
        self.assertIn('actor_email', log)

    def test_authorized_user_can_read_audit_logs(self):
        self.client.force_authenticate(user=self.auth_user)
        resp = self.client.get('/api/v1/audit-logs/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_normal_user_gets_403(self):
        self.client.force_authenticate(user=self.normal_user)
        resp = self.client.get('/api/v1/audit-logs/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_gets_401(self):
        resp = self.client.get('/api/v1/audit-logs/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_audit_logs_are_read_only(self):
        """PUT, PATCH, DELETE must all be rejected (405 Method Not Allowed)."""
        self.client.force_authenticate(user=self.super_user)
        log = AuditLog.objects.first()
        url = f'/api/v1/audit-logs/{log.id}/'
        resp = self.client.put(url, {'action': 'tampered'})
        self.assertIn(resp.status_code, [status.HTTP_405_METHOD_NOT_ALLOWED, status.HTTP_403_FORBIDDEN])
        resp = self.client.patch(url, {'action': 'tampered'})
        self.assertIn(resp.status_code, [status.HTTP_405_METHOD_NOT_ALLOWED, status.HTTP_403_FORBIDDEN])
        resp = self.client.delete(url)
        self.assertIn(resp.status_code, [status.HTTP_405_METHOD_NOT_ALLOWED, status.HTTP_403_FORBIDDEN])

    def test_audit_log_query_filters(self):
        self.client.force_authenticate(user=self.super_user)
        resp = self.client.get('/api/v1/audit-logs/?action=test_action')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        for entry in resp.data:
            self.assertEqual(entry['action'], 'test_action')
