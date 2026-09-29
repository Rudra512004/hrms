from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from apps.organization.models import Organization, Branch, Designation, Department
from apps.authorization.models import Role, Permission, RolePermission, UserRole
from apps.candidates.models import Candidate, LetterTemplate, IssuedLetter, CandidateDocument
from apps.employees.models import Employee

User = get_user_model()

class CandidateWorkflowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.org = Organization.objects.create(name='Test Org', status='active')
        self.org2 = Organization.objects.create(name='Other Org', status='active')
        self.branch = Branch.objects.create(organization=self.org, name='Test Branch', is_active=True)
        self.dept = Department.objects.create(branch=self.branch, name='Engineering')
        self.designation = Designation.objects.create(organization=self.org, name='SDE')

        # HR User
        self.hr_user = User.objects.create_user(email='hr@test.com', password='password', first_name='HR', last_name='User', status='active')
        self.hr_emp = Employee.objects.create(user=self.hr_user, organization=self.org, branch=self.branch, employee_code='EMP001', personal_email='hr@test.com')
        hr_role = Role.objects.create(organization=self.org, name='HR')
        UserRole.objects.create(user=self.hr_user, role=hr_role)

        # Assign permissions
        perms = [
            'candidate.view', 'candidate.create', 'candidate.update', 'candidate.manage_status',
            'candidate.onboard', 'candidate.verify', 'candidate.convert',
            'letter.view', 'letter.issue',
            'employee.view', 'employee.create'
        ]
        for p_code in perms:
            resource, action = p_code.split('.')
            p, _ = Permission.objects.get_or_create(codename=p_code, defaults={'name': p_code, 'resource': resource, 'action': action})
            RolePermission.objects.create(role=hr_role, permission=p)

        self.client.force_authenticate(user=self.hr_user)

    def test_candidate_crud_and_organization_isolation(self):
        from apps.authorization.services import AuthorizationService
        print("PERMS:", AuthorizationService.get_effective_permissions(self.hr_user))
        
        # Create
        data = {
            'organization': self.org.id,
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john.doe@example.com',
            'phone_number': '1234567890'
        }
        res = self.client.post('/api/v1/candidates/', data)
        print("CREATE CANDIDATE RESPONSE:", res.data)
        if res.status_code != status.HTTP_201_CREATED:
            print("CREATE CANDIDATE ERROR:", res.data)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        c_id = Candidate.objects.get(email='john.doe@example.com').id

        # View
        res = self.client.get(f'/api/v1/candidates/{c_id}/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Organization isolation
        other_branch = Branch.objects.create(organization=self.org2, name='Other Branch', is_active=True)
        other_hr = User.objects.create_user(email='other_hr@test.com', password='password', first_name='HR2', last_name='User2', status='active')
        other_hr_emp = Employee.objects.create(user=other_hr, organization=self.org2, branch=other_branch, employee_code='EMP002', personal_email='other_hr@test.com')
        other_hr_role = Role.objects.create(organization=self.org2, name='HR2')
        UserRole.objects.create(user=other_hr, role=other_hr_role)
        p = Permission.objects.get(codename='candidate.view')
        RolePermission.objects.create(role=other_hr_role, permission=p)

        client2 = APIClient()
        client2.force_authenticate(user=other_hr)
        res = client2.get(f'/api/v1/candidates/{c_id}/')
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_onboarding_workflow_end_to_end(self):
        # 1. Create candidate
        c = Candidate.objects.create(
            organization=self.org,
            first_name='Jane',
            last_name='Smith',
            email='jane.smith@example.com',
            status='created'
        )

        # 2. Issue offer (HR)
        tmpl = LetterTemplate.objects.create(organization=self.org, letter_type='offer', version=1, subject='Offer', body='Welcome {{candidate_name}}')
        res = self.client.post(f'/api/v1/candidates/{c.id}/issue-offer/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        c.refresh_from_db()
        self.assertEqual(c.status, 'offered')

        # 3. Candidate portal auth & activation (simulated by directly setting password)
        c.user.set_password('newpass123')
        c.user.save()

        client_cand = APIClient()
        client_cand.force_authenticate(user=c.user)

        # Portal view
        res = client_cand.get('/api/v1/candidates/portal/me/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['email'], c.email)

        # Portal letters
        res = client_cand.get('/api/v1/candidates/portal/letters/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)

        # 4. Upload docs (Candidate)
        # We'll just create one directly due to file mock complexity in minimal tests
        doc = CandidateDocument.objects.create(candidate=c, document_type='identity', document_name='id.pdf', file_size=0)

        # Simulate accepting offer
        c.status = 'onboarding'
        c.save()
        
        # 5. Submit onboarding (Candidate)
        res = client_cand.post('/api/v1/candidates/portal/submit/')
        if res.status_code != status.HTTP_200_OK:
            print("SUBMIT ERROR:", res.data)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        c.refresh_from_db()
        self.assertEqual(c.status, 'submitted')

        # 6. Verify docs (HR)
        res = self.client.post(f'/api/v1/candidates/{c.id}/verify-documents/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        c.refresh_from_db()
        self.assertEqual(c.status, 'verifying')

        res = self.client.post(f'/api/v1/candidates/{c.id}/documents/{doc.id}/verify/', {'decision': 'verified'})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        doc.refresh_from_db()
        self.assertEqual(doc.status, 'verified')

        # 7. Approve (HR)
        res = self.client.post(f'/api/v1/candidates/{c.id}/approve/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        c.refresh_from_db()
        self.assertEqual(c.status, 'approved')

        # 8. Convert to Employee (HR)
        LetterTemplate.objects.create(organization=self.org, letter_type='appointment', version=1, subject='Appt', body='Appt {{candidate_name}}')
        res = self.client.post(f'/api/v1/candidates/{c.id}/convert-to-employee/')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        c.refresh_from_db()
        self.assertEqual(c.status, 'converted')
        self.assertIsNotNone(c.employee)
        
        # Verify duplicate conversion fails safely
        res = self.client.post(f'/api/v1/candidates/{c.id}/convert-to-employee/')
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)

    def test_candidate_cannot_access_employee_apis(self):
        c = Candidate.objects.create(
            organization=self.org,
            first_name='Jane',
            last_name='Smith',
            email='jane.smith@example.com',
            status='offered'
        )
        u = User.objects.create_user(email='jane.smith@example.com', password='password')
        c.user = u
        c.save()

        client_cand = APIClient()
        client_cand.force_authenticate(user=u)
        
        # Try to access employees list
        res = client_cand.get('/api/v1/employees/')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
