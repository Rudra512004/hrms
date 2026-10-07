from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from apps.organization.models import Organization
from apps.authorization.models import Role, Permission, RolePermission, UserRole
from apps.documents.models import DocumentCategory, DocumentTemplate, TemplateType, IssuedDocument
from apps.employees.models import Employee
from apps.candidates.models import Candidate

User = get_user_model()

class DocumentVaultTests(APITestCase):
    def setUp(self):
        # Set up Organization A
        self.org_a = Organization.objects.create(name="Org A")
        self.user_a = User.objects.create_user(email="admin_a@test.com", password="pwd", first_name="Admin", last_name="A", status='active')
        self.employee_a = Employee.objects.create(
            organization=self.org_a,
            user=self.user_a,
            employee_code="A001"
        )
        
        # Set up Organization B
        self.org_b = Organization.objects.create(name="Org B")
        self.user_b = User.objects.create_user(email="admin_b@test.com", password="pwd", first_name="Admin", last_name="B", status='active')
        self.employee_b = Employee.objects.create(
            organization=self.org_b,
            user=self.user_b,
            employee_code="B001"
        )

        # Standard employee in Org A with no elevated permissions
        self.user_c = User.objects.create_user(email="user_c@test.com", password="pwd", first_name="Emp", last_name="C", status='active')
        self.employee_c = Employee.objects.create(
            organization=self.org_a, user=self.user_c, employee_code="C001"
        )

        # Permissions
        p_manage = Permission.objects.create(codename='document.manage_templates', resource='document', action='manage_templates')
        p_issue = Permission.objects.create(codename='document.issue', resource='document', action='issue')
        p_view_all = Permission.objects.create(codename='document.view_all', resource='document', action='view_all')

        role_a = Role.objects.create(organization=self.org_a, name="HR")
        RolePermission.objects.create(role=role_a, permission=p_manage)
        RolePermission.objects.create(role=role_a, permission=p_issue)
        RolePermission.objects.create(role=role_a, permission=p_view_all)
        UserRole.objects.create(user=self.user_a, role=role_a)
        
        role_b = Role.objects.create(organization=self.org_b, name="HR")
        RolePermission.objects.create(role=role_b, permission=p_manage)
        RolePermission.objects.create(role=role_b, permission=p_issue)
        RolePermission.objects.create(role=role_b, permission=p_view_all)
        UserRole.objects.create(user=self.user_b, role=role_b)

    def test_tenant_isolation_template_crud(self):
        self.client.force_authenticate(user=self.user_a)
        
        # Create Category
        res = self.client.post(reverse('document-category-list'), {'name': 'HR'})
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        cat_id = res.data['id']
        
        # Create Template
        res = self.client.post(reverse('document-template-list'), {
            'name': 'Welcome PDF',
            'template_type': 'pdf',
            'category': cat_id
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        template_id = res.data['id']

        # Add Version
        res = self.client.post(reverse('document-template-add-version', args=[template_id]), {
            'version_number': 1,
            'subject': 'Welcome to {{ employee.first_name }}',
            'body': '<h1>Welcome {{ employee.first_name }} {{ employee.last_name }}</h1>',
            'is_published': True
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        
        # Authenticate as User B
        self.client.force_authenticate(user=self.user_b)
        
        # Should not see User A's templates
        res = self.client.get(reverse('document-template-list'))
        self.assertEqual(len(res.data), 0)
        
        # Should not be able to fetch User A's template directly
        res = self.client.get(reverse('document-template-detail', args=[template_id]))
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_pdf_generation_and_vault(self):
        self.client.force_authenticate(user=self.user_a)
        
        # Create Template and Version
        cat = DocumentCategory.objects.create(organization=self.org_a, name='Letters')
        template = DocumentTemplate.objects.create(
            organization=self.org_a, name='Offer', template_type=TemplateType.PDF, category=cat
        )
        version = template.versions.create(
            version_number=1,
            body="<b>Hello {{ employee.first_name }}</b>",
            is_published=True
        )
        
        # Generate PDF Document
        res = self.client.post(reverse('issued-document-generate'), {
            'template_id': template.id,
            'employee_id': self.employee_a.id
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data['file_attachment'])
        self.assertIn('.pdf', res.data['file_attachment'])
        
        # Vault listing
        res = self.client.get(reverse('issued-document-list'))
        self.assertEqual(len(res.data), 1)

    def test_versioning_and_historical_reproducibility(self):
        """
        Verify: Template Version 1 -> generate issued doc -> add Version 2 (active) ->
        previously issued doc remains unchanged and references Version 1.
        """
        self.client.force_authenticate(user=self.user_a)
        
        template = DocumentTemplate.objects.create(
            organization=self.org_a, name='Policy Letter', template_type=TemplateType.EMAIL
        )
        v1 = template.versions.create(
            version_number=1,
            subject="Policy v1",
            body="<p>Version 1 Terms for {{ employee.first_name }}</p>",
            is_published=True
        )

        # Issue document with Version 1
        res = self.client.post(reverse('issued-document-generate'), {
            'template_id': template.id,
            'employee_id': self.employee_a.id
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        doc_id = res.data['id']
        issued_doc = IssuedDocument.objects.get(id=doc_id)
        self.assertEqual(issued_doc.template_version, v1)
        self.assertIn("Version 1 Terms for Admin", issued_doc.body_snapshot)
        saved_body_snapshot = issued_doc.body_snapshot

        # Now add and activate Version 2
        res_v2 = self.client.post(reverse('document-template-add-version', args=[template.id]), {
            'subject': 'Policy v2',
            'body': '<p>Version 2 Updated Terms for {{ employee.first_name }}</p>',
            'is_published': True
        })
        self.assertEqual(res_v2.status_code, status.HTTP_201_CREATED)
        v2_id = res_v2.data['id']

        # Verify old issued document remains completely unchanged!
        issued_doc.refresh_from_db()
        self.assertEqual(issued_doc.template_version_id, v1.id)
        self.assertEqual(issued_doc.body_snapshot, saved_body_snapshot)
        self.assertNotIn("Version 2", issued_doc.body_snapshot)

    def test_tenant_isolation_issued_documents_and_cross_org_idor(self):
        """
        Verify: Organization A cannot see Organization B issued documents.
        Cross-tenant generation targeting Org B template/employee from Org A is blocked.
        """
        # Create Org B template and document
        template_b = DocumentTemplate.objects.create(
            organization=self.org_b, name='Org B Secret Doc', template_type=TemplateType.EMAIL
        )
        v_b = template_b.versions.create(version_number=1, body="Top Secret", is_published=True)
        doc_b = IssuedDocument.objects.create(
            organization=self.org_b,
            employee=self.employee_b,
            template_version=v_b,
            document_type=TemplateType.EMAIL,
            title="Secret",
            body_snapshot="Org B confidential"
        )

        # Authenticate as Org A
        self.client.force_authenticate(user=self.user_a)

        # 1. Org A user listing vault cannot see Org B document
        res = self.client.get(reverse('issued-document-list'))
        self.assertEqual(len(res.data), 0)

        # 2. Org A user cannot retrieve Org B document directly by ID
        res = self.client.get(reverse('issued-document-detail', args=[doc_b.id]))
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

        # 3. Org A user cannot generate document using Org B's template ID (IDOR)
        res = self.client.post(reverse('issued-document-generate'), {
            'template_id': template_b.id,
            'employee_id': self.employee_a.id
        })
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

        # 4. Org A user cannot generate document targeting Org B's employee ID
        template_a = DocumentTemplate.objects.create(
            organization=self.org_a, name='Org A Doc', template_type=TemplateType.EMAIL
        )
        template_a.versions.create(version_number=1, body="Hi", is_published=True)
        res = self.client.post(reverse('issued-document-generate'), {
            'template_id': template_a.id,
            'employee_id': self.employee_b.id
        })
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_email_template_generation_and_candidate_targeting(self):
        """
        Verify: TemplateType.EMAIL works through the real API, and candidate targeting works.
        """
        self.client.force_authenticate(user=self.user_a)

        candidate = Candidate.objects.create(
            organization=self.org_a,
            first_name="Candidate",
            last_name="Jane",
            email="candidate.jane@example.com"
        )

        template = DocumentTemplate.objects.create(
            organization=self.org_a, name='Welcome Email', template_type=TemplateType.EMAIL
        )
        template.versions.create(
            version_number=1,
            subject="Welcome!",
            body="<p>Dear {{ candidate.full_name }}, welcome to the onboarding process.</p>",
            is_published=True
        )

        res = self.client.post(reverse('issued-document-generate'), {
            'template_id': template.id,
            'candidate_id': candidate.id
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['document_type'], 'email')
        self.assertIn("Dear Candidate Jane, welcome", res.data['body_snapshot'])
        self.assertEqual(res.data['candidate_name'], "Candidate Jane")

    def test_preview_and_syntax_error_handling(self):
        """
        Verify: preview renders expected context, and malformed template syntax returns HTTP 400.
        """
        self.client.force_authenticate(user=self.user_a)

        template = DocumentTemplate.objects.create(
            organization=self.org_a, name='Syntax Test', template_type=TemplateType.EMAIL
        )
        v1 = template.versions.create(
            version_number=1,
            body="Hello {{ employee.first_name }}",
            is_published=True
        )

        # 1. Normal preview
        res = self.client.post(reverse('document-template-preview', args=[template.id]), {
            'context_data': {'employee': {'first_name': 'Alice'}}
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['html'], 'Hello Alice')

        # 2. Malformed syntax error handling
        v_bad = template.versions.create(
            version_number=2,
            body="Hello {% if unclosed_tag %} broken",
            is_published=False
        )
        res = self.client.post(reverse('document-template-preview', args=[template.id]), {
            'version_id': v_bad.id,
            'context_data': {}
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Template rendering error', res.data['detail'])

    def test_activate_version(self):
        """
        Verify: activate_version sets target version to is_published=True and unpublishes other versions.
        """
        self.client.force_authenticate(user=self.user_a)

        template = DocumentTemplate.objects.create(
            organization=self.org_a, name='Multi Version', template_type=TemplateType.PDF
        )
        v1 = template.versions.create(version_number=1, body="v1", is_published=True)
        v2 = template.versions.create(version_number=2, body="v2", is_published=False)

        res = self.client.post(reverse('document-template-activate-version', args=[template.id]), {
            'version_id': v2.id
        })
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        v1.refresh_from_db()
        v2.refresh_from_db()
        self.assertFalse(v1.is_published)
        self.assertTrue(v2.is_published)

    def test_vault_self_service_filtering(self):
        """
        Verify: User without document.view_all can ONLY see their own documents in the Vault.
        """
        # Create doc for user A and doc for user C
        template = DocumentTemplate.objects.create(
            organization=self.org_a, name='Notice', template_type=TemplateType.EMAIL
        )
        v1 = template.versions.create(version_number=1, body="Notice", is_published=True)
        
        doc_a = IssuedDocument.objects.create(
            organization=self.org_a, employee=self.employee_a, template_version=v1,
            document_type=TemplateType.EMAIL, title="Notice A", body_snapshot="Notice A"
        )
        doc_c = IssuedDocument.objects.create(
            organization=self.org_a, employee=self.employee_c, template_version=v1,
            document_type=TemplateType.EMAIL, title="Notice C", body_snapshot="Notice C"
        )

        # User C (standard employee, no view_all permission)
        self.client.force_authenticate(user=self.user_c)
        res = self.client.get(reverse('issued-document-list'))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['id'], doc_c.id)

        # User A (HR manager with view_all permission) sees all org documents
        self.client.force_authenticate(user=self.user_a)
        res = self.client.get(reverse('issued-document-list'))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 2)

    def test_rbac_denial(self):
        # User C without permissions cannot generate documents
        self.client.force_authenticate(user=self.user_c)
        
        res = self.client.post(reverse('issued-document-generate'), {
            'template_id': 999,
            'employee_id': self.employee_c.id
        })
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
