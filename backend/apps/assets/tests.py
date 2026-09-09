from decimal import Decimal
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import User
from apps.organization.models import Organization, Branch, OfficeNetwork
from apps.authorization.models import Permission, Role, RolePermission, UserRole
from apps.employees.models import Employee, EmploymentStatus
from apps.audit.models import AuditLog
from .models import AssetCategory, Asset, AssetAssignment, AssetStatus


# ──────────────────────────────────────────────────────────────────────────────
# Test Helpers
# ──────────────────────────────────────────────────────────────────────────────

def make_user(email, first_name='Test', last_name='User', is_superuser=False):
    user = User.objects.create_user(email=email, first_name=first_name, last_name=last_name, password='password123')
    user.status = 'active'
    if is_superuser:
        user.is_superuser = True
    user.save()
    return user


def make_employee(user, org, code, status=EmploymentStatus.ACTIVE, branch=None):
    return Employee.objects.create(
        user=user,
        organization=org,
        employee_code=code,
        employment_status=status,
        branch=branch,
    )


def make_token(user):
    from rest_framework.authtoken.models import Token
    token, _ = Token.objects.get_or_create(user=user)
    return token.key


def auth_client(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Token {make_token(user)}')
    return client


def grant_permission(user, codename):
    perm = Permission.objects.filter(codename=codename).first()
    if not perm:
        if '.' in codename:
            resource, action = codename.split('.', 1)
        else:
            resource, action = codename, 'manage'
        perm, _ = Permission.objects.get_or_create(
            codename=codename,
            defaults={'name': codename, 'resource': resource, 'action': action}
        )
    role, _ = Role.objects.get_or_create(
        name=f'role_{codename}',
        organization=user.employee.organization,
        defaults={'description': ''}
    )
    RolePermission.objects.get_or_create(role=role, permission=perm)
    UserRole.objects.get_or_create(user=user, role=role)


CATEGORIES_URL = '/api/v1/assets/categories/'
ASSETS_URL = '/api/v1/assets/'
DETAIL_URL = lambda pk: f'/api/v1/assets/{pk}/'
ASSIGN_URL = lambda pk: f'/api/v1/assets/{pk}/assign/'
RETURN_URL = lambda pk: f'/api/v1/assets/{pk}/return/'
MY_ASSETS_URL = '/api/v1/assets/my-assets/'


# ──────────────────────────────────────────────────────────────────────────────
# Comprehensive Asset Management Test Suite
# ──────────────────────────────────────────────────────────────────────────────

class AssetManagementComprehensiveTests(TestCase):

    def setUp(self):
        # Organizations
        self.org_a = Organization.objects.create(name='Org A Assets', status='active')
        self.org_b = Organization.objects.create(name='Org B Assets', status='active')

        # Allow 127.0.0.0/8 so test client passes IsNetworkAllowed
        OfficeNetwork.objects.create(
            organization=self.org_a,
            name='Localhost A',
            network='127.0.0.0/8',
            is_active=True,
        )

        # Branches
        self.branch_a = Branch.objects.create(organization=self.org_a, name='HQ Branch')
        self.branch_b = Branch.objects.create(organization=self.org_b, name='Org B Branch')

        # Admin User with full asset permissions in Org A
        self.admin_user = make_user('asset_admin@orga.com', 'Admin', 'User')
        self.admin_emp = make_employee(self.admin_user, self.org_a, 'ADM_AST_01', branch=self.branch_a)
        for p in ['asset.view', 'asset.create', 'asset.update', 'asset.delete', 'asset.assign']:
            grant_permission(self.admin_user, p)

        # Standard Employees in Org A
        self.emp_user1 = make_user('emp1@orga.com', 'Alice', 'Smith')
        self.emp1 = make_employee(self.emp_user1, self.org_a, 'EMP_AST_01', branch=self.branch_a)

        self.emp_user2 = make_user('emp2@orga.com', 'Bob', 'Jones')
        self.emp2 = make_employee(self.emp_user2, self.org_a, 'EMP_AST_02', branch=self.branch_a)

        # Exited Employee in Org A
        self.exited_user = make_user('exited@orga.com', 'Exited', 'Employee')
        self.exited_emp = make_employee(self.exited_user, self.org_a, 'EMP_EXITED', status=EmploymentStatus.EXITED)

        # Org B User & Employee
        self.org_b_user = make_user('admin@orgb.com', 'OrgB', 'Admin')
        self.org_b_emp = make_employee(self.org_b_user, self.org_b, 'ORGB_EMP_01', branch=self.branch_b)
        grant_permission(self.org_b_user, 'asset.view')
        grant_permission(self.org_b_user, 'asset.create')

        # Seed categories
        self.cat_laptop = AssetCategory.objects.create(
            organization=self.org_a, name='Laptops', code='LAPTOP', description='Portable computers'
        )
        self.cat_monitor = AssetCategory.objects.create(
            organization=self.org_a, name='Monitors', code='MONITOR'
        )
        self.cat_b = AssetCategory.objects.create(
            organization=self.org_b, name='Laptops B', code='LAPTOP'
        )

        # Seed initial asset in Org A
        self.asset1 = Asset.objects.create(
            organization=self.org_a,
            category=self.cat_laptop,
            branch=self.branch_a,
            asset_tag='AST-001',
            name='MacBook Pro 16',
            serial_number='C02G12345',
            model_number='A2485',
            status=AssetStatus.AVAILABLE,
            purchase_date='2026-01-15',
            purchase_cost=Decimal('2499.00'),
        )

    # 1. Category creation
    def test_01_category_creation(self):
        client = auth_client(self.admin_user)
        payload = {'name': 'Access Cards', 'code': 'ACCESS_CARD', 'description': 'Office RFID badges'}
        res = client.post(CATEGORIES_URL, payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        self.assertEqual(res.data['name'], 'Access Cards')
        self.assertEqual(res.data['organization'], self.org_a.id)

    # 2. Category organization isolation
    def test_02_category_organization_isolation(self):
        client = auth_client(self.admin_user)
        res = client.get(CATEGORIES_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        category_ids = [c['id'] for c in res.data]
        self.assertIn(self.cat_laptop.id, category_ids)
        self.assertNotIn(self.cat_b.id, category_ids)

    # 3. Asset creation
    def test_03_asset_creation(self):
        client = auth_client(self.admin_user)
        payload = {
            'asset_tag': 'AST-002',
            'name': 'Dell UltraSharp 27',
            'category': self.cat_monitor.id,
            'branch': self.branch_a.id,
            'serial_number': 'CN09876',
            'purchase_cost': '450.00',
        }
        res = client.post(ASSETS_URL, payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        self.assertEqual(res.data['asset_tag'], 'AST-002')
        self.assertEqual(res.data['status'], AssetStatus.AVAILABLE)

    # 4. Asset organization isolation
    def test_04_asset_organization_isolation(self):
        asset_b = Asset.objects.create(
            organization=self.org_b,
            category=self.cat_b,
            asset_tag='AST-B-001',
            name='Org B ThinkPad',
            status=AssetStatus.AVAILABLE,
        )
        client = auth_client(self.admin_user)
        res = client.get(ASSETS_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        asset_ids = [a['id'] for a in res.data]
        self.assertIn(self.asset1.id, asset_ids)
        self.assertNotIn(asset_b.id, asset_ids)

    # 5. Duplicate asset tag within organization rejected
    def test_05_duplicate_asset_tag_within_organization(self):
        client = auth_client(self.admin_user)
        payload = {
            'asset_tag': 'AST-001',  # already exists in Org A
            'name': 'Duplicate Tag Laptop',
            'category': self.cat_laptop.id,
        }
        res = client.post(ASSETS_URL, payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # 6. Same asset tag allowed in different organizations
    def test_06_same_asset_tag_allowed_in_different_orgs(self):
        client = auth_client(self.org_b_user)
        payload = {
            'asset_tag': 'AST-001',  # same tag as in Org A, but for Org B
            'name': 'Org B Laptop with same tag',
            'category': self.cat_b.id,
        }
        res = client.post(ASSETS_URL, payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        self.assertEqual(res.data['asset_tag'], 'AST-001')

    # 7. Asset listing with filters
    def test_07_asset_listing_and_filters(self):
        client = auth_client(self.admin_user)
        res = client.get(f'{ASSETS_URL}?category={self.cat_laptop.id}')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)

        res_search = client.get(f'{ASSETS_URL}?search=MacBook')
        self.assertEqual(res_search.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_search.data), 1)

    # 8. Asset retrieval
    def test_08_asset_retrieval(self):
        client = auth_client(self.admin_user)
        res = client.get(DETAIL_URL(self.asset1.id))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['id'], self.asset1.id)
        self.assertIn('assignment_history', res.data)

    # 9. Asset update
    def test_09_asset_update(self):
        client = auth_client(self.admin_user)
        res = client.patch(DETAIL_URL(self.asset1.id), {'notes': 'Upgraded RAM to 32GB'})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.asset1.refresh_from_db()
        self.assertEqual(self.asset1.notes, 'Upgraded RAM to 32GB')

    # 10. RBAC view enforcement
    def test_10_rbac_view_enforced(self):
        client = auth_client(self.emp_user1)  # standard employee without asset.view
        res = client.get(ASSETS_URL)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    # 11. RBAC create enforcement
    def test_11_rbac_create_enforced(self):
        client = auth_client(self.emp_user1)
        res = client.post(ASSETS_URL, {'asset_tag': 'AST-NEW', 'name': 'New', 'category': self.cat_laptop.id})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    # 12. RBAC update enforcement
    def test_12_rbac_update_enforced(self):
        client = auth_client(self.emp_user1)
        res = client.patch(DETAIL_URL(self.asset1.id), {'notes': 'hacked'})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    # 13. RBAC delete enforcement
    def test_13_rbac_delete_enforced(self):
        client = auth_client(self.emp_user1)
        res = client.delete(DETAIL_URL(self.asset1.id))
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    # 14. RBAC assign enforcement
    def test_14_rbac_assign_enforced(self):
        client = auth_client(self.emp_user1)
        res = client.post(ASSIGN_URL(self.asset1.id), {'employee': self.emp2.id})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    # 15. Unauthorized unauthenticated access blocked
    def test_15_unauthenticated_access_blocked(self):
        client = APIClient()
        res = client.get(ASSETS_URL)
        self.assertIn(res.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    # 16. Cross-organization asset IDOR returns 404
    def test_16_cross_org_asset_idor_returns_404(self):
        asset_b = Asset.objects.create(
            organization=self.org_b,
            category=self.cat_b,
            asset_tag='AST-B-SECRET',
            name='Org B Secret Asset',
            status=AssetStatus.AVAILABLE,
        )
        client = auth_client(self.admin_user)  # Org A admin
        res = client.get(DETAIL_URL(asset_b.id))
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    # 17. Valid assignment succeeds
    def test_17_valid_assignment_succeeds(self):
        client = auth_client(self.admin_user)
        payload = {
            'employee': self.emp1.id,
            'condition_at_allocation': 'excellent',
            'allocation_notes': 'Assigned for engineering project',
        }
        res = client.post(ASSIGN_URL(self.asset1.id), payload)
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.asset1.refresh_from_db()
        self.assertEqual(self.asset1.status, AssetStatus.ASSIGNED)
        self.assertTrue(self.asset1.assignments.filter(employee=self.emp1, is_active=True).exists())

    # 18. Assignment of unavailable asset fails
    def test_18_assignment_of_unavailable_asset_fails(self):
        self.asset1.status = AssetStatus.UNDER_MAINTENANCE
        self.asset1.save()
        client = auth_client(self.admin_user)
        res = client.post(ASSIGN_URL(self.asset1.id), {'employee': self.emp1.id})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # 19. Duplicate active assignment blocked
    def test_19_duplicate_active_assignment_blocked(self):
        # Assign asset once
        AssetAssignment.objects.create(
            asset=self.asset1, employee=self.emp1, condition_at_allocation='good', is_active=True
        )
        self.asset1.status = AssetStatus.ASSIGNED
        self.asset1.save()

        client = auth_client(self.admin_user)
        res = client.post(ASSIGN_URL(self.asset1.id), {'employee': self.emp2.id})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # 20. Cross-org assignment rejected
    def test_20_cross_org_assignment_rejected(self):
        client = auth_client(self.admin_user)
        # Attempt to assign Org A asset to Org B employee
        res = client.post(ASSIGN_URL(self.asset1.id), {'employee': self.org_b_emp.id})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # 21. Exited employee assignment rejected
    def test_21_exited_employee_assignment_rejected(self):
        client = auth_client(self.admin_user)
        res = client.post(ASSIGN_URL(self.asset1.id), {'employee': self.exited_emp.id})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # 22. Successful return closes assignment and updates status
    def test_22_successful_return(self):
        # Assign first
        AssetAssignment.objects.create(
            asset=self.asset1, employee=self.emp1, condition_at_allocation='good', is_active=True
        )
        self.asset1.status = AssetStatus.ASSIGNED
        self.asset1.save()

        client = auth_client(self.admin_user)
        payload = {
            'condition_at_return': 'fair',
            'return_notes': 'Minor scratch on lid',
            'next_status': 'available',
        }
        res = client.post(RETURN_URL(self.asset1.id), payload)
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)

        self.asset1.refresh_from_db()
        self.assertEqual(self.asset1.status, AssetStatus.AVAILABLE)
        self.assertFalse(self.asset1.assignments.filter(is_active=True).exists())
        self.assertTrue(self.asset1.assignments.filter(is_active=False, condition_at_return='fair').exists())

    # 23. Return without active assignment fails
    def test_23_return_without_active_assignment_fails(self):
        client = auth_client(self.admin_user)
        res = client.post(RETURN_URL(self.asset1.id), {'condition_at_return': 'good'})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # 24. Invalid return status rejected
    def test_24_invalid_return_status_rejected(self):
        AssetAssignment.objects.create(
            asset=self.asset1, employee=self.emp1, condition_at_allocation='good', is_active=True
        )
        self.asset1.status = AssetStatus.ASSIGNED
        self.asset1.save()

        client = auth_client(self.admin_user)
        res = client.post(RETURN_URL(self.asset1.id), {'next_status': 'invalid_status_xyz'})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # 25. Assigned asset deletion rejected
    def test_25_assigned_asset_deletion_rejected(self):
        AssetAssignment.objects.create(
            asset=self.asset1, employee=self.emp1, condition_at_allocation='good', is_active=True
        )
        self.asset1.status = AssetStatus.ASSIGNED
        self.asset1.save()

        client = auth_client(self.admin_user)
        res = client.delete(DETAIL_URL(self.asset1.id))
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Asset.objects.filter(id=self.asset1.id).exists())

    # 26. Historical assignment preservation after return
    def test_26_historical_assignment_preserved(self):
        assign1 = AssetAssignment.objects.create(
            asset=self.asset1, employee=self.emp1, condition_at_allocation='good', is_active=True
        )
        self.asset1.status = AssetStatus.ASSIGNED
        self.asset1.save()

        client = auth_client(self.admin_user)
        client.post(RETURN_URL(self.asset1.id), {'condition_at_return': 'good'})

        # Reassign to emp2
        client.post(ASSIGN_URL(self.asset1.id), {'employee': self.emp2.id})

        # Check detail endpoint returns both in history
        res = client.get(DETAIL_URL(self.asset1.id))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        history = res.data['assignment_history']
        self.assertEqual(len(history), 2)
        emp_ids = [h['employee'] for h in history]
        self.assertIn(self.emp1.id, emp_ids)
        self.assertIn(self.emp2.id, emp_ids)

    # 27. Reassignment after return succeeds
    def test_27_reassignment_after_return(self):
        AssetAssignment.objects.create(
            asset=self.asset1, employee=self.emp1, is_active=False, returned_at=timezone.now().date()
        )
        self.asset1.status = AssetStatus.AVAILABLE
        self.asset1.save()

        client = auth_client(self.admin_user)
        res = client.post(ASSIGN_URL(self.asset1.id), {'employee': self.emp2.id})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.asset1.refresh_from_db()
        self.assertEqual(self.asset1.status, AssetStatus.ASSIGNED)

    # 28. Self-service my-assets returns current employee's assets
    def test_28_self_service_my_assets(self):
        AssetAssignment.objects.create(
            asset=self.asset1, employee=self.emp1, condition_at_allocation='good', is_active=True
        )
        self.asset1.status = AssetStatus.ASSIGNED
        self.asset1.save()

        client = auth_client(self.emp_user1)  # emp1 self-service
        res = client.get(MY_ASSETS_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['asset'], self.asset1.id)
        self.assertEqual(res.data[0]['asset_tag'], 'AST-001')

    # 29. Self-service cannot see another employee's assets
    def test_29_self_service_cannot_see_other_assets(self):
        AssetAssignment.objects.create(
            asset=self.asset1, employee=self.emp1, condition_at_allocation='good', is_active=True
        )
        self.asset1.status = AssetStatus.ASSIGNED
        self.asset1.save()

        client = auth_client(self.emp_user2)  # emp2 has no assets assigned
        res = client.get(MY_ASSETS_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 0)

    # 30. Audit logging on asset events
    def test_30_audit_logging_on_asset_events(self):
        client = auth_client(self.admin_user)

        # 1. Create asset -> audit log
        count_before = AuditLog.objects.filter(action='asset_created').count()
        res_create = client.post(ASSETS_URL, {
            'asset_tag': 'AST-AUDIT-01',
            'name': 'Audit Test Mouse',
            'category': self.cat_laptop.id,
        })
        self.assertEqual(res_create.status_code, status.HTTP_201_CREATED)
        new_asset_id = res_create.data['id']
        self.assertEqual(AuditLog.objects.filter(action='asset_created').count(), count_before + 1)

        # 2. Assign asset -> audit log
        count_assign = AuditLog.objects.filter(action='asset_assigned').count()
        client.post(ASSIGN_URL(new_asset_id), {'employee': self.emp1.id})
        self.assertEqual(AuditLog.objects.filter(action='asset_assigned').count(), count_assign + 1)

        # 3. Return asset -> audit log
        count_return = AuditLog.objects.filter(action='asset_returned').count()
        client.post(RETURN_URL(new_asset_id), {'condition_at_return': 'good'})
        self.assertEqual(AuditLog.objects.filter(action='asset_returned').count(), count_return + 1)

        # 4. Delete asset -> audit log
        count_delete = AuditLog.objects.filter(action='asset_deleted').count()
        client.delete(DETAIL_URL(new_asset_id))
        self.assertEqual(AuditLog.objects.filter(action='asset_deleted').count(), count_delete + 1)

    # 31. Database unique constraint prevents duplicate active assignment
    def test_31_unique_active_assignment_constraint(self):
        from django.db import IntegrityError
        # Direct DB insert for active assignment
        AssetAssignment.objects.create(
            asset=self.asset1, employee=self.emp1, is_active=True
        )
        # Second active assignment directly at DB level must raise IntegrityError
        with self.assertRaises(IntegrityError):
            AssetAssignment.objects.create(
                asset=self.asset1, employee=self.emp2, is_active=True
            )
