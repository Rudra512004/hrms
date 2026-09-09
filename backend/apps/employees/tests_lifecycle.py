from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from unittest.mock import patch

from apps.authorization.models import Permission, Role, UserRole, RolePermission
from apps.organization.models import Organization, Department, Designation, Branch
from apps.employees.models import Employee, EmploymentStatus, EmployeeLifecycleEvent
from apps.attendance.models import Attendance
from apps.leaves.models import LeaveType, LeaveRequest
from apps.payroll.models import CompensationHistory, PayrollPeriod, PayrollRecord, Payslip
from apps.payroll.services import generate_payroll_for_period, issue_payslips_for_period
from apps.audit.models import AuditLog

User = get_user_model()


@patch('apps.authorization.permissions.IsNetworkAllowed.has_permission', return_value=True)
class EmployeeLifecycleComprehensiveTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org = Organization.objects.create(name='Acme Corp')
        self.other_org = Organization.objects.create(name='Other Corp')

        self.branch1 = Branch.objects.create(organization=self.org, name='HQ')
        self.branch2 = Branch.objects.create(organization=self.org, name='Tech Hub')
        self.other_branch = Branch.objects.create(organization=self.other_org, name='External Branch')

        self.dept1 = Department.objects.create(organization=self.org, name='Engineering')
        self.dept2 = Department.objects.create(organization=self.org, name='Product')
        self.other_dept = Department.objects.create(organization=self.other_org, name='Legal')

        self.desig1 = Designation.objects.create(organization=self.org, name='Software Engineer')
        self.desig2 = Designation.objects.create(organization=self.org, name='Senior Software Engineer')
        self.other_desig = Designation.objects.create(organization=self.other_org, name='VP')

        self.admin_user = User.objects.create_user(email='admin@acme.com', password='password123', status='active')
        self.admin_emp = Employee.objects.create(user=self.admin_user, employee_code='ADM001', organization=self.org)

        self.emp_user = User.objects.create_user(email='emp@acme.com', password='password123', status='active')
        self.employee = Employee.objects.create(
            user=self.emp_user,
            employee_code='EMPBS101',
            organization=self.org,
            branch=self.branch1,
            department=self.dept1,
            designation=self.desig1,
            employment_status=EmploymentStatus.ACTIVE,
            joining_date=date(2026, 1, 1),
            personal_email='emp.personal@gmail.com',
            phone_number='9876543210'
        )

        self.hr_role = Role.objects.create(name='HRRole', organization=self.org)
        UserRole.objects.create(user=self.admin_user, role=self.hr_role)

        for codename in [
            'employee.view', 'employee.update', 'employee.manage_status',
            'employee.transfer', 'employee.promote', 'employee.exit', 'employee.lifecycle.view',
            'employee.view_sensitive', 'leave.request', 'leave.approve', 'payroll.view', 'payroll.view_sensitive'
        ]:
            perm, _ = Permission.objects.get_or_create(
                codename=codename,
                defaults={'name': codename, 'resource': 'employee', 'action': codename.split('.')[1]}
            )
            RolePermission.objects.create(role=self.hr_role, permission=perm)

        self.emp_role = Role.objects.create(name='EmpRole', organization=self.org)
        UserRole.objects.create(user=self.emp_user, role=self.emp_role)
        leave_perm = Permission.objects.get(codename='leave.request')
        RolePermission.objects.create(role=self.emp_role, permission=leave_perm)

    # 1. Employee starts ACTIVE
    def test_employee_starts_active(self, mock_net):
        self.assertEqual(self.employee.employment_status, EmploymentStatus.ACTIVE)

    # 2. ACTIVE -> ON_NOTICE succeeds
    def test_active_to_on_notice_succeeds(self, mock_net):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(reverse('employee-management-exit', args=[self.employee.id]), {
            'exit_type': 'resignation',
            'exit_date': '2026-12-31',
            'exit_reason': 'Better opportunity',
            'resignation_date': '2026-11-01',
            'notice_period_start': '2026-11-01',
            'notice_period_end': '2026-12-31',
            'set_notice_status': True
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.employment_status, EmploymentStatus.ON_NOTICE)
        self.assertEqual(str(self.employee.exit_date), '2026-12-31')
        self.assertEqual(str(self.employee.resignation_date), '2026-11-01')
        self.assertEqual(self.employee.exit_reason, 'Better opportunity')

        # Verify lifecycle event
        event = EmployeeLifecycleEvent.objects.filter(employee=self.employee, event_type='resignation').first()
        self.assertIsNotNone(event)
        self.assertEqual(event.to_status, EmploymentStatus.ON_NOTICE)

    # 3. ON_NOTICE -> EXITED succeeds
    def test_on_notice_to_exited_succeeds(self, mock_net):
        self.employee.employment_status = EmploymentStatus.ON_NOTICE
        self.employee.save()

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(reverse('employee-management-exit', args=[self.employee.id]), {
            'exit_type': 'resignation',
            'exit_date': '2026-12-31',
            'exit_reason': 'Notice period completed',
            'set_notice_status': False
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.employment_status, EmploymentStatus.EXITED)
        self.assertEqual(self.employee.user.status, 'inactive')
        self.assertFalse(self.employee.user.is_active)

    # 4. Invalid lifecycle transition is rejected
    def test_invalid_lifecycle_transition_is_rejected(self, mock_net):
        self.client.force_authenticate(user=self.admin_user)
        # Invalid status choice
        response = self.client.post(reverse('employee-management-change-employment-status', args=[self.employee.id]), {
            'employment_status': 'super_active'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Transition EXITED -> ACTIVE via change_employment_status rejected
        self.employee.employment_status = EmploymentStatus.EXITED
        self.employee.save()
        response = self.client.post(reverse('employee-management-change-employment-status', args=[self.employee.id]), {
            'employment_status': 'active'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Exited employee cannot be transitioned', response.data['detail'])

    # 5. EXITED employee cannot be accidentally edited into active employee through normal update
    def test_exited_employee_cannot_be_edited_to_active_via_normal_patch(self, mock_net):
        self.employee.employment_status = EmploymentStatus.EXITED
        self.employee.save()

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.patch(reverse('employee-management-detail', args=[self.employee.id]), {
            'employment_status': 'active',
            'phone_number': '1112223333'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.employee.refresh_from_db()
        # employment_status must remain EXITED (it is read-only)
        self.assertEqual(self.employee.employment_status, EmploymentStatus.EXITED)
        self.assertEqual(self.employee.phone_number, '1112223333')

    # 6. Transfer preserves employee identity
    def test_transfer_preserves_employee_identity(self, mock_net):
        initial_id = self.employee.id
        initial_code = self.employee.employee_code

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(reverse('employee-management-transfer', args=[self.employee.id]), {
            'department': self.dept2.id,
            'branch': self.branch2.id,
            'effective_date': '2026-06-01',
            'reason': 'Relocation to Tech Hub'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.id, initial_id)
        self.assertEqual(self.employee.employee_code, initial_code)
        self.assertEqual(self.employee.department, self.dept2)
        self.assertEqual(self.employee.branch, self.branch2)

    # 7. Transfer preserves historical attendance
    def test_transfer_preserves_historical_attendance(self, mock_net):
        att = Attendance.objects.create(employee=self.employee, date=date(2026, 5, 15), status='present')

        self.client.force_authenticate(user=self.admin_user)
        self.client.post(reverse('employee-management-transfer', args=[self.employee.id]), {
            'department': self.dept2.id,
            'effective_date': '2026-06-01'
        })

        att.refresh_from_db()
        self.assertEqual(att.employee_id, self.employee.id)
        self.assertEqual(Attendance.objects.filter(employee=self.employee).count(), 1)

    # 8. Transfer preserves leave
    def test_transfer_preserves_leave(self, mock_net):
        lt = LeaveType.objects.create(organization=self.org, name='Vacation', annual_allocation=20)
        lr = LeaveRequest.objects.create(
            employee=self.employee, leave_type=lt, start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 2), status='approved', reason='Trip'
        )

        self.client.force_authenticate(user=self.admin_user)
        self.client.post(reverse('employee-management-transfer', args=[self.employee.id]), {
            'branch': self.branch2.id,
            'effective_date': '2026-06-01'
        })

        lr.refresh_from_db()
        self.assertEqual(lr.employee_id, self.employee.id)
        self.assertEqual(LeaveRequest.objects.filter(employee=self.employee).count(), 1)

    # 9. Transfer preserves payroll
    def test_transfer_preserves_payroll(self, mock_net):
        period = PayrollPeriod.objects.create(
            organization=self.org, year=2026, month=5,
            start_date=date(2026, 5, 1), end_date=date(2026, 5, 31),
            status=PayrollPeriod.STATUS_APPROVED
        )
        prec = PayrollRecord.objects.create(
            period=period, employee=self.employee, working_days=20,
            present_days=20, half_days=0, absent_days=0, leave_days=0,
            effective_days=Decimal('20.00'), basic_salary=Decimal('50000.00'),
            gross_salary=Decimal('50000.00'), net_salary=Decimal('50000.00'),
            status=PayrollRecord.STATUS_APPROVED
        )

        self.client.force_authenticate(user=self.admin_user)
        self.client.post(reverse('employee-management-transfer', args=[self.employee.id]), {
            'department': self.dept2.id,
            'effective_date': '2026-06-01'
        })

        prec.refresh_from_db()
        self.assertEqual(prec.employee_id, self.employee.id)
        self.assertEqual(prec.gross_salary, Decimal('50000.00'))

    # 10. Promotion preserves employee identity
    def test_promotion_preserves_employee_identity(self, mock_net):
        initial_id = self.employee.id
        initial_code = self.employee.employee_code

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(reverse('employee-management-promote', args=[self.employee.id]), {
            'designation': self.desig2.id,
            'effective_date': '2026-07-01',
            'reason': 'Merit promotion'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.id, initial_id)
        self.assertEqual(self.employee.employee_code, initial_code)
        self.assertEqual(self.employee.designation, self.desig2)

    # 11. Compensation history remains correct after promotion/salary change
    def test_compensation_history_correct_after_promotion(self, mock_net):
        c1 = CompensationHistory.objects.create(
            employee=self.employee, effective_from=date(2026, 1, 1), basic_salary=Decimal('50000.00')
        )

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(reverse('employee-management-promote', args=[self.employee.id]), {
            'designation': self.desig2.id,
            'effective_date': '2026-07-01',
            'new_basic_salary': '75000.00',
            'reason': 'Promotion with salary raise'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        c1.refresh_from_db()
        self.assertEqual(c1.effective_to, date(2026, 7, 1))

        new_comp = CompensationHistory.objects.filter(employee=self.employee, effective_to__isnull=True).first()
        self.assertIsNotNone(new_comp)
        self.assertEqual(new_comp.effective_from, date(2026, 7, 1))
        self.assertEqual(new_comp.basic_salary, Decimal('75000.00'))

    # 12. EXITED employee is excluded from future payroll generation
    def test_exited_employee_excluded_from_future_payroll(self, mock_net):
        CompensationHistory.objects.create(
            employee=self.employee, effective_from=date(2026, 1, 1), basic_salary=Decimal('60000.00')
        )
        self.employee.employment_status = EmploymentStatus.EXITED
        self.employee.exit_date = date(2026, 7, 31)
        self.employee.save()

        period = PayrollPeriod.objects.create(
            organization=self.org, year=2026, month=8,
            start_date=date(2026, 8, 1), end_date=date(2026, 8, 31),
            status=PayrollPeriod.STATUS_DRAFT
        )

        records = generate_payroll_for_period(period)
        emp_ids = [r.employee_id for r in records]
        self.assertNotIn(self.employee.id, emp_ids)
        self.assertFalse(PayrollRecord.objects.filter(period=period, employee=self.employee).exists())

    # 13. Existing historical payroll remains accessible for exited employee
    def test_existing_historical_payroll_remains_accessible(self, mock_net):
        period = PayrollPeriod.objects.create(
            organization=self.org, year=2026, month=6,
            start_date=date(2026, 6, 1), end_date=date(2026, 6, 30),
            status=PayrollPeriod.STATUS_APPROVED
        )
        PayrollRecord.objects.create(
            period=period, employee=self.employee, working_days=22,
            present_days=22, half_days=0, absent_days=0, leave_days=0,
            effective_days=Decimal('22.00'), basic_salary=Decimal('50000.00'),
            gross_salary=Decimal('50000.00'), net_salary=Decimal('50000.00'),
            status=PayrollRecord.STATUS_APPROVED
        )

        # Mark employee as exited
        self.employee.employment_status = EmploymentStatus.EXITED
        self.employee.exit_date = date(2026, 7, 1)
        self.employee.save()

        # Query payroll records for this employee
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(reverse('payroll-record-list') + f'?employee={self.employee.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['employee_code'], 'EMPBS101')

    # 14. Existing payslips remain accessible for exited employee
    def test_existing_payslips_remain_accessible(self, mock_net):
        period = PayrollPeriod.objects.create(
            organization=self.org, year=2026, month=6,
            start_date=date(2026, 6, 1), end_date=date(2026, 6, 30),
            status=PayrollPeriod.STATUS_APPROVED
        )
        prec = PayrollRecord.objects.create(
            period=period, employee=self.employee, working_days=22,
            present_days=22, half_days=0, absent_days=0, leave_days=0,
            effective_days=Decimal('22.00'), basic_salary=Decimal('50000.00'),
            gross_salary=Decimal('50000.00'), net_salary=Decimal('50000.00'),
            status=PayrollRecord.STATUS_APPROVED
        )
        payslips = issue_payslips_for_period(period)
        self.assertEqual(len(payslips), 1)

        # Mark employee as exited
        self.employee.employment_status = EmploymentStatus.EXITED
        self.employee.save()

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(reverse('payslip-list') + f'?employee={self.employee.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertIn('EMPBS101', response.data[0]['payslip_number'])

    # 15. EXITED employee cannot create future attendance
    def test_exited_employee_cannot_create_future_attendance(self, mock_net):
        self.employee.employment_status = EmploymentStatus.EXITED
        self.employee.save()

        self.client.force_authenticate(user=self.emp_user)
        response = self.client.post(reverse('attendance-check-in'), {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Exited employees cannot record attendance', response.data['detail'])

    # 16. EXITED employee cannot create inappropriate future leave
    def test_exited_employee_cannot_create_future_leave(self, mock_net):
        lt = LeaveType.objects.create(organization=self.org, name='Annual', annual_allocation=20)
        self.employee.employment_status = EmploymentStatus.EXITED
        self.employee.save()

        self.client.force_authenticate(user=self.emp_user)
        response = self.client.post(reverse('leave-requests-list'), {
            'leave_type': lt.id,
            'start_date': '2026-09-01',
            'end_date': '2026-09-02',
            'reason': 'Future vacation'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Exited employees cannot request leave', str(response.data))

    # 17. Organization isolation remains enforced on transfer & promotion
    def test_organization_isolation_enforced_on_transfer_and_promotion(self, mock_net):
        self.client.force_authenticate(user=self.admin_user)

        # Cross-org department transfer
        res_trans = self.client.post(reverse('employee-management-transfer', args=[self.employee.id]), {
            'department': self.other_dept.id,
            'effective_date': '2026-06-01'
        })
        self.assertEqual(res_trans.status_code, status.HTTP_400_BAD_REQUEST)

        # Cross-org branch transfer
        res_branch = self.client.post(reverse('employee-management-transfer', args=[self.employee.id]), {
            'branch': self.other_branch.id,
            'effective_date': '2026-06-01'
        })
        self.assertEqual(res_branch.status_code, status.HTTP_400_BAD_REQUEST)

        # Cross-org designation promotion
        res_promo = self.client.post(reverse('employee-management-promote', args=[self.employee.id]), {
            'designation': self.other_desig.id,
            'effective_date': '2026-06-01'
        })
        self.assertEqual(res_promo.status_code, status.HTTP_400_BAD_REQUEST)

    # 18. IDOR protection remains enforced
    def test_idor_protection_enforced(self, mock_net):
        other_user = User.objects.create_user(email='other_admin@other.com', password='password123', status='active')
        Employee.objects.create(user=other_user, employee_code='EXT001', organization=self.other_org)
        other_role = Role.objects.create(name='OtherHR', organization=self.other_org)
        UserRole.objects.create(user=other_user, role=other_role)
        perm = Permission.objects.get(codename='employee.transfer')
        RolePermission.objects.create(role=other_role, permission=perm)

        # Other org admin tries to transfer employee in self.org
        self.client.force_authenticate(user=other_user)
        response = self.client.post(reverse('employee-management-transfer', args=[self.employee.id]), {
            'department': self.other_dept.id,
            'effective_date': '2026-06-01'
        })
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # 19. RBAC permissions are enforced
    def test_rbac_permissions_enforced(self, mock_net):
        RolePermission.objects.filter(role=self.hr_role).delete()
        self.client.force_authenticate(user=self.admin_user)

        res_trans = self.client.post(reverse('employee-management-transfer', args=[self.employee.id]), {
            'department': self.dept2.id,
            'effective_date': '2026-06-01'
        })
        self.assertEqual(res_trans.status_code, status.HTTP_403_FORBIDDEN)

        res_promo = self.client.post(reverse('employee-management-promote', args=[self.employee.id]), {
            'designation': self.desig2.id,
            'effective_date': '2026-06-01'
        })
        self.assertEqual(res_promo.status_code, status.HTTP_403_FORBIDDEN)

        res_exit = self.client.post(reverse('employee-management-exit', args=[self.employee.id]), {
            'exit_date': '2026-12-31'
        })
        self.assertEqual(res_exit.status_code, status.HTTP_403_FORBIDDEN)

    # 20. Audit logs are generated for lifecycle operations
    def test_audit_logs_generated_for_lifecycle_operations(self, mock_net):
        self.client.force_authenticate(user=self.admin_user)

        self.client.post(reverse('employee-management-transfer', args=[self.employee.id]), {
            'department': self.dept2.id,
            'effective_date': '2026-06-01'
        })
        self.assertTrue(AuditLog.objects.filter(action='employee_transferred', target_id=str(self.employee.id)).exists())

        self.client.post(reverse('employee-management-promote', args=[self.employee.id]), {
            'designation': self.desig2.id,
            'effective_date': '2026-06-01'
        })
        self.assertTrue(AuditLog.objects.filter(action='employee_promoted', target_id=str(self.employee.id)).exists())

        self.client.post(reverse('employee-management-exit', args=[self.employee.id]), {
            'exit_date': '2026-12-31',
            'exit_reason': 'Resigned'
        })
        self.assertTrue(AuditLog.objects.filter(action='employee_exited', target_id=str(self.employee.id)).exists())
