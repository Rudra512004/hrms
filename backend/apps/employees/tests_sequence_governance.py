import concurrent.futures
from django.test import TestCase, TransactionTestCase
from django.db import connection
from django.contrib.auth import get_user_model
from django.apps import apps

from apps.organization.models import Organization
from apps.employees.models import Employee, EmployeeIDSequence
from apps.employees.utils import generate_next_employee_code

User = get_user_model()


class EmployeeIDSequenceGovernanceTests(TestCase):
    """
    Exhaustive verification of Multi-Tenant Employee ID Sequence Governance:
    - Organization isolation
    - Initial sequence creation
    - Monotonic repeated allocation
    - No ID reuse on employee deletion
    - Error handling on missing organization context
    """

    def setUp(self):
        self.org_a = Organization.objects.create(name='Tenant Alpha', code='ALPHA')
        self.org_b = Organization.objects.create(name='Tenant Beta', code='BETA')

    def test_missing_organization_context_raises_value_error(self):
        """Organization context is strictly required."""
        with self.assertRaises(ValueError) as ctx:
            generate_next_employee_code(None)
        self.assertIn("Organization context is required", str(ctx.exception))

    def test_organization_isolation_independent_sequences(self):
        """Each tenant has its own isolated sequence counter."""
        code_a1 = generate_next_employee_code(self.org_a)
        code_a2 = generate_next_employee_code(self.org_a)

        # Tenant Beta generates independently without jumping or affecting Tenant Alpha
        code_b1 = generate_next_employee_code(self.org_b)
        code_b2 = generate_next_employee_code(self.org_b)

        self.assertEqual(code_a1, 'EMPBS001')
        self.assertEqual(code_a2, 'EMPBS002')
        self.assertEqual(code_b1, 'EMPBS001')
        self.assertEqual(code_b2, 'EMPBS002')

        seq_a = EmployeeIDSequence.objects.get(organization=self.org_a)
        seq_b = EmployeeIDSequence.objects.get(organization=self.org_b)
        self.assertEqual(seq_a.last_generated, 2)
        self.assertEqual(seq_b.last_generated, 2)

    def test_initial_sequence_creation_when_no_record_exists(self):
        """An organization without an existing sequence creates one starting at 1."""
        org_c = Organization.objects.create(name='Tenant Gamma', code='GAMMA')
        self.assertFalse(EmployeeIDSequence.objects.filter(organization=org_c).exists())

        code = generate_next_employee_code(org_c)
        self.assertEqual(code, 'EMPBS001')
        self.assertTrue(EmployeeIDSequence.objects.filter(organization=org_c).exists())
        self.assertEqual(EmployeeIDSequence.objects.get(organization=org_c).last_generated, 1)

    def test_monotonic_repeated_allocation(self):
        """Repeated calls produce sequential IDs."""
        codes = [generate_next_employee_code(self.org_a) for _ in range(5)]
        self.assertEqual(codes, ['EMPBS001', 'EMPBS002', 'EMPBS003', 'EMPBS004', 'EMPBS005'])
        self.assertEqual(EmployeeIDSequence.objects.get(organization=self.org_a).last_generated, 5)

    def test_no_code_reuse_after_employee_deletion(self):
        """Monotonic sequence counter prevents reusing deleted employee codes."""
        code1 = generate_next_employee_code(self.org_a)
        user1 = User.objects.create_user(email='user1@alpha.com')
        emp1 = Employee.objects.create(user=user1, organization=self.org_a, employee_code=code1)

        code2 = generate_next_employee_code(self.org_a)
        user2 = User.objects.create_user(email='user2@alpha.com')
        emp2 = Employee.objects.create(user=user2, organization=self.org_a, employee_code=code2)

        self.assertEqual(code1, 'EMPBS001')
        self.assertEqual(code2, 'EMPBS002')

        # Delete emp2
        emp2.delete()

        # Next code must be EMPBS003, not EMPBS002
        code3 = generate_next_employee_code(self.org_a)
        self.assertEqual(code3, 'EMPBS003')

    def test_custom_prefix_support(self):
        """Prefixes can be configured per tenant or workflow."""
        code = generate_next_employee_code(self.org_a, prefix='ALPHA')
        self.assertEqual(code, 'ALPHA001')

    def test_orphaned_employee_code_preserved_and_prevents_duplicate_allocation(self):
        """
        Orphaned legacy employees (organization=None) have their codes preserved
        and are never arbitrarily assigned to any organization.
        New sequence allocations strictly account for orphaned codes to prevent duplicates.
        """
        orphaned_user = User.objects.create_user(email='orphaned@legacy.com')
        orphaned_emp = Employee.objects.create(
            user=orphaned_user,
            organization=None,
            employee_code='EMPBS007'
        )

        # Generating code for org_a must skip past EMPBS007 to avoid collision
        next_code = generate_next_employee_code(self.org_a)
        self.assertEqual(next_code, 'EMPBS008')

        # Verify orphaned employee remains unassigned and preserved
        orphaned_emp.refresh_from_db()
        self.assertIsNone(orphaned_emp.organization)
        self.assertEqual(orphaned_emp.employee_code, 'EMPBS007')

    def test_employee_clean_rejects_duplicate_of_orphaned_code(self):
        """Employee.clean() rejects assigning a code matching an unassigned legacy employee."""
        orphaned_user = User.objects.create_user(email='orphaned_clean@legacy.com')
        Employee.objects.create(
            user=orphaned_user,
            organization=None,
            employee_code='EMPBS020'
        )

        from django.core.exceptions import ValidationError
        new_user = User.objects.create_user(email='new_clean@alpha.com')
        new_emp = Employee(
            user=new_user,
            organization=self.org_a,
            employee_code='EMPBS020'
        )
        with self.assertRaises(ValidationError) as ctx:
            new_emp.clean()
        self.assertIn('employee_code', ctx.exception.message_dict)

    def test_migration_0017_backfill_accounts_for_orphaned_employees(self):
        """Migration 0017 backfill accounts for orphaned legacy employee codes."""
        import importlib
        migration_0017 = importlib.import_module('apps.employees.migrations.0017_employeeidsequence_organization')
        backfill_employee_id_sequences = migration_0017.backfill_employee_id_sequences

        # Clear existing sequence records for this test
        EmployeeIDSequence.objects.all().delete()

        # Create an orphaned employee
        orphaned_user = User.objects.create_user(email='mig_orphaned@legacy.com')
        orphaned_emp = Employee.objects.create(
            user=orphaned_user,
            organization=None,
            employee_code='EMPBS015'
        )

        # Run backfill
        backfill_employee_id_sequences(apps, None)

        # The orphaned employee remains unassigned
        orphaned_emp.refresh_from_db()
        self.assertIsNone(orphaned_emp.organization)

        # Next code generated by org_a must be EMPBS016 or higher
        code = generate_next_employee_code(self.org_a)
        self.assertEqual(code, 'EMPBS016')

    def test_migration_0017_rollback_safety_single_vs_multi_tenant(self):
        """
        Migration 0017 rollback:
        - Safely unassigns sequence row if only 1 sequence exists.
        - Strictly blocks reversal with RuntimeError if multiple tenant sequences exist.
        """
        import importlib
        migration_0017 = importlib.import_module('apps.employees.migrations.0017_employeeidsequence_organization')
        reverse_backfill = migration_0017.reverse_backfill

        # Ensure both org_a and org_b have sequences
        generate_next_employee_code(self.org_a)
        generate_next_employee_code(self.org_b)

        # Attempting rollback with multiple tenant sequences must raise RuntimeError
        with self.assertRaises(RuntimeError) as ctx:
            reverse_backfill(apps, None)
        self.assertIn("Cannot safely rollback migration 0017", str(ctx.exception))
        self.assertIn("protect tenant isolation", str(ctx.exception))

        # Delete org_b sequence so only 1 sequence remains
        EmployeeIDSequence.objects.filter(organization=self.org_b).delete()

        # Single tenant rollback succeeds and unassigns organization
        reverse_backfill(apps, None)
        seq_a = EmployeeIDSequence.objects.get(id=EmployeeIDSequence.objects.first().id)
        self.assertIsNone(seq_a.organization)

    def test_employee_clean_rejects_duplicate_within_same_org(self):
        """Employee.clean() rejects duplicate employee code within the same organization."""
        from django.core.exceptions import ValidationError
        user1 = User.objects.create_user(email='existing_emp@alpha.com')
        Employee.objects.create(
            user=user1,
            organization=self.org_a,
            employee_code='EMPBS001'
        )

        user2 = User.objects.create_user(email='dup_emp@alpha.com')
        dup_emp = Employee(
            user=user2,
            organization=self.org_a,
            employee_code='EMPBS001'
        )
        with self.assertRaises(ValidationError) as ctx:
            dup_emp.clean()
        self.assertIn('employee_code', ctx.exception.message_dict)
        self.assertIn('already exists in this organization', ctx.exception.message_dict['employee_code'][0])

    def test_orphaned_hyphenated_and_custom_prefix_backfill(self):
        """Migration 0017 backfill correctly parses hyphenated and punctuated employee codes."""
        import importlib
        migration_0017 = importlib.import_module('apps.employees.migrations.0017_employeeidsequence_organization')
        backfill_employee_id_sequences = migration_0017.backfill_employee_id_sequences

        EmployeeIDSequence.objects.all().delete()

        # Create an orphaned employee with a hyphenated prefix
        orphaned_user = User.objects.create_user(email='orphaned_hyphen@legacy.com')
        orphaned_emp = Employee.objects.create(
            user=orphaned_user,
            organization=None,
            employee_code='EMP-A-010'
        )

        # Create an existing employee in org_a with the matching hyphenated prefix
        user_a = User.objects.create_user(email='user_a_hyphen@alpha.com')
        Employee.objects.create(
            user=user_a,
            organization=self.org_a,
            employee_code='EMP-A-002'
        )

        # Run backfill
        backfill_employee_id_sequences(apps, None)

        seq_a = EmployeeIDSequence.objects.get(organization=self.org_a)
        self.assertGreaterEqual(seq_a.last_generated, 10)

        # Next generated code for org_a with prefix EMP-A- must be EMP-A-011
        next_code = generate_next_employee_code(self.org_a, prefix='EMP-A-')
        self.assertEqual(next_code, 'EMP-A-011')

    def test_orphaned_codes_across_multiple_prefixes_and_tenants(self):
        """
        In multi-tenant setups, orphaned codes for a specific prefix do not corrupt
        the sequence of an unrelated organization using a different prefix.
        """
        import importlib
        migration_0017 = importlib.import_module('apps.employees.migrations.0017_employeeidsequence_organization')
        backfill_employee_id_sequences = migration_0017.backfill_employee_id_sequences

        EmployeeIDSequence.objects.all().delete()

        # Orphaned employee with prefix CORP
        orphaned_user = User.objects.create_user(email='orphaned_corp@legacy.com')
        Employee.objects.create(
            user=orphaned_user,
            organization=None,
            employee_code='CORP050'
        )

        # Org B already has employee with prefix EMPBS
        user_b = User.objects.create_user(email='user_b_empbs@beta.com')
        Employee.objects.create(
            user=user_b,
            organization=self.org_b,
            employee_code='EMPBS002'
        )

        # Run backfill
        backfill_employee_id_sequences(apps, None)

        seq_b = EmployeeIDSequence.objects.get(organization=self.org_b)
        # Org B should be at 2, not jumped to 50 because it does not use CORP
        self.assertEqual(seq_b.last_generated, 2)

    def test_rollback_atomicity_with_extra_unassigned_sequence_record(self):
        """
        Rollback is blocked if multiple sequence records exist in total,
        even if only one has organization set.
        """
        import importlib
        migration_0017 = importlib.import_module('apps.employees.migrations.0017_employeeidsequence_organization')
        reverse_backfill = migration_0017.reverse_backfill

        EmployeeIDSequence.objects.all().delete()
        # 1 active sequence and 1 unassigned sequence row
        EmployeeIDSequence.objects.create(organization=self.org_a, last_generated=5)
        EmployeeIDSequence.objects.create(organization=None, last_generated=10)

        with self.assertRaises(RuntimeError) as ctx:
            reverse_backfill(apps, None)
        self.assertIn("Cannot safely rollback migration 0017", str(ctx.exception))
        self.assertIn("total", str(ctx.exception))

    def test_database_enforces_unique_together_on_bulk_create_bypassing_clean(self):
        """
        Database-level UNIQUE constraint ('organization', 'employee_code')
        rejects duplicates even when model.clean() is bypassed via bulk_create.
        """
        from django.db import IntegrityError
        user1 = User.objects.create_user(email='bulk1@alpha.com')
        user2 = User.objects.create_user(email='bulk2@alpha.com')

        emp1 = Employee(user=user1, organization=self.org_a, employee_code='EMPBS100')
        emp2 = Employee(user=user2, organization=self.org_a, employee_code='EMPBS100')

        with self.assertRaises(IntegrityError):
            Employee.objects.bulk_create([emp1, emp2])

    def test_database_enforces_unique_together_on_update_bypassing_clean(self):
        """
        Database-level UNIQUE constraint ('organization', 'employee_code')
        rejects duplicates when updating a record directly via QuerySet.update().
        """
        from django.db import IntegrityError
        user1 = User.objects.create_user(email='upd1@alpha.com')
        user2 = User.objects.create_user(email='upd2@alpha.com')

        Employee.objects.create(user=user1, organization=self.org_a, employee_code='EMPBS101')
        emp2 = Employee.objects.create(user=user2, organization=self.org_a, employee_code='EMPBS102')

        with self.assertRaises(IntegrityError):
            Employee.objects.filter(pk=emp2.pk).update(employee_code='EMPBS101')


class EmployeeIDSequenceConcurrencyTests(TransactionTestCase):
    """
    Validates concurrency safety:
    Simulates concurrent database connections allocating employee codes
    simultaneously within the same organization.
    """

    def setUp(self):
        self.org = Organization.objects.create(name='Concurrent Org', code='CONC')

    def tearDown(self):
        from django.db import connections
        connections.close_all()
        super().tearDown()

    def test_concurrent_allocation_produces_unique_codes(self):
        num_threads = 5

        def allocate():
            from django.db import connection
            try:
                return generate_next_employee_code(self.org)
            finally:
                connection.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(allocate) for _ in range(num_threads)]
            results = [f.result() for f in futures]

        from django.db import connections
        connections.close_all()

        # All generated codes must be strictly unique
        self.assertEqual(len(results), num_threads)
        self.assertEqual(len(set(results)), num_threads, f"Duplicate codes detected: {results}")

        # The sequence must have advanced by exactly num_threads
        seq = EmployeeIDSequence.objects.get(organization=self.org)
        self.assertEqual(seq.last_generated, num_threads)
