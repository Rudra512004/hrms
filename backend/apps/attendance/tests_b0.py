import json
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
from apps.organization.models import Organization, Branch, OfficeNetwork, AttendancePolicy
from apps.employees.models import Employee, WFHRequest
from apps.accounts.models import User

class B0AttendanceSecurityTests(APITestCase):
    def setUp(self):
        # Create Organizations
        self.org_a = Organization.objects.create(name="Org A")
        self.org_b = Organization.objects.create(name="Org B")

        # Create Branches
        self.branch_a = Branch.objects.create(
            organization=self.org_a, name="HQ A",
            latitude='12.971600', longitude='77.594600', radius=100.0
        )
        self.branch_b = Branch.objects.create(
            organization=self.org_b, name="HQ B",
            latitude='12.971600', longitude='77.594600', radius=100.0
        )

        # Create Attendance Policies
        self.policy_a = self.branch_a.attendance_policy
        self.policy_a.is_office_gps_enabled = True
        self.policy_a.is_office_ip_enabled = True
        self.policy_a.is_wfh_enabled = True
        self.policy_a.wfh_bypasses_office_restrictions = True
        self.policy_a.save()

        self.policy_b = self.branch_b.attendance_policy
        self.policy_b.is_office_gps_enabled = True
        self.policy_b.is_office_ip_enabled = True
        self.policy_b.is_wfh_enabled = True
        self.policy_b.wfh_bypasses_office_restrictions = True
        self.policy_b.save()

        # Create Networks
        self.net_a = OfficeNetwork.objects.create(branch=self.branch_a, name="Net A", network="192.168.1.0/24")
        self.net_b = OfficeNetwork.objects.create(branch=self.branch_b, name="Net B", network="10.0.0.0/8")

        # Create User & Employee for Org A
        self.user_a = User.objects.create_user(email="emp_a@orga.com", password="pwd", first_name="Emp", last_name="A")
        self.emp_a = Employee.objects.create(
            user=self.user_a, organization=self.org_a,
            branch=self.branch_a,
            employee_code="EMP-001"
        )

        self.url = reverse('attendance-check-in')

    def test_radius_validation(self):
        # Enforce Branch radius >=100m.
        branch = Branch(
            organization=self.org_a, name="Invalid Branch",
            latitude='12.000000', longitude='77.000000', radius=99.0
        )
        with self.assertRaises(Exception):
            branch.full_clean()

    def test_cross_tenant_network_rejection(self):
        self.client.force_authenticate(user=self.user_a)
        data = {'latitude': 12.9716, 'longitude': 77.5946, 'accuracy': 50}
        response = self.client.post(self.url, data, REMOTE_ADDR='10.0.0.5', format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['detail'], 'ATTENDANCE_OUTSIDE_OFFICE_NETWORK')

    def test_gps_and_ip_valid(self):
        self.client.force_authenticate(user=self.user_a)
        data = {'latitude': 12.9716, 'longitude': 77.5946, 'accuracy': 50}
        response = self.client.post(self.url, data, REMOTE_ADDR='192.168.1.50', format='json')
        print("Response data:", response.data if hasattr(response, 'data') else response.content)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_gps_outside_radius(self):
        self.client.force_authenticate(user=self.user_a)
        data = {'latitude': 13.0, 'longitude': 77.6, 'accuracy': 50}
        response = self.client.post(self.url, data, REMOTE_ADDR='192.168.1.50', format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['detail'], 'ATTENDANCE_OUTSIDE_GEOFENCE')

    def test_missing_branch_coordinates_gps_enabled_rejection(self):
        self.branch_a.latitude = None
        self.branch_a.longitude = None
        self.branch_a.save()

        self.client.force_authenticate(user=self.user_a)
        data = {'latitude': 12.9716, 'longitude': 77.5946, 'accuracy': 50}
        response = self.client.post(self.url, data, REMOTE_ADDR='192.168.1.50', format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['detail'], 'ATTENDANCE_OUTSIDE_GEOFENCE')

    def test_gps_disabled_ip_valid(self):
        self.policy_a.is_office_gps_enabled = False
        self.policy_a.save()

        self.client.force_authenticate(user=self.user_a)
        self.branch_a.latitude = None
        self.branch_a.longitude = None
        self.branch_a.save()

        data = {'latitude': 13.0, 'longitude': 77.6, 'accuracy': 50}
        response = self.client.post(self.url, data, REMOTE_ADDR='192.168.1.50', format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_ip_disabled_gps_valid(self):
        self.policy_a.is_office_ip_enabled = False
        self.policy_a.save()

        self.client.force_authenticate(user=self.user_a)
        data = {'latitude': 12.9716, 'longitude': 77.5946, 'accuracy': 50}
        response = self.client.post(self.url, data, REMOTE_ADDR='8.8.8.8', format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_wfh_bypass_valid(self):
        now = timezone.now()
        WFHRequest.objects.create(
            employee=self.emp_a, status='approved',
            start_at=now - timedelta(days=1),
            end_at=now + timedelta(days=1)
        )

        self.client.force_authenticate(user=self.user_a)
        data = {'latitude': 13.0, 'longitude': 77.6, 'accuracy': 50}
        response = self.client.post(self.url, data, REMOTE_ADDR='8.8.8.8', format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_wfh_bypass_unapproved(self):
        now = timezone.now()
        WFHRequest.objects.create(
            employee=self.emp_a, status='pending',
            start_at=now - timedelta(days=1),
            end_at=now + timedelta(days=1)
        )

        self.client.force_authenticate(user=self.user_a)
        data = {'latitude': 13.0, 'longitude': 77.6, 'accuracy': 50}
        response = self.client.post(self.url, data, REMOTE_ADDR='8.8.8.8', format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_wfh_disabled_no_bypass(self):
        self.policy_a.is_wfh_enabled = False
        self.policy_a.save()

        now = timezone.now()
        WFHRequest.objects.create(
            employee=self.emp_a, status='approved',
            start_at=now - timedelta(days=1),
            end_at=now + timedelta(days=1)
        )

        self.client.force_authenticate(user=self.user_a)
        data = {'latitude': 13.0, 'longitude': 77.6, 'accuracy': 50}
        response = self.client.post(self.url, data, REMOTE_ADDR='8.8.8.8', format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
