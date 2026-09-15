from django.test import TransactionTestCase
from apps.payroll.models import PayrollPeriod, PayrollRecord, Payslip
from apps.organization.models import Organization
from apps.employees.models import Employee
from django.contrib.auth import get_user_model
from apps.notifications.models import Notification
from apps.payroll.services import issue_payslips_for_period
from django.utils import timezone
from datetime import date

User = get_user_model()

class PayrollNotificationIntegrationTests(TransactionTestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Payroll Org')
        self.user = User.objects.create_user(email='emp_pay@example.com', password='Password123!', status='active')
        self.employee = Employee.objects.create(user=self.user, employee_code='PAY01', organization=self.org)
        self.period = PayrollPeriod.objects.create(organization=self.org, year=2026, month=9, start_date=date(2026,9,1), end_date=date(2026,9,30), status=PayrollPeriod.STATUS_APPROVED)
        self.record = PayrollRecord.objects.create(
            period=self.period, employee=self.employee, status=PayrollRecord.STATUS_APPROVED,
            basic_salary=1000, gross_salary=1000, net_salary=1000, working_days=20, leave_days=0, present_days=20, absent_days=0, effective_days=20
        )

    def test_payslip_issued_notification(self):
        # Explicitly issue payslips
        payslips = issue_payslips_for_period(self.period)
        self.assertEqual(len(payslips), 1)

        # Check notification
        notifs = Notification.objects.filter(recipient=self.user)
        self.assertEqual(notifs.count(), 1)
        notif = notifs.first()
        self.assertEqual(notif.notification_type, 'PAYSLIP_ISSUED')
        self.assertEqual(notif.organization, self.org)
        self.assertEqual(notif.reference_id, str(payslips[0].id))
        self.assertIn(payslips[0].payslip_number, notif.message)
