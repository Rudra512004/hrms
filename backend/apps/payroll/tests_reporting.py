from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from django.utils import timezone
from unittest.mock import patch

from apps.employees.models import Employee, EmploymentStatus
from apps.organization.models import Organization, Branch, Department
from apps.attendance.models import Attendance
from apps.leaves.models import LeaveType, LeaveRequest
from apps.payroll.models import PayrollPeriod, PayrollRecord, CompensationHistory
from apps.payroll.services import generate_payroll_for_period

User = get_user_model()


class PayrollReportingTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org1 = Organization.objects.create(name='Acme Corp')
        self.org2 = Organization.objects.create(name='Beta Ltd')

        # Branches & Departments in Org 1
        self.branch1 = Branch.objects.create(organization=self.org1, name='HQ Branch', radius=100)
        self.branch2 = Branch.objects.create(organization=self.org1, name='East Branch', radius=100)
        self.dept1 = Department.objects.create(organization=self.org1, name='Engineering')
        self.dept2 = Department.objects.create(organization=self.org1, name='Marketing')

        # Branch in Org 2
        self.branch_org2 = Branch.objects.create(organization=self.org2, name='Other Branch', radius=100)
        self.dept_org2 = Department.objects.create(organization=self.org2, name='Other Dept')


        # Employee 1 in Org 1 (Engineering, HQ)
        self.u1 = User.objects.create_user(email='e1@acme.com', password='Pass123!', first_name='Alice', last_name='Smith', status='active')
        self.emp1 = Employee.objects.create(
            user=self.u1, employee_code='E01', organization=self.org1,
            branch=self.branch1, department=self.dept1, employment_status=EmploymentStatus.ACTIVE
        )
        CompensationHistory.objects.create(employee=self.emp1, effective_from=date(2025, 1, 1), basic_salary=Decimal('50000.00'))

        # Employee 2 in Org 1 (Marketing, East)
        self.u2 = User.objects.create_user(email='e2@acme.com', password='Pass123!', first_name='Bob', last_name='Jones', status='active')
        self.emp2 = Employee.objects.create(
            user=self.u2, employee_code='E02', organization=self.org1,
            branch=self.branch2, department=self.dept2, employment_status=EmploymentStatus.ACTIVE
        )
        CompensationHistory.objects.create(employee=self.emp2, effective_from=date(2025, 1, 1), basic_salary=Decimal('40000.00'))

        # Employee in Org 2
        self.u_org2 = User.objects.create_user(email='e3@beta.com', password='Pass123!', first_name='Charlie', last_name='Brown', status='active')
        self.emp_org2 = Employee.objects.create(
            user=self.u_org2, employee_code='E03', organization=self.org2,
            branch=self.branch_org2, department=self.dept_org2, employment_status=EmploymentStatus.ACTIVE
        )
        CompensationHistory.objects.create(employee=self.emp_org2, effective_from=date(2025, 1, 1), basic_salary=Decimal('45000.00'))

        # Period in Org 1
        self.period1 = PayrollPeriod.objects.create(
            organization=self.org1, year=2025, month=1,
            start_date=date(2025, 1, 1), end_date=date(2025, 1, 31),
        )
        generate_payroll_for_period(self.period1)

        # Period in Org 2
        self.period_org2 = PayrollPeriod.objects.create(
            organization=self.org2, year=2025, month=1,
            start_date=date(2025, 1, 1), end_date=date(2025, 1, 31),
        )
        generate_payroll_for_period(self.period_org2)

    def _auth_user1(self, permissions=None):
        self.client.force_authenticate(user=self.u1)
        perms = set(permissions or ['payroll.view_reports', 'payroll.view_sensitive'])
        return patch('apps.authorization.services.AuthorizationService.has_permission', side_effect=lambda u, p: p in perms)

    def test_unauthenticated_requests_return_401(self):
        resp = self.client.get(f'/api/v1/payroll/reports/period-summary/?period={self.period1.id}')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_employees_without_payroll_view_reports_cannot_access_reports(self):
        self.client.force_authenticate(user=self.u1)
        with patch('apps.authorization.services.AuthorizationService.has_permission', return_value=False):
            resp = self.client.get(f'/api/v1/payroll/reports/period-summary/?period={self.period1.id}')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_period_summary_aggregation_correctness(self):
        with self._auth_user1():
            resp = self.client.get(f'/api/v1/payroll/reports/period-summary/?period={self.period1.id}')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        sum_data = resp.data['summary']
        self.assertEqual(sum_data['total_employees'], 2)
        # Total basic = 50000 + 40000 = 90000.00
        self.assertEqual(Decimal(sum_data['total_basic_salary']), Decimal('90000.00'))
        self.assertEqual(Decimal(sum_data['total_gross_salary']), Decimal('0.00'))  # no attendance logged yet
        self.assertEqual(sum_data['scheduled_working_days'], 23)

    def test_reconciliation_output_correctness(self):
        with self._auth_user1():
            resp = self.client.get(f'/api/v1/payroll/reports/reconciliation/?period={self.period1.id}')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 2)
        codes = [r['employee_code'] for r in resp.data['records']]
        self.assertIn('E01', codes)
        self.assertIn('E02', codes)

        # Check search filtering
        with self._auth_user1():
            resp_search = self.client.get(f'/api/v1/payroll/reports/reconciliation/?period={self.period1.id}&search=Alice')
        self.assertEqual(resp_search.status_code, status.HTTP_200_OK)
        self.assertEqual(resp_search.data['count'], 1)
        self.assertEqual(resp_search.data['records'][0]['employee_code'], 'E01')

    def test_branch_department_aggregation(self):
        with self._auth_user1():
            resp = self.client.get(f'/api/v1/payroll/reports/organization-breakdown/?period={self.period1.id}')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        branches = resp.data['by_branch']
        departments = resp.data['by_department']

        branch_names = [b['branch_name'] for b in branches]
        self.assertIn('HQ Branch', branch_names)
        self.assertIn('East Branch', branch_names)

        dept_names = [d['department_name'] for d in departments]
        self.assertIn('Engineering', dept_names)
        self.assertIn('Marketing', dept_names)

    def test_organization_isolation(self):
        # User in Org 1 queries breakdown without period ID (defaults to org1 latest)
        with self._auth_user1():
            resp = self.client.get('/api/v1/payroll/reports/organization-breakdown/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        branch_names = [b['branch_name'] for b in resp.data['by_branch']]
        self.assertNotIn('Other Branch', branch_names)

    def test_cross_org_period_id_rejection(self):
        # User in Org 1 passes period belonging to Org 2 -> 404
        with self._auth_user1():
            resp = self.client.get(f'/api/v1/payroll/reports/period-summary/?period={self.period_org2.id}')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_cross_org_branch_filter_rejection(self):
        # User in Org 1 passes branch belonging to Org 2 -> 404
        with self._auth_user1():
            resp = self.client.get(f'/api/v1/payroll/reports/reconciliation/?period={self.period1.id}&branch={self.branch_org2.id}')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_cross_org_department_filter_rejection(self):
        # User in Org 1 passes department belonging to Org 2 -> 404
        with self._auth_user1():
            resp = self.client.get(f'/api/v1/payroll/reports/reconciliation/?period={self.period1.id}&department={self.dept_org2.id}')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_salary_masking_without_payroll_view_sensitive(self):
        # User has payroll.view_reports but NOT payroll.view_sensitive
        with self._auth_user1(permissions=['payroll.view_reports']):
            resp_summary = self.client.get(f'/api/v1/payroll/reports/period-summary/?period={self.period1.id}')
            resp_recon = self.client.get(f'/api/v1/payroll/reports/reconciliation/?period={self.period1.id}')
            resp_breakdown = self.client.get(f'/api/v1/payroll/reports/organization-breakdown/?period={self.period1.id}')

        self.assertEqual(resp_summary.status_code, status.HTTP_200_OK)
        self.assertIsNone(resp_summary.data['summary']['total_net_salary'])
        self.assertIsNone(resp_summary.data['summary']['total_basic_salary'])

        self.assertEqual(resp_recon.status_code, status.HTTP_200_OK)
        for rec in resp_recon.data['records']:
            self.assertIsNone(rec['basic_salary'])
            self.assertIsNone(rec['net_salary'])

        self.assertEqual(resp_breakdown.status_code, status.HTTP_200_OK)
        for b in resp_breakdown.data['by_branch']:
            self.assertIsNone(b['total_net_salary'])

    def test_salary_visibility_with_payroll_view_sensitive(self):
        with self._auth_user1(permissions=['payroll.view_reports', 'payroll.view_sensitive']):
            resp_summary = self.client.get(f'/api/v1/payroll/reports/period-summary/?period={self.period1.id}')
        self.assertEqual(resp_summary.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(resp_summary.data['summary']['total_net_salary'])
        self.assertIsNotNone(resp_summary.data['summary']['total_basic_salary'])

    def test_missing_compensation_detection(self):
        # Create active employee without compensation
        u_no_comp = User.objects.create_user(email='nocomp@acme.com', password='Pass123!', status='active')
        emp_no_comp = Employee.objects.create(
            user=u_no_comp, employee_code='E_NC', organization=self.org1, employment_status=EmploymentStatus.ACTIVE
        )

        with self._auth_user1():
            resp = self.client.get(f'/api/v1/payroll/reports/exceptions/?period={self.period1.id}')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        types = [e['type'] for e in resp.data['exceptions']]
        self.assertIn('MISSING_COMPENSATION', types)

    def test_missing_record_detection(self):
        # Create active employee who was NOT part of period1 (joined after generation)
        u_new = User.objects.create_user(email='new@acme.com', password='Pass123!', status='active')
        emp_new = Employee.objects.create(
            user=u_new, employee_code='E_NEW', organization=self.org1, employment_status=EmploymentStatus.ACTIVE
        )
        CompensationHistory.objects.create(employee=emp_new, effective_from=date(2025, 1, 1), basic_salary=Decimal('50000.00'))

        with self._auth_user1():
            resp = self.client.get(f'/api/v1/payroll/reports/exceptions/?period={self.period1.id}')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        missing = [e for e in resp.data['exceptions'] if e['type'] == 'MISSING_RECORD']
        self.assertTrue(len(missing) > 0)
        self.assertIn('E_NEW', [e['employee_code'] for e in missing])

    def test_full_absence_detection(self):
        # Since records have no attendance logged, effective_days == 0 -> FULL_ABSENCE
        with self._auth_user1():
            resp = self.client.get(f'/api/v1/payroll/reports/exceptions/?period={self.period1.id}')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        absent_ex = [e for e in resp.data['exceptions'] if e['type'] == 'FULL_ABSENCE']
        self.assertTrue(len(absent_ex) > 0)

    def test_pending_leave_detection(self):
        lt = LeaveType.objects.create(organization=self.org1, name='Casual', annual_allocation=12)
        LeaveRequest.objects.create(
            employee=self.emp1, leave_type=lt,
            start_date=date(2025, 1, 10), end_date=date(2025, 1, 12),
            status='pending', reason='Vacation'
        )

        with self._auth_user1():
            resp = self.client.get(f'/api/v1/payroll/reports/exceptions/?period={self.period1.id}')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        leave_ex = [e for e in resp.data['exceptions'] if e['type'] == 'PENDING_LEAVE']
        self.assertTrue(len(leave_ex) > 0)
        self.assertEqual(leave_ex[0]['employee_code'], 'E01')

    def test_attendance_incomplete_detection(self):
        # Check-in without check-out inside the period
        Attendance.objects.create(
            employee=self.emp1,
            date=date(2025, 1, 15),
            check_in=timezone.now(),
            check_out=None,
            status='present'
        )
        with self._auth_user1():
            resp = self.client.get(f'/api/v1/payroll/reports/exceptions/?period={self.period1.id}')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        att_ex = [e for e in resp.data['exceptions'] if e['type'] == 'ATTENDANCE_INCOMPLETE']
        self.assertTrue(len(att_ex) > 0)
        self.assertEqual(att_ex[0]['employee_code'], 'E01')

    def test_large_query_does_not_n_plus_one(self):
        # Verify reconciliation uses select_related by measuring query count
        with self._auth_user1():
            with self.assertNumQueries(2):  # 1 period lookup, 1 records with select_related
                resp = self.client.get(f'/api/v1/payroll/reports/reconciliation/?period={self.period1.id}')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

