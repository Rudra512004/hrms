from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta, date

from apps.organization.models import Organization
from apps.employees.models import Employee, ReviewCycle, PerformanceReview
from apps.authorization.models import Permission, Role, RolePermission, UserRole
from apps.audit.models import AuditLog

User = get_user_model()

class PerformanceReviewsTests(APITestCase):
    def setUp(self):
        self.org_a = Organization.objects.create(name='Org A')
        self.org_b = Organization.objects.create(name='Org B')

        # Org A Users & Employees
        self.u_mgr_a = User.objects.create_user(email='mgr_a@example.com', password='Password123!', status='active')
        self.emp_mgr_a = Employee.objects.create(user=self.u_mgr_a, organization=self.org_a, employee_code='MGR-A')

        self.u_emp_a = User.objects.create_user(email='emp_a@example.com', password='Password123!', status='active')
        self.emp_a = Employee.objects.create(user=self.u_emp_a, organization=self.org_a, employee_code='EMP-A', reporting_manager=self.emp_mgr_a)

        self.u_emp_b = User.objects.create_user(email='emp_b@example.com', password='Password123!', status='active')
        self.emp_b = Employee.objects.create(user=self.u_emp_b, organization=self.org_a, employee_code='EMP-B')

        # Org B Users & Employees
        self.u_mgr_b = User.objects.create_user(email='mgr_b@example.com', password='Password123!', status='active')
        self.emp_mgr_b = Employee.objects.create(user=self.u_mgr_b, organization=self.org_b, employee_code='MGR-B')

        self.u_emp_c = User.objects.create_user(email='emp_c@example.com', password='Password123!', status='active')
        self.emp_c = Employee.objects.create(user=self.u_emp_c, organization=self.org_b, employee_code='EMP-C', reporting_manager=self.emp_mgr_b)

        # Permissions & Roles setup
        self.perm_view, _ = Permission.objects.get_or_create(resource='employee', action='view', defaults={'name': 'View Employee', 'codename': 'employee.view'})
        self.perm_update, _ = Permission.objects.get_or_create(resource='employee', action='update', defaults={'name': 'Update Employee', 'codename': 'employee.update'})

        # Employee role (can only view)
        self.role_emp_a = Role.objects.create(organization=self.org_a, name='Employee')
        RolePermission.objects.create(role=self.role_emp_a, permission=self.perm_view)
        UserRole.objects.create(user=self.u_emp_a, role=self.role_emp_a)
        
        self.role_emp_a_2 = Role.objects.create(organization=self.org_a, name='Employee 2')
        RolePermission.objects.create(role=self.role_emp_a_2, permission=self.perm_view)
        UserRole.objects.create(user=self.u_emp_b, role=self.role_emp_a_2)

        self.role_emp_b = Role.objects.create(organization=self.org_b, name='Employee')
        RolePermission.objects.create(role=self.role_emp_b, permission=self.perm_view)
        UserRole.objects.create(user=self.u_emp_c, role=self.role_emp_b)

        # Manager role (can view and update)
        self.role_mgr_a = Role.objects.create(organization=self.org_a, name='Manager')
        RolePermission.objects.create(role=self.role_mgr_a, permission=self.perm_view)
        RolePermission.objects.create(role=self.role_mgr_a, permission=self.perm_update)
        UserRole.objects.create(user=self.u_mgr_a, role=self.role_mgr_a)

        self.role_mgr_b = Role.objects.create(organization=self.org_b, name='Manager')
        RolePermission.objects.create(role=self.role_mgr_b, permission=self.perm_view)
        RolePermission.objects.create(role=self.role_mgr_b, permission=self.perm_update)
        UserRole.objects.create(user=self.u_mgr_b, role=self.role_mgr_b)

        # Base Cycle
        self.cycle_a = ReviewCycle.objects.create(organization=self.org_a, name='2025 Q1', start_date=date(2025, 1, 1), end_date=date(2025, 3, 31))
        self.cycle_b = ReviewCycle.objects.create(organization=self.org_b, name='2025 Q1', start_date=date(2025, 1, 1), end_date=date(2025, 3, 31))

    # --- Authentication Tests ---
    def test_unauthenticated_access_denied(self):
        res = self.client.get('/api/v1/employees/reviews/')
        self.assertEqual(res.status_code, 401)
        res = self.client.post('/api/v1/employees/reviews/', {})
        self.assertEqual(res.status_code, 401)
        res = self.client.post('/api/v1/employees/reviews/999/submit/')
        self.assertEqual(res.status_code, 401)
        res = self.client.post('/api/v1/employees/reviews/999/acknowledge/')
        self.assertEqual(res.status_code, 401)

    # --- ReviewCycle Tests ---
    def test_create_review_cycle(self):
        self.client.force_authenticate(user=self.u_mgr_a)
        res = self.client.post('/api/v1/employees/review-cycles/', {
            'name': '2025 Q2',
            'start_date': '2025-04-01',
            'end_date': '2025-06-30'
        })
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data['organization'], self.org_a.id)

    def test_create_review_cycle_invalid_dates(self):
        self.client.force_authenticate(user=self.u_mgr_a)
        res = self.client.post('/api/v1/employees/review-cycles/', {
            'name': '2025 Q3',
            'start_date': '2025-09-30',
            'end_date': '2025-07-01'  # End before start
        })
        self.assertEqual(res.status_code, 400)

    def test_review_cycle_cross_tenant_isolation(self):
        self.client.force_authenticate(user=self.u_mgr_a)
        res = self.client.get('/api/v1/employees/review-cycles/')
        self.assertEqual(res.status_code, 200)
        cycle_ids = [c['id'] for c in res.data]
        self.assertIn(self.cycle_a.id, cycle_ids)
        self.assertNotIn(self.cycle_b.id, cycle_ids)

    # --- PerformanceReview Creation Tests ---
    def test_manager_create_review_valid(self):
        self.client.force_authenticate(user=self.u_mgr_a)
        res = self.client.post('/api/v1/employees/reviews/', {
            'cycle': self.cycle_a.id,
            'employee': self.emp_a.id,
            'rating': 4,
            'summary': 'Good work'
        })
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data['reviewer'], self.emp_mgr_a.id)

    def test_create_review_invalid_rating(self):
        self.client.force_authenticate(user=self.u_mgr_a)
        for rating in [0, 6]:
            res = self.client.post('/api/v1/employees/reviews/', {
                'cycle': self.cycle_a.id,
                'employee': self.emp_a.id,
                'rating': rating,
                'summary': 'Bad rating bounds'
            })
            self.assertEqual(res.status_code, 400, f"Rating {rating} should be rejected.")

    def test_create_review_cross_tenant_employee(self):
        self.client.force_authenticate(user=self.u_mgr_a)
        res = self.client.post('/api/v1/employees/reviews/', {
            'cycle': self.cycle_a.id,
            'employee': self.emp_c.id,  # From Org B
            'rating': 3,
            'summary': 'Cross tenant'
        })
        self.assertEqual(res.status_code, 400)
        
    def test_create_review_cross_tenant_cycle(self):
        self.client.force_authenticate(user=self.u_mgr_a)
        res = self.client.post('/api/v1/employees/reviews/', {
            'cycle': self.cycle_b.id,  # From Org B
            'employee': self.emp_a.id,
            'rating': 3,
            'summary': 'Cross tenant cycle'
        })
        self.assertEqual(res.status_code, 400)

    # --- Access & IDOR Tests ---
    def test_employee_access_isolation(self):
        # Create reviews manually
        rev_a = PerformanceReview.objects.create(cycle=self.cycle_a, employee=self.emp_a, reviewer=self.emp_mgr_a)
        rev_b = PerformanceReview.objects.create(cycle=self.cycle_a, employee=self.emp_b, reviewer=self.emp_mgr_a)
        rev_c = PerformanceReview.objects.create(cycle=self.cycle_b, employee=self.emp_c, reviewer=self.emp_mgr_b)

        self.client.force_authenticate(user=self.u_emp_a)
        
        # 1. Employee A can see their own review
        res = self.client.get('/api/v1/employees/reviews/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['id'], rev_a.id)
        
        res = self.client.get(f'/api/v1/employees/reviews/{rev_a.id}/')
        self.assertEqual(res.status_code, 200)

        # 2. Employee A cannot see Employee B's review (IDOR test)
        res = self.client.get(f'/api/v1/employees/reviews/{rev_b.id}/')
        self.assertEqual(res.status_code, 404)

        # 3. Employee A cannot see Employee C's review (Cross-tenant IDOR test)
        res = self.client.get(f'/api/v1/employees/reviews/{rev_c.id}/')
        self.assertEqual(res.status_code, 404)

    def test_manager_access_isolation(self):
        rev_a = PerformanceReview.objects.create(cycle=self.cycle_a, employee=self.emp_a, reviewer=self.emp_mgr_a)
        rev_b = PerformanceReview.objects.create(cycle=self.cycle_a, employee=self.emp_b, reviewer=self.emp_mgr_a) # emp_b is not direct report
        rev_c = PerformanceReview.objects.create(cycle=self.cycle_b, employee=self.emp_c, reviewer=self.emp_mgr_b)

        self.client.force_authenticate(user=self.u_mgr_a)
        
        # 1. Manager A can see their direct report's review (emp_a) and their own reviews
        res = self.client.get('/api/v1/employees/reviews/')
        self.assertEqual(res.status_code, 200)
        
        res = self.client.get(f'/api/v1/employees/reviews/{rev_a.id}/')
        self.assertEqual(res.status_code, 200)

        # 2. Manager A cannot see unrelated employee's review
        res = self.client.get(f'/api/v1/employees/reviews/{rev_b.id}/')
        self.assertEqual(res.status_code, 404)
        
        # 3. Manager A cannot see cross-tenant employee's review
        res = self.client.get(f'/api/v1/employees/reviews/{rev_c.id}/')
        self.assertEqual(res.status_code, 404)

    # --- Workflow & State Transitions ---
    def test_workflow_transitions(self):
        rev = PerformanceReview.objects.create(cycle=self.cycle_a, employee=self.emp_a, reviewer=self.emp_mgr_a)
        self.assertEqual(rev.status, 'draft')

        # Submit (Manager)
        self.client.force_authenticate(user=self.u_mgr_a)
        res = self.client.post(f'/api/v1/employees/reviews/{rev.id}/submit/')
        self.assertEqual(res.status_code, 200)
        rev.refresh_from_db()
        self.assertEqual(rev.status, 'submitted')

        # Acknowledge (Employee)
        self.client.force_authenticate(user=self.u_emp_a)
        res = self.client.post(f'/api/v1/employees/reviews/{rev.id}/acknowledge/')
        self.assertEqual(res.status_code, 200)
        rev.refresh_from_db()
        self.assertEqual(rev.status, 'acknowledged')

    def test_invalid_workflow_transitions(self):
        rev = PerformanceReview.objects.create(cycle=self.cycle_a, employee=self.emp_a, reviewer=self.emp_mgr_a)

        # Cannot acknowledge a draft
        self.client.force_authenticate(user=self.u_emp_a)
        res = self.client.post(f'/api/v1/employees/reviews/{rev.id}/acknowledge/')
        self.assertEqual(res.status_code, 400)
        
        # Submit
        self.client.force_authenticate(user=self.u_mgr_a)
        self.client.post(f'/api/v1/employees/reviews/{rev.id}/submit/')

        # Cannot submit an already submitted review
        res = self.client.post(f'/api/v1/employees/reviews/{rev.id}/submit/')
        self.assertEqual(res.status_code, 400)

        # Acknowledge
        self.client.force_authenticate(user=self.u_emp_a)
        self.client.post(f'/api/v1/employees/reviews/{rev.id}/acknowledge/')

        # Cannot acknowledge an already acknowledged review
        res = self.client.post(f'/api/v1/employees/reviews/{rev.id}/acknowledge/')
        self.assertEqual(res.status_code, 400)
        
        # Cannot submit an acknowledged review
        self.client.force_authenticate(user=self.u_mgr_a)
        res = self.client.post(f'/api/v1/employees/reviews/{rev.id}/submit/')
        self.assertEqual(res.status_code, 400)

    # --- Authorization for Actions ---
    def test_submit_authorization(self):
        rev = PerformanceReview.objects.create(cycle=self.cycle_a, employee=self.emp_a, reviewer=self.emp_mgr_a)

        # Employee cannot submit
        self.client.force_authenticate(user=self.u_emp_a)
        res = self.client.post(f'/api/v1/employees/reviews/{rev.id}/submit/')
        self.assertIn(res.status_code, [400, 403, 404])
        
        # Unrelated manager cannot submit
        self.client.force_authenticate(user=self.u_mgr_b)
        res = self.client.post(f'/api/v1/employees/reviews/{rev.id}/submit/')
        self.assertEqual(res.status_code, 404)

        # Reviewer can submit
        self.client.force_authenticate(user=self.u_mgr_a)
        res = self.client.post(f'/api/v1/employees/reviews/{rev.id}/submit/')
        self.assertEqual(res.status_code, 200)

    def test_acknowledge_authorization(self):
        rev = PerformanceReview.objects.create(cycle=self.cycle_a, employee=self.emp_a, reviewer=self.emp_mgr_a, status='submitted')

        # Reviewer cannot acknowledge
        self.client.force_authenticate(user=self.u_mgr_a)
        res = self.client.post(f'/api/v1/employees/reviews/{rev.id}/acknowledge/')
        self.assertIn(res.status_code, [400, 403, 404])

        # Another employee cannot acknowledge
        self.client.force_authenticate(user=self.u_emp_b)
        res = self.client.post(f'/api/v1/employees/reviews/{rev.id}/acknowledge/')
        self.assertEqual(res.status_code, 404)

        # Reviewed employee can acknowledge
        self.client.force_authenticate(user=self.u_emp_a)
        res = self.client.post(f'/api/v1/employees/reviews/{rev.id}/acknowledge/')
        self.assertEqual(res.status_code, 200)

    # --- Audit Logging ---
    def test_audit_logging(self):
        self.client.force_authenticate(user=self.u_mgr_a)
        
        # Create
        res = self.client.post('/api/v1/employees/reviews/', {
            'cycle': self.cycle_a.id,
            'employee': self.emp_a.id,
            'rating': 3,
            'summary': 'Audit test'
        })
        self.assertEqual(res.status_code, 201)
        rev_id = res.data['id']
        self.assertTrue(AuditLog.objects.filter(action='performance_review_created', target_id=str(rev_id)).exists())

        # Submit
        res = self.client.post(f'/api/v1/employees/reviews/{rev_id}/submit/')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(AuditLog.objects.filter(action='performance_review_submitted', target_id=str(rev_id)).exists())

        # Acknowledge
        self.client.force_authenticate(user=self.u_emp_a)
        res = self.client.post(f'/api/v1/employees/reviews/{rev_id}/acknowledge/')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(AuditLog.objects.filter(action='performance_review_acknowledged', target_id=str(rev_id)).exists())
