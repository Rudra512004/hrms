"""
Employee Document Management — Comprehensive Test Suite (16 scenarios)
"""
import io
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import User
from apps.organization.models import Organization, OfficeNetwork
from apps.employees.models import Employee, EmployeeDocument, EmploymentStatus
from apps.audit.models import AuditLog


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def make_user(email, first_name='Test', last_name='User', is_superuser=False):
    user = User.objects.create_user(email=email, first_name=first_name, last_name=last_name)
    user.status = 'active'
    if is_superuser:
        user.is_superuser = True
    user.save()
    return user


def make_employee(user, org, code):
    return Employee.objects.create(
        user=user,
        organization=org,
        employee_code=code,
        employment_status=EmploymentStatus.ACTIVE,
    )


def make_pdf(name='test.pdf', size=1024):
    content = b'%PDF-1.4 fake content' + b'A' * max(0, size - 20)
    return SimpleUploadedFile(name, content, content_type='application/pdf')


def make_token(user):
    from rest_framework.authtoken.models import Token
    token, _ = Token.objects.get_or_create(user=user)
    return token.key


def auth_client(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Token {make_token(user)}')
    return client


def grant_permission(user, codename):
    from apps.authorization.models import Permission, Role, RolePermission, UserRole
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


LIST_URL = '/api/v1/employees/documents/'
DETAIL_URL = lambda pk: f'/api/v1/employees/documents/{pk}/'
DOWNLOAD_URL = lambda pk: f'/api/v1/employees/documents/{pk}/download/'


# ──────────────────────────────────────────────────────────────────────────────
# Test Class
# ──────────────────────────────────────────────────────────────────────────────

class EmployeeDocumentTests(TestCase):

    def setUp(self):
        self.org_a = Organization.objects.create(name='Org A Doc', status='active')
        self.org_b = Organization.objects.create(name='Org B Doc', status='active')

        # Allow 127.0.0.0/8 so test client passes IsNetworkAllowed
        OfficeNetwork.objects.create(
            organization=self.org_a,
            name='Localhost',
            network='127.0.0.0/8',
            is_active=True
        )

        self.hr_user = make_user('hr@doctest.local', 'HR', 'User')
        self.hr_emp = make_employee(self.hr_user, self.org_a, 'DOCTEST001')

        self.emp_user = make_user('emp@doctest.local', 'Emp', 'User')
        self.emp = make_employee(self.emp_user, self.org_a, 'DOCTEST002')

        self.emp_b_user = make_user('empb@doctest.local', 'EmpB', 'User')
        self.emp_b = make_employee(self.emp_b_user, self.org_b, 'DOCTEST003')

        self.superuser = make_user('super@doctest.local', 'Super', 'Admin', is_superuser=True)
        self.super_emp = make_employee(self.superuser, self.org_a, 'DOCTEST004')

        grant_permission(self.hr_user, 'employee.document.view')
        grant_permission(self.hr_user, 'employee.document.upload')
        grant_permission(self.hr_user, 'employee.document.delete')

        self.existing_doc = EmployeeDocument.objects.create(
            employee=self.emp,
            document_type='identity',
            document_name='pre_existing.pdf',
            file=SimpleUploadedFile('pre_existing.pdf', b'%PDF-pre', content_type='application/pdf'),
            file_size=8,
            mime_type='application/pdf',
            uploaded_by=self.hr_user,
        )

    def test_01_authorized_upload_succeeds(self):
        client = auth_client(self.hr_user)
        pdf = make_pdf('resume.pdf')
        data = {'employee': self.emp.id, 'document_type': 'employment', 'document_name': 'Resume', 'file': pdf}
        response = client.post(LIST_URL, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['document_name'], 'Resume')

    def test_02_unauthorized_upload_returns_403(self):
        client = auth_client(self.emp_user)
        pdf = make_pdf()
        data = {'employee': self.emp.id, 'document_type': 'other', 'file': pdf}
        response = client.post(LIST_URL, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_03_cross_org_upload_rejected(self):
        client = auth_client(self.hr_user)
        pdf = make_pdf()
        data = {'employee': self.emp_b.id, 'document_type': 'other', 'file': pdf}
        response = client.post(LIST_URL, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_04_idor_cross_org_retrieve_returns_404(self):
        doc_b = EmployeeDocument.objects.create(
            employee=self.emp_b,
            document_type='other',
            document_name='orgb_doc.pdf',
            file=SimpleUploadedFile('orgb_doc.pdf', b'%PDF-b', content_type='application/pdf'),
            file_size=6,
            uploaded_by=self.emp_b_user,
        )
        client = auth_client(self.hr_user)
        response = client.get(DETAIL_URL(doc_b.id))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_05_idor_list_isolation(self):
        doc_b = EmployeeDocument.objects.create(
            employee=self.emp_b,
            document_type='other',
            document_name='orgb_secret.pdf',
            file=SimpleUploadedFile('orgb_secret.pdf', b'%PDF-b', content_type='application/pdf'),
            file_size=6,
            uploaded_by=self.emp_b_user,
        )
        client = auth_client(self.hr_user)
        response = client.get(LIST_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_ids = [d['id'] for d in response.data]
        self.assertNotIn(doc_b.id, returned_ids)

    def test_06_employee_can_retrieve_own_document(self):
        client = auth_client(self.emp_user)
        response = client.get(DETAIL_URL(self.existing_doc.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.existing_doc.id)

    def test_07_disallowed_extension_rejected(self):
        client = auth_client(self.hr_user)
        txt_file = SimpleUploadedFile('notes.txt', b'some text', content_type='text/plain')
        data = {'employee': self.emp.id, 'document_type': 'other', 'file': txt_file}
        response = client.post(LIST_URL, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_08_oversized_file_rejected(self):
        client = auth_client(self.hr_user)
        large_pdf = SimpleUploadedFile(
            'large.pdf', b'%PDF-' + b'X' * (5 * 1024 * 1024 + 1), content_type='application/pdf'
        )
        data = {'employee': self.emp.id, 'document_type': 'other', 'file': large_pdf}
        response = client.post(LIST_URL, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_09_dangerous_extensions_rejected(self):
        client = auth_client(self.hr_user)
        for ext in ['.exe', '.sh', '.bat', '.py', '.js', '.php']:
            dangerous = SimpleUploadedFile(f'evil{ext}', b'evil', content_type='application/octet-stream')
            data = {'employee': self.emp.id, 'document_type': 'other', 'file': dangerous}
            response = client.post(LIST_URL, data, format='multipart')
            self.assertEqual(
                response.status_code, status.HTTP_400_BAD_REQUEST,
                f"Expected 400 for '{ext}', got {response.status_code}"
            )

    def test_10_filename_sanitization(self):
        client = auth_client(self.hr_user)
        pdf = make_pdf()
        data = {
            'employee': self.emp.id,
            'document_type': 'other',
            'document_name': '../../../etc/passwd',
            'file': pdf,
        }
        response = client.post(LIST_URL, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        returned_name = response.data['document_name']
        self.assertNotIn('..', returned_name)
        self.assertNotIn('/', returned_name)

    def test_11_delete_permission_enforced(self):
        client = auth_client(self.emp_user)
        response = client.delete(DETAIL_URL(self.existing_doc.id))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(EmployeeDocument.objects.filter(id=self.existing_doc.id).exists())

    def test_12_deleted_document_returns_404(self):
        doc = EmployeeDocument.objects.create(
            employee=self.emp,
            document_type='other',
            document_name='disposable.pdf',
            file=SimpleUploadedFile('disposable.pdf', b'%PDF-disp', content_type='application/pdf'),
            file_size=9,
            uploaded_by=self.hr_user,
        )
        doc_id = doc.id
        client = auth_client(self.hr_user)
        response = client.delete(DETAIL_URL(doc_id))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        response = client.get(DETAIL_URL(doc_id))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_13_exited_employee_retains_documents(self):
        self.emp.employment_status = EmploymentStatus.EXITED
        self.emp.save()
        client = auth_client(self.hr_user)
        response = client.get(DETAIL_URL(self.existing_doc.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_14_unauthenticated_access_blocked(self):
        client = APIClient()
        response = client.get(LIST_URL)
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_15_audit_log_generated_on_upload_and_delete(self):
        client = auth_client(self.hr_user)
        before_upload = AuditLog.objects.filter(action='employee_document_uploaded').count()
        pdf = make_pdf('audit_test.pdf')
        data = {'employee': self.emp.id, 'document_type': 'other', 'file': pdf}
        response = client.post(LIST_URL, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        doc_id = response.data['id']
        self.assertEqual(AuditLog.objects.filter(action='employee_document_uploaded').count(), before_upload + 1)

        before_delete = AuditLog.objects.filter(action='employee_document_deleted').count()
        client.delete(DETAIL_URL(doc_id))
        self.assertEqual(AuditLog.objects.filter(action='employee_document_deleted').count(), before_delete + 1)

    def test_16_organization_isolation_queryset(self):
        doc_b = EmployeeDocument.objects.create(
            employee=self.emp_b,
            document_type='other',
            document_name='orgb_only.pdf',
            file=SimpleUploadedFile('orgb_only.pdf', b'%PDF-b2', content_type='application/pdf'),
            file_size=7,
            uploaded_by=self.emp_b_user,
        )
        client = auth_client(self.hr_user)
        response = client.get(LIST_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [d['id'] for d in response.data]
        self.assertIn(self.existing_doc.id, ids)
        self.assertNotIn(doc_b.id, ids)

    def test_17_download_authorized_and_private(self):
        client = auth_client(self.hr_user)
        response = client.get(DOWNLOAD_URL(self.existing_doc.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment', response.get('Content-Disposition', ''))

    def test_18_download_cross_org_returns_404(self):
        doc_b = EmployeeDocument.objects.create(
            employee=self.emp_b,
            document_type='other',
            document_name='orgb_doc.pdf',
            file=SimpleUploadedFile('orgb_doc.pdf', b'%PDF-b', content_type='application/pdf'),
            file_size=6,
            uploaded_by=self.emp_b_user,
        )
        client = auth_client(self.hr_user)
        response = client.get(DOWNLOAD_URL(doc_b.id))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_19_preview_authorized(self):
        client = auth_client(self.hr_user)
        preview_url = f'/api/v1/employees/documents/{self.existing_doc.id}/preview/'
        response = client.get(preview_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('inline', response.get('Content-Disposition', ''))

    def test_20_download_unauthorized_returns_403(self):
        # Create doc for another employee in org A
        other_user = make_user('other@doctest.local', 'Other', 'User')
        other_emp = make_employee(other_user, self.org_a, 'DOCTEST005')
        other_doc = EmployeeDocument.objects.create(
            employee=other_emp,
            document_type='other',
            document_name='other.pdf',
            file=SimpleUploadedFile('other.pdf', b'%PDF-other', content_type='application/pdf'),
            file_size=10,
            uploaded_by=self.hr_user,
        )
        client = auth_client(self.emp_user)  # emp_user does not own other_doc and has no employee.document.view
        response = client.get(DOWNLOAD_URL(other_doc.id))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
