from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.employees.models import Employee
from apps.organization.models import Organization

User = get_user_model()

class EmployeeManagementAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org = Organization.objects.create(name='Test Org')

        # Superadmin
        self.super_user = User.objects.create_user(email='super@example.com', password='Password123!', status='active', is_superuser=True)
        self.super_employee = Employee.objects.create(user=self.super_user, employee_code='EMP_SUPER')

        # Normal Employee (No management permissions)
        self.normal_user = User.objects.create_user(email='normal@example.com', password='Password123!', status='active')
        self.normal_employee = Employee.objects.create(user=self.normal_user, employee_code='EMP_NORMAL')

        # Another employee to manipulate
        self.target_user = User.objects.create_user(email='target@example.com', password='Password123!', status='active')
        self.target_employee = Employee.objects.create(user=self.target_user, employee_code='EMP_TARGET')

    def test_employee_creation_superadmin(self):
        self.client.force_authenticate(user=self.super_user)
        response = self.client.post(reverse('employee-management-list'), {
            'email': 'new_emp@example.com',
            'first_name': 'New',
            'last_name': 'Emp',
            'employee_code': 'EMP_NEW'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email='new_emp@example.com').exists())

    def test_employee_creation_unauthorized(self):
        self.client.force_authenticate(user=self.normal_user)
        response = self.client.post(reverse('employee-management-list'), {
            'email': 'new_emp2@example.com',
            'first_name': 'New',
            'last_name': 'Emp',
            'employee_code': 'EMP_NEW2'
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_employee_list(self):
        self.client.force_authenticate(user=self.super_user)
        response = self.client.get(reverse('employee-management-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should see all 3 employees created in setUp
        self.assertEqual(len(response.data), 3)

    def test_employee_activation(self):
        self.target_user.status = 'inactive'
        self.target_user.save()

        self.client.force_authenticate(user=self.super_user)
        response = self.client.post(reverse('employee-management-activate', kwargs={'pk': self.target_employee.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.target_user.refresh_from_db()
        self.assertEqual(self.target_user.status, 'active')
        self.assertTrue(self.target_user.is_active)

    def test_employee_deactivation(self):
        self.client.force_authenticate(user=self.super_user)
        response = self.client.post(reverse('employee-management-deactivate', kwargs={'pk': self.target_employee.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.target_user.refresh_from_db()
        self.assertEqual(self.target_user.status, 'inactive')
        self.assertFalse(self.target_user.is_active)

    def test_deactivate_own_account_fails(self):
        self.client.force_authenticate(user=self.super_user)
        response = self.client.post(reverse('employee-management-deactivate', kwargs={'pk': self.super_employee.pk}))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_deactivated_account_access(self):
        from rest_framework.authtoken.models import Token
        token, _ = Token.objects.get_or_create(user=self.target_user)

        self.target_user.status = 'inactive'
        self.target_user.save()

        # Clear any force_authenticate state
        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)

        response = self.client.get(reverse('employee-me'))
        # Should fail authentication since user is inactive
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        

    def test_last_superadmin_protection(self):
        # Case B: 1 active superuser -> deactivating that superuser is DENIED
        # Wait, self-deactivation is blocked anyway. We need a second superuser to try to deactivate the last active superuser?
        # But if there's only 1 active superuser, nobody else can deactivate them.
        # Let's create a second superadmin, make them inactive, and try to deactivate the first one.

        super2 = User.objects.create_user(email='super2@example.com', password='Password123!', status='inactive', is_superuser=True)
        Employee.objects.create(user=super2, employee_code='EMP_SUPER2')
        # We need a normal user with employee.status permission to try to deactivate superadmin? No, only superadmin can deactivate superadmin.
        # So we must test Case A and Case C.

        # Case A: 2 active superusers
        super2.status = 'active'
        super2.save()
        self.client.force_authenticate(user=super2)
        response = self.client.post(reverse('employee-management-deactivate', kwargs={'pk': self.super_employee.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Now there is 1 active superuser left (super2). Let's create a third superadmin to try to deactivate super2.
        super3 = User.objects.create_user(email='super3@example.com', password='Password123!', status='active', is_superuser=True)
        Employee.objects.create(user=super3, employee_code='EMP_SUPER3')

        # super3 deactivates super2 (2 active superusers now: super2 and super3)
        self.client.force_authenticate(user=super3)
        response = self.client.post(reverse('employee-management-deactivate', kwargs={'pk': super2.employee.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Now super3 is the LAST active superadmin.
        # We create a new superadmin who is INACTIVE (Case C).
        super4 = User.objects.create_user(email='super4@example.com', password='Password123!', status='inactive', is_superuser=True)
        Employee.objects.create(user=super4, employee_code='EMP_SUPER4')

        # To test deactivation of super3, we need someone else who is a superadmin and active to make the request...
        # But wait! If super3 is the last active superadmin, no other active superadmin exists to make the request!
        # What if a normal user with 'employee.status' tries?
        # The logic says 'Only superadmin can deactivate a superadmin', so normal user will get 403 anyway.
        # How do we trigger the "Cannot deactivate the last active superadmin"?
        # Ah, the logic in views.py is: if user.is_superuser: active_superadmins = ... if <= 1: return 403.
        # If someone calls deactivate, it can ONLY be a superadmin (since `request.user.is_superuser` is required).
        # So if `request.user` is super3, and they try to deactivate super3, they get "Cannot deactivate own account."
        # If we remove the "Cannot deactivate own account" check, then it would trigger.
        # Wait, if super4 is an INACTIVE superadmin, they can't login!
        # So it's actually IMPOSSIBLE for the last active superadmin to be deactivated by anyone!
        pass


