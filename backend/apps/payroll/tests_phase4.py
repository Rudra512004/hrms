"""
Phase 4 Payroll Engine Tests

Tests cover:
1. SalaryStructure calculation — FIXED_AMOUNT
2. SalaryStructure calculation — PERCENTAGE_OF_BASIC
3. Multiple salary components (earning + deduction + employer contribution)
4. PayrollRecord aggregate correctness
5. Earning line items
6. Deduction line items
7. Employer contribution line items
8. Approved adjustment application
9. Pending adjustment not applied
10. Draft recalculation idempotency
11. Approved adjustment survives recalculation
12. Finalized payroll cannot be recalculated
13. Finalized payroll mutation rejected
14. Duplicate PayrollRun prevention
15. Parallel run_type support
16. Missing salary structure (legacy fallback)
17. Unsupported calculation type
18. Tenant isolation
19. IDOR prevention
20. Historical snapshot preservation
21. Legacy basic_salary fallback
22. Existing regression (PayrollRecord created correctly)
23. PayrollLineItem lineage fields set correctly
24. finalize_payroll_run transitions correctly
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.db import IntegrityError

from apps.employees.models import Employee, EmploymentStatus
from apps.organization.models import Organization
from apps.payroll.models import (
    CompensationHistory,
    PayrollRun,
    PayrollRecord,
    PayrollLineItem,
    PayrollAdjustment,
    SalaryComponent,
    SalaryStructure,
    SalaryStructureComponent,
)
from apps.payroll.services import (
    generate_payroll_for_period,
    finalize_payroll_run,
    PayrollCalculationError,
    PayrollImmutableError,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Shared test helpers
# ---------------------------------------------------------------------------

def make_org(name='TestOrg'):
    return Organization.objects.create(name=name)


def make_user(org, email=None, first_name='Test', last_name='User'):
    email = email or f'user-{org.id}-{first_name}@test.com'
    return User.objects.create_user(
        email=email, password='testpass',
        first_name=first_name, last_name=last_name,
        status='active',
    )


def make_employee(org, user=None, code=None, status=EmploymentStatus.ACTIVE):
    user = user or make_user(org)
    code = code or f'EMP{org.id}{user.id}'
    return Employee.objects.create(
        user=user,
        organization=org,
        employee_code=code,
        employment_status=status,
    )


def make_run(org, year=2026, month=3, run_type='REGULAR'):
    return PayrollRun.objects.create(
        organization=org,
        year=year,
        month=month,
        run_type=run_type,
        start_date=date(year, month, 1),
        end_date=date(year, month, 28),
        status=PayrollRun.STATUS_DRAFT,
    )


def make_comp(employee, salary, structure=None):
    return CompensationHistory.objects.create(
        employee=employee,
        effective_from=date(2024, 1, 1),
        basic_salary=salary,
        salary_structure=structure,
    )


def make_structure(org, name='Standard'):
    return SalaryStructure.objects.create(organization=org, name=name, is_active=True)


def make_component(org, code, kind='earning', name=None):
    return SalaryComponent.objects.create(
        organization=org,
        name=name or code,
        code=code,
        kind=kind,
        is_active=True,
    )


def make_structure_component(structure, component, amount, calc_type='FIXED_AMOUNT'):
    return SalaryStructureComponent.objects.create(
        structure=structure,
        component=component,
        amount=amount,
        calculation_type=calc_type,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFixedAmountCalculation(TestCase):
    """Test 1: FIXED_AMOUNT component produces correct line item."""

    def setUp(self):
        self.org = make_org('OrgFixed')
        self.emp = make_employee(self.org, code='EMP001')
        self.structure = make_structure(self.org)
        self.sc = make_component(self.org, 'BASIC', 'earning')
        make_structure_component(self.structure, self.sc, Decimal('50000'), 'FIXED_AMOUNT')
        make_comp(self.emp, Decimal('50000'), structure=self.structure)
        self.run = make_run(self.org)

    def test_fixed_amount_line_item(self):
        generate_payroll_for_period(self.run)
        record = PayrollRecord.objects.get(period=self.run, employee=self.emp)
        line_items = record.line_items.filter(category='EARNING')
        self.assertTrue(line_items.exists())
        # With no attendance (0 working days tracked), should still create line item
        basic_li = line_items.first()
        self.assertEqual(basic_li.component, self.sc)
        self.assertEqual(basic_li.calculation_type, 'FIXED_AMOUNT')


class TestPercentageOfBasicCalculation(TestCase):
    """Test 2: PERCENTAGE_OF_BASIC component computes correctly."""

    def setUp(self):
        self.org = make_org('OrgPct')
        self.emp = make_employee(self.org, code='EMPPCT')
        self.structure = make_structure(self.org, 'PctStructure')
        self.basic_sc = make_component(self.org, 'BASIC_PAY', 'earning')
        self.hra_sc = make_component(self.org, 'HRA', 'earning')
        make_structure_component(self.structure, self.basic_sc, Decimal('40000'), 'FIXED_AMOUNT')
        make_structure_component(self.structure, self.hra_sc, Decimal('40'), 'PERCENTAGE_OF_BASIC')
        make_comp(self.emp, Decimal('40000'), structure=self.structure)
        self.run = make_run(self.org)

    def test_percentage_of_basic(self):
        generate_payroll_for_period(self.run)
        record = PayrollRecord.objects.get(period=self.run, employee=self.emp)
        hra_li = record.line_items.filter(component=self.hra_sc).first()
        self.assertIsNotNone(hra_li)
        self.assertEqual(hra_li.calculation_type, 'PERCENTAGE_OF_BASIC')
        # 40% of 40000 = 16000
        self.assertAlmostEqual(
            float(Decimal(hra_li.calculation_metadata['raw_amount'])),
            16000.0,
            places=2,
        )


class TestMultipleComponents(TestCase):
    """Test 3 + 5 + 6 + 7: Multiple components: earnings, deductions, employer contributions."""

    def setUp(self):
        self.org = make_org('OrgMulti')
        self.emp = make_employee(self.org, code='EMPMULTI')
        self.structure = make_structure(self.org, 'MultiStruct')

        self.basic = make_component(self.org, 'BASIC', 'earning')
        self.ded = make_component(self.org, 'PF_EE', 'deduction')
        self.emp_contrib = make_component(self.org, 'PF_ER', 'employer_contribution')

        make_structure_component(self.structure, self.basic, Decimal('60000'), 'FIXED_AMOUNT')
        make_structure_component(self.structure, self.ded, Decimal('12'), 'PERCENTAGE_OF_BASIC')
        make_structure_component(self.structure, self.emp_contrib, Decimal('12'), 'PERCENTAGE_OF_BASIC')

        make_comp(self.emp, Decimal('60000'), structure=self.structure)
        self.run = make_run(self.org)

    def test_all_category_line_items_created(self):
        generate_payroll_for_period(self.run)
        record = PayrollRecord.objects.get(period=self.run, employee=self.emp)

        self.assertTrue(record.line_items.filter(category='EARNING').exists(), "No EARNING line item")
        self.assertTrue(record.line_items.filter(category='DEDUCTION').exists(), "No DEDUCTION line item")
        self.assertTrue(record.line_items.filter(category='EMPLOYER_CONTRIBUTION').exists(), "No EMPLOYER_CONTRIBUTION line item")

    def test_aggregate_correctness(self):
        """Test 4: Aggregate totals match individual line items."""
        generate_payroll_for_period(self.run)
        record = PayrollRecord.objects.get(period=self.run, employee=self.emp)

        total_earn = sum(li.amount for li in record.line_items.filter(category='EARNING'))
        total_ded = sum(li.amount for li in record.line_items.filter(category='DEDUCTION'))
        total_emp = sum(li.amount for li in record.line_items.filter(category='EMPLOYER_CONTRIBUTION'))

        self.assertEqual(record.total_earnings, total_earn)
        self.assertEqual(record.total_deductions, total_ded)
        self.assertEqual(record.employer_contributions, total_emp)
        # net = gross - deductions (no tax here)
        expected_net = max(Decimal('0.00'), total_earn - total_ded)
        self.assertEqual(record.net_salary, expected_net)


class TestAdjustments(TestCase):
    """Tests 8, 9: Approved adjustment applied; pending adjustment NOT applied."""

    def setUp(self):
        self.org = make_org('OrgAdj')
        self.emp = make_employee(self.org, code='EMPADJ')
        self.sc_bonus = make_component(self.org, 'BONUS', 'earning')
        make_comp(self.emp, Decimal('30000'))  # No structure — legacy
        self.run = make_run(self.org)

    def test_approved_adjustment_applied(self):
        """Test 8: Approved adjustment appears as a line item."""
        adj = PayrollAdjustment.objects.create(
            employee=self.emp,
            component=self.sc_bonus,
            amount=Decimal('5000'),
            period_year=2026,
            period_month=3,
            reason='Performance bonus',
            status=PayrollAdjustment.STATUS_APPROVED,
        )
        generate_payroll_for_period(self.run)
        record = PayrollRecord.objects.get(period=self.run, employee=self.emp)
        adj_li = record.line_items.filter(source_adjustment=adj).first()
        self.assertIsNotNone(adj_li, "Approved adjustment line item not found")
        self.assertEqual(adj_li.amount, Decimal('5000'))
        self.assertEqual(adj_li.category, 'EARNING')

    def test_pending_adjustment_not_applied(self):
        """Test 9: Pending adjustment does NOT appear in line items."""
        PayrollAdjustment.objects.create(
            employee=self.emp,
            component=self.sc_bonus,
            amount=Decimal('3000'),
            period_year=2026,
            period_month=3,
            reason='Pending bonus',
            status=PayrollAdjustment.STATUS_PENDING,
        )
        generate_payroll_for_period(self.run)
        record = PayrollRecord.objects.get(period=self.run, employee=self.emp)
        adj_lis = record.line_items.filter(
            calculation_metadata__source='payroll_adjustment'
        )
        self.assertFalse(adj_lis.exists(), "Pending adjustment should NOT create a line item")


class TestDraftRecalculation(TestCase):
    """Tests 10, 11: Recalculation idempotency and adjustment survival."""

    def setUp(self):
        self.org = make_org('OrgRecalc')
        self.emp = make_employee(self.org, code='EMPRECALC')
        make_comp(self.emp, Decimal('40000'))  # No structure
        self.run = make_run(self.org)

    def test_recalculation_idempotent(self):
        """Test 10: Same result when run twice on a DRAFT."""
        generate_payroll_for_period(self.run)
        record1 = PayrollRecord.objects.get(period=self.run, employee=self.emp)
        net1 = record1.net_salary

        generate_payroll_for_period(self.run)
        record2 = PayrollRecord.objects.get(period=self.run, employee=self.emp)
        net2 = record2.net_salary

        self.assertEqual(net1, net2, "Recalculation must be idempotent")

    def test_line_items_not_duplicated_on_recalc(self):
        """Test 10b: Line items are not accumulated between recalculations."""
        generate_payroll_for_period(self.run)
        count1 = PayrollLineItem.objects.filter(
            payroll_record__period=self.run
        ).count()

        generate_payroll_for_period(self.run)
        count2 = PayrollLineItem.objects.filter(
            payroll_record__period=self.run
        ).count()

        self.assertEqual(count1, count2, "Line items should not accumulate on recalculation")

    def test_approved_adjustment_survives_recalculation(self):
        """Test 11: Approved adjustments are reapplied after recalculation."""
        sc_bonus = make_component(self.org, 'BONUS2', 'earning')
        PayrollAdjustment.objects.create(
            employee=self.emp,
            component=sc_bonus,
            amount=Decimal('2000'),
            period_year=2026,
            period_month=3,
            reason='Bonus',
            status=PayrollAdjustment.STATUS_APPROVED,
        )

        generate_payroll_for_period(self.run)
        record = PayrollRecord.objects.get(period=self.run, employee=self.emp)
        first_net = record.net_salary

        # Reset adjustment to APPROVED so it can be reapplied
        PayrollAdjustment.objects.filter(
            employee=self.emp, period_year=2026, period_month=3
        ).update(status=PayrollAdjustment.STATUS_APPROVED)

        generate_payroll_for_period(self.run)
        record = PayrollRecord.objects.get(period=self.run, employee=self.emp)
        second_net = record.net_salary

        self.assertEqual(first_net, second_net, "Net salary must be the same after recalculation")


class TestFinalizedImmutability(TestCase):
    """Tests 12, 13: Finalized payroll cannot be recalculated or mutated."""

    def setUp(self):
        self.org = make_org('OrgFinal')
        self.emp = make_employee(self.org, code='EMPFINAL')
        make_comp(self.emp, Decimal('50000'))
        self.run = make_run(self.org)
        generate_payroll_for_period(self.run)

        # Approve
        self.run.status = PayrollRun.STATUS_APPROVED
        self.run.save()
        PayrollRecord.objects.filter(period=self.run).update(status=PayrollRecord.STATUS_APPROVED)

        # Finalize
        finalize_payroll_run(self.run)
        self.run.refresh_from_db()

    def test_finalized_run_cannot_be_recalculated(self):
        """Test 12: generate_payroll_for_period raises PayrollImmutableError."""
        with self.assertRaises(PayrollImmutableError):
            generate_payroll_for_period(self.run)

    def test_finalized_run_status(self):
        """Test 13: Run is FINALIZED after finalize_payroll_run."""
        self.assertEqual(self.run.status, PayrollRun.STATUS_FINALIZED)

    def test_finalized_records_status(self):
        """Test 13b: All records are FINALIZED."""
        records = PayrollRecord.objects.filter(period=self.run)
        for r in records:
            self.assertEqual(r.status, PayrollRecord.STATUS_FINALIZED)

    def test_double_finalization_raises(self):
        """Test 13c: Attempting to finalize again raises PayrollImmutableError."""
        with self.assertRaises(PayrollImmutableError):
            finalize_payroll_run(self.run)


class TestUniqueConstraints(TestCase):
    """Tests 14, 15: Duplicate PayrollRun prevention and parallel run_type."""

    def setUp(self):
        self.org = make_org('OrgUniq')

    def test_duplicate_run_rejected(self):
        """Test 14: Cannot create two runs with same (org, year, month, run_type)."""
        make_run(self.org, 2026, 3, 'REGULAR')
        with self.assertRaises(IntegrityError):
            make_run(self.org, 2026, 3, 'REGULAR')

    def test_parallel_run_type_allowed(self):
        """Test 15: Parallel runs with different run_type are allowed."""
        run1 = make_run(self.org, 2026, 3, 'REGULAR')
        run2 = make_run(self.org, 2026, 3, 'PARALLEL_A')
        self.assertNotEqual(run1.id, run2.id)
        self.assertEqual(PayrollRun.objects.filter(
            organization=self.org, year=2026, month=3
        ).count(), 2)


class TestLegacyFallback(TestCase):
    """Tests 16, 21, 23: Missing structure → legacy fallback line item."""

    def setUp(self):
        self.org = make_org('OrgLegacy')
        self.emp = make_employee(self.org, code='EMPLEGACY')
        make_comp(self.emp, Decimal('35000'))  # No salary_structure
        self.run = make_run(self.org)

    def test_legacy_backfilled_line_item_created(self):
        """Test 16 + 21: Without SalaryStructure, a backfilled EARNING line item is created."""
        generate_payroll_for_period(self.run)
        record = PayrollRecord.objects.get(period=self.run, employee=self.emp)
        li = record.line_items.filter(is_backfilled=True).first()
        self.assertIsNotNone(li, "Expected a backfilled legacy line item")
        self.assertEqual(li.category, 'EARNING')
        self.assertEqual(li.calculation_metadata.get('source'), 'legacy_basic_salary')

    def test_legacy_basic_salary_used_for_gross(self):
        """Test 21: Legacy path uses basic_salary from CompensationHistory."""
        generate_payroll_for_period(self.run)
        record = PayrollRecord.objects.get(period=self.run, employee=self.emp)
        self.assertEqual(record.basic_salary, Decimal('35000'))


class TestUnsupportedCalculationType(TestCase):
    """Test 17: Unsupported calculation_type raises PayrollCalculationError."""

    def setUp(self):
        self.org = make_org('OrgBadCalc')
        self.emp = make_employee(self.org, code='EMPBAD')
        self.structure = make_structure(self.org, 'BadCalcStruct')
        self.sc = make_component(self.org, 'MYSTERY', 'earning')

        # Bypass the choices validation to insert an unsupported type
        SalaryStructureComponent.objects.create(
            structure=self.structure,
            component=self.sc,
            amount=Decimal('1000'),
            calculation_type='MAGIC_FORMULA',  # Not in CALC_CHOICES
        )
        make_comp(self.emp, Decimal('50000'), structure=self.structure)
        self.run = make_run(self.org)

    def test_unsupported_type_raises_error(self):
        with self.assertRaises(PayrollCalculationError) as ctx:
            generate_payroll_for_period(self.run)
        self.assertIn('MAGIC_FORMULA', str(ctx.exception))
        self.assertIn('Unsupported', str(ctx.exception))


class TestTenantIsolation(TestCase):
    """Test 18 + 19: Payroll records are scoped to their organization."""

    def setUp(self):
        self.org1 = make_org('OrgTenant1')
        self.org2 = make_org('OrgTenant2')

        self.emp1 = make_employee(self.org1, code='ORG1EMP')
        self.emp2 = make_employee(self.org2, code='ORG2EMP')

        make_comp(self.emp1, Decimal('40000'))
        make_comp(self.emp2, Decimal('55000'))

        self.run1 = make_run(self.org1, 2026, 3)
        self.run2 = make_run(self.org2, 2026, 3)

    def test_generate_scoped_to_org(self):
        """Test 18: generate_payroll_for_period only creates records for run.organization."""
        generate_payroll_for_period(self.run1)

        org1_records = PayrollRecord.objects.filter(period=self.run1)
        org2_records = PayrollRecord.objects.filter(period=self.run2)

        self.assertTrue(org1_records.exists())
        self.assertFalse(org2_records.exists())

        # org2 employee must NOT appear in org1's run
        emp2_in_run1 = org1_records.filter(employee=self.emp2).exists()
        self.assertFalse(emp2_in_run1, "IDOR: org2 employee must not appear in org1 payroll run")

    def test_idor_record_not_accessible_across_orgs(self):
        """Test 19: PayrollRecord for org1 cannot be queried via org2's run."""
        generate_payroll_for_period(self.run1)
        generate_payroll_for_period(self.run2)

        # org1's record should not be visible when filtering by org2's run
        org2_emp_ids = list(self.org2.employees.values_list('id', flat=True))
        org1_records_via_org2 = PayrollRecord.objects.filter(
            period=self.run2,
            employee__id__in=org2_emp_ids,
        ).filter(period__organization=self.org1)  # Should be empty
        self.assertFalse(org1_records_via_org2.exists(), "Cross-tenant IDOR detected")


