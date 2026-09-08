from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from django.urls import reverse
from apps.organization.models import Organization, Branch
from apps.employees.models import Employee
from apps.attendance.models import Attendance, Holiday, Shift
from rest_framework import status
from django.utils import timezone

User = get_user_model()

class GeofenceTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org1 = Organization.objects.create(name='Org 1')
        self.org2 = Organization.objects.create(name='Org 2')
        
        self.branch1 = Branch.objects.create(
            organization=self.org1, name='HQ', 
            latitude=19.0760, longitude=72.8777, radius=100.0
        )
        self.branch2 = Branch.objects.create(
            organization=self.org2, name='Remote', 
            latitude=28.7041, longitude=77.1025, radius=100.0
        )
        
        self.user1 = User.objects.create_user(email='emp1@test.com', password='Password123!', status='active')
        self.emp1 = Employee.objects.create(user=self.user1, employee_code='E1', organization=self.org1, branch=self.branch1)

        self.user2 = User.objects.create_user(email='emp2@test.com', password='Password123!', status='active')
        self.emp2 = Employee.objects.create(user=self.user2, employee_code='E2', organization=self.org2, branch=self.branch2)

        # User without branch
        self.user3 = User.objects.create_user(email='emp3@test.com', password='Password123!', status='active')
        self.emp3 = Employee.objects.create(user=self.user3, employee_code='E3', organization=self.org1)

    def test_unauthenticated(self):
        response = self.client.post(reverse('attendance-check-in'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_inside_geofence(self):
        self.client.force_authenticate(user=self.user1)
        response = self.client.post(reverse('attendance-check-in'), {
            'latitude': 19.0760,
            'longitude': 72.8777,
            'accuracy': 10.0
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        attendance = Attendance.objects.get(employee=self.emp1, date=timezone.now().date())
        self.assertEqual(float(attendance.check_in_latitude), 19.0760)

    def test_outside_geofence(self):
        self.client.force_authenticate(user=self.user1)
        response = self.client.post(reverse('attendance-check-in'), {
            'latitude': 19.0800, # Far away
            'longitude': 72.8800,
            'accuracy': 10.0
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['detail'], 'ATTENDANCE_OUTSIDE_GEOFENCE')

    def test_poor_accuracy(self):
        self.client.force_authenticate(user=self.user1)
        response = self.client.post(reverse('attendance-check-in'), {
            'latitude': 19.0760,
            'longitude': 72.8777,
            'accuracy': 200.0 # > 100m
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], 'POOR_GPS_ACCURACY')

    def test_missing_coordinates(self):
        self.client.force_authenticate(user=self.user1)
        response = self.client.post(reverse('attendance-check-in'), {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_employee_without_branch(self):
        self.client.force_authenticate(user=self.user3)
        # Should fallback to IsNetworkAllowed. Since it's testserver, NetworkAccessService will reject it
        response = self.client.post(reverse('attendance-check-in'), {
            'latitude': 19.0760,
            'longitude': 72.8777,
            'accuracy': 10.0
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['detail'], 'ATTENDANCE_OUTSIDE_GEOFENCE')

class BranchHolidayShiftTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org1 = Organization.objects.create(name='Org 1')
        self.org2 = Organization.objects.create(name='Org 2')
        self.user1 = User.objects.create_user(email='admin@test.com', password='Password123!', status='active')
        self.emp1 = Employee.objects.create(user=self.user1, employee_code='E1', organization=self.org1)

    def test_branch_creation(self):
        self.client.force_authenticate(user=self.user1)
        from apps.authorization.models import Role, Permission, RolePermission, UserRole
        role = Role.objects.create(organization=self.org1, name='Admin')
        perm, _ = Permission.objects.get_or_create(codename='branch.manage', defaults={'name':'Manage Branches', 'resource':'branch', 'action':'manage'})
        RolePermission.objects.create(role=role, permission=perm)
        UserRole.objects.create(user=self.user1, role=role)

        response = self.client.post(reverse('branch-list'), {
            'name': 'New Branch',
            'radius': 150.0
        })
        if response.status_code != status.HTTP_201_CREATED:
            print("Branch creation failed:", response.data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Branch.objects.count(), 1)
        self.assertEqual(Branch.objects.first().organization, self.org1)
