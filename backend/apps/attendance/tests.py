from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.employees.models import Employee, WFHRequest
from apps.organization.models import Organization, OfficeNetwork
from .models import Attendance
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

class AttendanceAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email='emp@example.com', password='Password123!', status='active')
        self.employee = Employee.objects.create(user=self.user, employee_code='EMP01')
        self.org = Organization.objects.create(name='Test Org')
        self.network = OfficeNetwork.objects.create(organization=self.org, name='HQ', network='203.0.113.0/24')
        self.office_ip = '203.0.113.50'
        self.external_ip = '198.51.100.5'

        self.super_user = User.objects.create_user(email='super@example.com', password='Password123!', status='active', is_superuser=True)
        self.super_employee = Employee.objects.create(user=self.super_user, employee_code='EMP02')

    def test_office_ip_check_in(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.office_ip)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Attendance.objects.count(), 1)

    def test_external_ip_rejection(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.external_ip)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_active_wfh_check_in(self):
        now = timezone.now()
        WFHRequest.objects.create(employee=self.employee, start_at=now - timedelta(days=1), end_at=now + timedelta(days=1), status='approved')
        self.client.force_authenticate(user=self.user)
        response = self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.external_ip)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_future_wfh_rejection(self):
        now = timezone.now()
        WFHRequest.objects.create(employee=self.employee, start_at=now + timedelta(days=1), end_at=now + timedelta(days=2), status='approved')
        self.client.force_authenticate(user=self.user)
        response = self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.external_ip)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_expired_wfh_rejection(self):
        now = timezone.now()
        WFHRequest.objects.create(employee=self.employee, start_at=now - timedelta(days=2), end_at=now - timedelta(days=1), status='approved')
        self.client.force_authenticate(user=self.user)
        response = self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.external_ip)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_rejected_wfh_rejection(self):
        now = timezone.now()
        WFHRequest.objects.create(employee=self.employee, start_at=now - timedelta(days=1), end_at=now + timedelta(days=1), status='rejected')
        self.client.force_authenticate(user=self.user)
        response = self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.external_ip)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_superadmin_access(self):
        self.client.force_authenticate(user=self.super_user)
        response = self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.external_ip)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_duplicate_check_in(self):
        self.client.force_authenticate(user=self.user)
        self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.office_ip)
        response = self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.office_ip)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_successful_check_out(self):
        self.client.force_authenticate(user=self.user)
        self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.office_ip)
        response = self.client.post(reverse('attendance-check-out'), REMOTE_ADDR=self.office_ip)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(Attendance.objects.first().check_out)

    def test_check_out_before_check_in(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(reverse('attendance-check-out'), REMOTE_ADDR=self.office_ip)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_check_out(self):
        self.client.force_authenticate(user=self.user)
        self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.office_ip)
        self.client.post(reverse('attendance-check-out'), REMOTE_ADDR=self.office_ip)
        response = self.client.post(reverse('attendance-check-out'), REMOTE_ADDR=self.office_ip)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_employee_id_injection(self):
        self.client.force_authenticate(user=self.user)
        # Attempt to inject another employee ID
        response = self.client.post(reverse('attendance-check-in'), data={'employee': self.super_employee.id}, REMOTE_ADDR=self.office_ip)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Verify attendance was logged for self.user's employee, not the injected one
        attendance = Attendance.objects.first()
        self.assertEqual(attendance.employee.id, self.employee.id)

    def test_idor_view_attendance(self):
        Attendance.objects.create(employee=self.super_employee, date=timezone.now().date(), status='present')
        Attendance.objects.create(employee=self.employee, date=timezone.now().date(), status='present')
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse('attendance-list'), REMOTE_ADDR=self.office_ip)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['employee'], self.employee.id)

    def test_forwarded_ip_spoofing(self):
        self.client.force_authenticate(user=self.user)
        # Inject HTTP_X_FORWARDED_FOR with an office IP, while REMOTE_ADDR is external
        response = self.client.post(reverse('attendance-check-in'), REMOTE_ADDR=self.external_ip, HTTP_X_FORWARDED_FOR=self.office_ip)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