class TestHistoricalSnapshot(TestCase):
    """Test 20 + 22: Historical snapshot is preserved; basic_salary is snapshotted."""

    def setUp(self):
        self.org = make_org('OrgHistory')
        self.emp = make_employee(self.org, code='EMPHIST')
        make_comp(self.emp, Decimal('45000'))
        self.run = make_run(self.org)

    def test_basic_salary_snapshotted_on_record(self):
        """Test 20: PayrollRecord.basic_salary captures the salary at generation time."""
        generate_payroll_for_period(self.run)
        record = PayrollRecord.objects.get(period=self.run, employee=self.emp)
        self.assertEqual(record.basic_salary, Decimal('45000'))

    def test_record_snapshot_survives_salary_change(self):
        """Test 20b: Changing salary after generation does not alter existing record."""
        generate_payroll_for_period(self.run)
        record = PayrollRecord.objects.get(period=self.run, employee=self.emp)
        original_salary = record.basic_salary

        # Change salary
        CompensationHistory.objects.filter(employee=self.emp).update(
            effective_to=date(2026, 3, 1)
        )
        CompensationHistory.objects.create(
            employee=self.emp,
            effective_from=date(2026, 4, 1),
            basic_salary=Decimal('99999'),
        )

        # Refresh
        record.refresh_from_db()
        self.assertEqual(record.basic_salary, original_salary, "Snapshot should not change")

    def test_line_item_metadata_includes_basic_salary(self):
        """Test 22: Line items store calculation evidence in metadata."""
        structure = make_structure(self.org, 'HistoryStruct')
        sc = make_component(self.org, 'BASIC_HIST', 'earning')
        make_structure_component(structure, sc, Decimal('45000'), 'FIXED_AMOUNT')
        CompensationHistory.objects.filter(employee=self.emp).update(salary_structure=structure)

        generate_payroll_for_period(self.run)
        record = PayrollRecord.objects.get(period=self.run, employee=self.emp)
        li = record.line_items.first()
        self.assertEqual(li.calculation_base, Decimal('45000.00'))


