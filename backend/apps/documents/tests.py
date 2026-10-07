from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from apps.organization.models import Organization
from apps.authorization.models import Role, Permission, RolePermission, UserRole
from apps.documents.models import DocumentCategory, DocumentTemplate, TemplateType, IssuedDocument
from apps.employees.models import Employee

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

    def test_rbac_denial(self):
        # Create user without permissions
        user_c = User.objects.create_user(email="user_c@test.com", password="pwd", first_name="C", last_name="C", status='active')
        employee_c = Employee.objects.create(
            organization=self.org_a, user=user_c, employee_code="C001"
        )
        
        self.client.force_authenticate(user=user_c)
        
        res = self.client.post(reverse('issued-document-generate'), {
            'template_id': 999,
            'employee_id': employee_c.id
        })
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
