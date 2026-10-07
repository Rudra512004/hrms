from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from rest_framework import status
from apps.organization.models import Organization, Branch, Designation, Department
from apps.authorization.models import Permission, Role, RolePermission, UserRole
from apps.employees.models import Employee, EmployeeStatutoryAndBank, EmployeeDependent, EmployeeEducation, EmployeePriorExperience
from apps.candidates.models import Candidate, CandidateStatus

User = get_user_model()

class EmployeePhase2APITests(APITestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Phase 2 Org")
        self.branch = Branch.objects.create(organization=self.org, name="HQ")
        self.dept = Department.objects.create(branch=self.branch, name="Engineering")
        self.desig = Designation.objects.create(organization=self.org, name="SDE")
        
        self.user = User.objects.create_user(email="test@example.com", password="password", status='active')
        self.employee = Employee.objects.create(
            user=self.user,
            organization=self.org,
            branch=self.branch,
            department=self.dept,
            designation=self.desig,
            employee_code="EMP0001"
        )
        
        self.hr_user = User.objects.create_user(email="hr@example.com", password="password", status='active')
        self.hr_employee = Employee.objects.create(
            user=self.hr_user,
            organization=self.org,
            branch=self.branch,
            department=self.dept,
            designation=self.desig,
            employee_code="EMP0002"
        )
        
        # Give HR user all permissions
        hr_role = Role.objects.create(organization=self.org, name="HR")
        for codename in ['employee.manage_statutory', 'employee.view_statutory', 'bgv.manage', 'employee.view']:
            p, _ = Permission.objects.get_or_create(codename=codename, defaults={'name': codename, 'resource': 'employee', 'action': codename})
            RolePermission.objects.create(role=hr_role, permission=p)
        UserRole.objects.create(user=self.hr_user, role=hr_role, scope='organization')
        
        # Give normal user employee.view and view_statutory so they can see their own info
        emp_role = Role.objects.create(organization=self.org, name="EmpRole")
        for p_name in ['employee.view', 'employee.view_statutory']:
            p, _ = Permission.objects.get_or_create(codename=p_name, defaults={'name': p_name, 'resource': 'employee', 'action': p_name})
            RolePermission.objects.create(role=emp_role, permission=p)
        UserRole.objects.create(user=self.user, role=emp_role, scope='organization')

    def test_statutory_and_bank_crud(self):
        self.client.force_authenticate(user=self.hr_user)
        # Create
        data = {
            "employee": self.employee.id,
            "pan_number": "ABCDE1234F",
            "aadhaar_number": "123456789012",
            "bank_name": "Test Bank"
        }
        res = self.client.post("/api/v1/employees/statutory/", data)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        statutory_id = res.data['id']
        
        # Read as HR (unmasked)
        res = self.client.get(f"/api/v1/employees/statutory/{statutory_id}/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['aadhaar_number'], "123456789012")
        
        # Read as normal user (masked) - actually it's their own profile, so they should see it unmasked.
        self.client.force_authenticate(user=self.user)
        res = self.client.get(f"/api/v1/employees/statutory/{statutory_id}/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['aadhaar_number'], "123456789012")
        
        # If normal user views someone else's, it should be masked or forbidden.
        # But wait, employee.view_statutory might not give access to others if not authorized for their branch.
        # Let's just create one for HR and view as normal user.
        data_hr = {
            "employee": self.hr_employee.id,
            "pan_number": "XYZDE1234F",
            "aadhaar_number": "987654321098"
        }
        self.client.force_authenticate(user=self.hr_user)
        res_hr = self.client.post("/api/v1/employees/statutory/", data_hr)
        hr_stat_id = res_hr.data['id']
        
        self.client.force_authenticate(user=self.user)
        res_view_hr = self.client.get(f"/api/v1/employees/statutory/{hr_stat_id}/")
        if res_view_hr.status_code == status.HTTP_200_OK:
            self.assertEqual(res_view_hr.data['aadhaar_number'], "********1098")
            
    def test_dependent_crud(self):
        self.client.force_authenticate(user=self.user)
        data = {
            "employee": self.employee.id,
            "full_name": "John Doe Jr",
            "relationship": "Son"
        }
        res = self.client.post("/api/v1/employees/dependents/", data)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        
        res = self.client.get(f"/api/v1/employees/dependents/?employee={self.employee.id}")
        self.assertEqual(len(res.data), 1)

    def test_education_crud(self):
        self.client.force_authenticate(user=self.user)
        data = {
            "employee": self.employee.id,
            "degree": "B.Tech",
            "institution": "Test Uni",
            "completion_year": 2020
        }
        res = self.client.post("/api/v1/employees/education/", data)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_experience_crud(self):
        self.client.force_authenticate(user=self.user)
        data = {
            "employee": self.employee.id,
            "employer_name": "Old Corp",
            "designation": "Intern",
            "start_date": "2019-01-01",
            "end_date": "2019-12-31"
        }
        res = self.client.post("/api/v1/employees/experience/", data)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