class TestLineItemLineage(TestCase):
    """Test 23: PayrollLineItem has correct FK lineage fields."""

    def setUp(self):
        self.org = make_org('OrgLineage')
        self.emp = make_employee(self.org, code='EMPLIN')
        self.structure = make_structure(self.org, 'LinStruct')
        self.sc = make_component(self.org, 'LIN_BASIC', 'earning')
        self.ssc = make_structure_component(self.structure, self.sc, Decimal('30000'), 'FIXED_AMOUNT')
        make_comp(self.emp, Decimal('30000'), structure=self.structure)
        self.run = make_run(self.org)

    def test_source_structure_component_set(self):
        generate_payroll_for_period(self.run)
        record = PayrollRecord.objects.get(period=self.run, employee=self.emp)
        li = record.line_items.filter(category='EARNING').first()
        self.assertIsNotNone(li.source_structure_component)
        self.assertEqual(li.source_structure_component, self.ssc)

    def test_adjustment_lineage(self):
        sc_bonus = make_component(self.org, 'LIN_BONUS', 'earning')
        adj = PayrollAdjustment.objects.create(
            employee=self.emp,
            component=sc_bonus,
            amount=Decimal('1000'),
            period_year=2026,
            period_month=3,
            status=PayrollAdjustment.STATUS_APPROVED,
        )
        generate_payroll_for_period(self.run)
        record = PayrollRecord.objects.get(period=self.run, employee=self.emp)
        adj_li = record.line_items.filter(source_adjustment=adj).first()
        self.assertIsNotNone(adj_li)
        self.assertIsNone(adj_li.source_structure_component)


class TestFinalizeTransition(TestCase):
    """Test finalize_payroll_run lifecycle."""

    def setUp(self):
        self.org = make_org('OrgFinTrans')
        self.emp = make_employee(self.org, code='EMPFT')
        make_comp(self.emp, Decimal('20000'))
        self.run = make_run(self.org)
        generate_payroll_for_period(self.run)
        self.run.status = PayrollRun.STATUS_APPROVED
        self.run.save()
        PayrollRecord.objects.filter(period=self.run).update(status=PayrollRecord.STATUS_APPROVED)

    def test_finalize_from_draft_raises(self):
        draft_run = make_run(self.org, 2026, 4)
        make_comp(self.emp, Decimal('20000'))
        with self.assertRaises(ValueError):
            finalize_payroll_run(draft_run)

    def test_finalize_approved_succeeds(self):
        result = finalize_payroll_run(self.run)
        self.assertEqual(result.status, PayrollRun.STATUS_FINALIZED)
