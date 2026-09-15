from django.test import TransactionTestCase
from django.utils import timezone
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.employees.models import Employee
from apps.organization.models import Organization
from .models import Asset, AssetCategory
from apps.notifications.models import Notification
from unittest.mock import patch

User = get_user_model()

class AssetNotificationIntegrationTests(TransactionTestCase):
    def setUp(self):
        self.client = APIClient()
        self.org = Organization.objects.create(name='Asset Org')

        self.user = User.objects.create_user(email='emp_asset@example.com', password='Password123!', status='active')
        self.employee = Employee.objects.create(user=self.user, employee_code='ASS01', organization=self.org)

        self.admin_user = User.objects.create_user(email='admin_asset@example.com', password='Password123!', status='active', is_superuser=True)

        self.category = AssetCategory.objects.create(organization=self.org, name='Laptops', code='LAP')
        self.asset = Asset.objects.create(organization=self.org, category=self.category, asset_tag='LAP-001', name='Dell XPS', status='available')

    @patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True)
    def test_asset_assigned_notification(self, mock_perm):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(f'/api/v1/assets/{self.asset.pk}/assign/', {
            'employee': self.employee.id,
            'allocated_at': timezone.now().date().isoformat()
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        notifs = Notification.objects.filter(recipient=self.user)
        self.assertEqual(notifs.count(), 1)
        notif = notifs.first()
        self.assertEqual(notif.notification_type, 'ASSET_ASSIGNED')
        self.assertEqual(notif.organization, self.org)
        self.assertIn('Dell XPS', notif.message)

    @patch('apps.authorization.services.AuthorizationService.has_permission', return_value=True)
    def test_asset_returned_notification(self, mock_perm):
        # Assign first without API
        self.asset.status = 'assigned'
        self.asset.save()
        from apps.assets.models import AssetAssignment
        AssetAssignment.objects.create(asset=self.asset, employee=self.employee, allocated_at=timezone.now().date(), is_active=True, assigned_by=self.admin_user)

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(f'/api/v1/assets/{self.asset.pk}/return/', {
            'condition_notes': 'Good'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        notifs = Notification.objects.filter(recipient=self.user)
        self.assertEqual(notifs.count(), 1)
        notif = notifs.first()
        self.assertEqual(notif.notification_type, 'ASSET_RETURNED')
        self.assertEqual(notif.organization, self.org)
        self.assertIn('Dell XPS', notif.message)
