from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from rest_framework import status
from apps.organization.models import Organization, Branch, Designation, Department
from apps.authorization.models import Permission, Role, RolePermission, UserRole
from apps.candidates.models import Candidate, JobRequisition, InterviewScorecard

User = get_user_model()

class CandidatePhase2APITests(APITestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Phase 2 Org")
        self.desig = Designation.objects.create(organization=self.org, name="SDE")
        
        self.hr_user = User.objects.create_user(email="hr@example.com", password="password", status='active')
        hr_role = Role.objects.create(organization=self.org, name="HR")
        for codename in ['candidate.requisition.manage', 'candidate.interview.manage', 'candidate.view']:
            p, _ = Permission.objects.get_or_create(codename=codename, defaults={'name': codename, 'resource': 'candidate', 'action': codename})
            RolePermission.objects.create(role=hr_role, permission=p)
        UserRole.objects.create(user=self.hr_user, role=hr_role, scope='organization')
        
        self.candidate = Candidate.objects.create(
            organization=self.org,
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
            applied_designation=self.desig
        )

    def test_job_requisition_crud(self):
        self.client.force_authenticate(user=self.hr_user)
        data = {
            "designation": self.desig.id,
            "headcount": 2,
            "budget_ctc": "1500000.00",
            "justification": "Need more devs"
        }
        res = self.client.post("/api/v1/candidates/requisitions/", data)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['approval_status'], "DRAFT")
        
        res = self.client.get("/api/v1/candidates/requisitions/")
        self.assertEqual(len(res.data), 1)

    def test_interview_scorecard_crud(self):
        self.client.force_authenticate(user=self.hr_user)
        data = {
            "candidate": self.candidate.id,
            "round_name": "Technical Round 1",
            "technical_score": 8,
            "cultural_score": 9,
            "recommendation": "STRONG_YES",
            "comments": "Great candidate"
        }
        res = self.client.post("/api/v1/candidates/scorecards/", data)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        
        res = self.client.get(f"/api/v1/candidates/scorecards/?candidate={self.candidate.id}")
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['recommendation'], "STRONG_YES")
