from django.test import TestCase
from django.utils import timezone
from datetime import timedelta, date
from django.core.exceptions import ValidationError
from apps.organization.models import Organization, Branch, Department, Team
from apps.employees.models import Employee
from apps.alerts.models import AlertRule, EmployeeAlertPreference, AlertInstance
from apps.alerts.services import AlertEvaluationService
from apps.attendance.models import Attendance, AttendanceProductivity, AttendanceBreak
from apps.accounts.models import User
import uuid

class WorkHealthAlertTests(TestCase):
    def setUp(self):
        self.org1 = Organization.objects.create(name="Org1", code="O1")
        self.org2 = Organization.objects.create(name="Org2", code="O2")
        
        self.branch1 = Branch.objects.create(organization=self.org1, name="B1")
        self.branch2 = Branch.objects.create(organization=self.org2, name="B2")
        
        self.user1 = User.objects.create_user(email="u1@test.com", password="pwd", first_name="User", last_name="1")
        self.user1.status = 'active'
        self.user1.save()
        self.emp1 = Employee.objects.create(user=self.user1, organization=self.org1, branch=self.branch1)
        
        self.user2 = User.objects.create_user(email="u2@test.com", password="pwd", first_name="User", last_name="2")
        self.user2.status = 'active'
        self.user2.save()
        self.emp2 = Employee.objects.create(user=self.user2, organization=self.org2, branch=self.branch2)

    def test_alert_rule_validation(self):
        # 1. Organization integrity check on M2M is difficult to unit test directly without triggering m2m_changed,
        # but we can test the bounds:
        rule = AlertRule(
            organization=self.org1,
            alert_type='excessive_hours',
            name="Test",
            default_value=60,
            minimum_value=120,
            maximum_value=100, # Invalid bounds
            value_unit='minutes'
        )
        with self.assertRaises(ValidationError):
            rule.full_clean()
            
        rule.minimum_value = 30
        rule.maximum_value = 120
        rule.default_value = 20 # Below minimum
        with self.assertRaises(ValidationError):
            rule.full_clean()
            
        rule.default_value = 60
        rule.save()

    def test_employee_preference_validation(self):
        rule = AlertRule.objects.create(
            organization=self.org1,
            alert_type='excessive_hours',
            name="Test",
            default_value=60,
            minimum_value=30,
            maximum_value=120,
            value_unit='minutes',
            employee_customization_allowed=False
        )
        
        # Cross-tenant validation
        pref = EmployeeAlertPreference(employee=self.emp2, rule=rule, custom_value=50)
        with self.assertRaises(ValidationError) as e:
            pref.full_clean()
        self.assertIn('same organization', str(e.exception))

        # Customization disabled
        pref = EmployeeAlertPreference(employee=self.emp1, rule=rule, custom_value=50)
        with self.assertRaises(ValidationError) as e:
            pref.full_clean()
        self.assertIn('not allowed', str(e.exception))
        
        rule.employee_customization_allowed = True
        rule.save()
        
        # Out of bounds
        pref = EmployeeAlertPreference(employee=self.emp1, rule=rule, custom_value=20) # < 30
        with self.assertRaises(ValidationError) as e:
            pref.full_clean()
        self.assertIn('less than the rule minimum', str(e.exception))
        
        pref.custom_value = 60
        pref.save()

    def test_duplicate_prevention(self):
        rule = AlertRule.objects.create(
            organization=self.org1, alert_type='excessive_hours', name="Test", default_value=60, value_unit='minutes'
        )
        target_date = date(2026, 10, 8)
        
        AlertEvaluationService.trigger_alert(self.emp1, rule, "key_1", 100, target_date, "Msg")
        self.assertEqual(AlertInstance.objects.count(), 1)
        
        # Trigger same key
        AlertEvaluationService.trigger_alert(self.emp1, rule, "key_1", 120, target_date, "Msg2")
        self.assertEqual(AlertInstance.objects.count(), 1)
        
        # Trigger different key
        AlertEvaluationService.trigger_alert(self.emp1, rule, "key_2", 120, target_date, "Msg3")
        self.assertEqual(AlertInstance.objects.count(), 2)

    def test_excessive_hours_evaluator(self):
        rule = AlertRule.objects.create(
            organization=self.org1, alert_type='excessive_hours', name="Test", default_value=60, value_unit='minutes'
        )
        target_date = date(2026, 10, 8)
        now = timezone.now()
        
        # 120 minutes of work
        att = Attendance.objects.create(employee=self.emp1, date=target_date, check_in=now - timedelta(minutes=120), check_out=now)
        
        AlertEvaluationService.evaluate_employee_event(self.emp1, target_date)
        self.assertEqual(AlertInstance.objects.count(), 1)
        instance = AlertInstance.objects.first()
        self.assertEqual(instance.rule, rule)
        self.assertEqual(instance.metric_value_at_trigger, 120)

    def test_hydration_evaluator(self):
        rule = AlertRule.objects.create(
            organization=self.org1, alert_type='hydration', name="Hydration", default_value=30, value_unit='minutes'
        )
        target_date = date(2026, 10, 8)
        now = timezone.now()
        
        # 65 minutes of active work
        att = Attendance.objects.create(employee=self.emp1, date=target_date, check_in=now - timedelta(minutes=65), check_out=now)
        
        AlertEvaluationService.evaluate_employee_event(self.emp1, target_date)
        
        # Block 2 (65 // 30 = 2) should trigger
        self.assertEqual(AlertInstance.objects.count(), 1)
        instance = AlertInstance.objects.first()
        self.assertEqual(instance.occurrence_key, f"{target_date}_block_2")

    def test_long_session_evaluator(self):
        rule = AlertRule.objects.create(
            organization=self.org1, alert_type='long_session', name="Test LS", default_value=60, value_unit='minutes'
        )
        target_date = date(2026, 10, 8)
        now = timezone.now()
        att = Attendance.objects.create(employee=self.emp1, date=target_date, check_in=now - timedelta(minutes=120), check_out=now)
        AlertEvaluationService.evaluate_employee_event(self.emp1, target_date)
        self.assertEqual(AlertInstance.objects.count(), 1)
        
    def test_break_reminder_evaluator(self):
        rule = AlertRule.objects.create(
            organization=self.org1, alert_type='break_reminder', name="Test BR", default_value=60, value_unit='minutes'
        )
        target_date = date(2026, 10, 8)
        now = timezone.now()
        att = Attendance.objects.create(employee=self.emp1, date=target_date, check_in=now - timedelta(minutes=120), check_out=now)
        AlertEvaluationService.evaluate_employee_event(self.emp1, target_date)
        self.assertEqual(AlertInstance.objects.count(), 1)

    def test_excessive_break_evaluator(self):
        rule = AlertRule.objects.create(
            organization=self.org1, alert_type='excessive_break', name="Test EB", default_value=15, value_unit='minutes'
        )
        target_date = date(2026, 10, 8)
        now = timezone.now()
        att = Attendance.objects.create(employee=self.emp1, date=target_date, check_in=now - timedelta(minutes=120), check_out=now)
        # Add a break
        AttendanceBreak.objects.create(attendance=att, started_at=now - timedelta(minutes=30), ended_at=now - timedelta(minutes=5))
        
        AlertEvaluationService.evaluate_employee_event(self.emp1, target_date)
        self.assertEqual(AlertInstance.objects.count(), 1)

    def test_prolonged_idle_evaluator(self):
        rule = AlertRule.objects.create(
            organization=self.org1, alert_type='prolonged_idle', name="Test PI", default_value=15, value_unit='minutes'
        )
        target_date = date(2026, 10, 8)
        now = timezone.now()
        att = Attendance.objects.create(employee=self.emp1, date=target_date, check_in=now - timedelta(minutes=120), check_out=now)
        prod = AttendanceProductivity.objects.create(attendance=att, idle_duration=timedelta(minutes=30))
        
        AlertEvaluationService.evaluate_employee_event(self.emp1, target_date)
        self.assertEqual(AlertInstance.objects.count(), 1)

    def test_low_active_evaluator(self):
        rule = AlertRule.objects.create(
            organization=self.org1, alert_type='low_active', name="Test LA", default_value=80, value_unit='percentage'
        )
        target_date = date(2026, 10, 8)
        now = timezone.now()
        # Ensure they have worked > 120 mins grace period
        att = Attendance.objects.create(employee=self.emp1, date=target_date, check_in=now - timedelta(minutes=130), check_out=now)
        prod = AttendanceProductivity.objects.create(attendance=att, active_percent=70) # Less than 80
        
        AlertEvaluationService.evaluate_employee_event(self.emp1, target_date)
        self.assertEqual(AlertInstance.objects.count(), 1)

    def test_consecutive_days_evaluator(self):
        rule = AlertRule.objects.create(
            organization=self.org1, alert_type='consecutive_days', name="Test CD", default_value=6, value_unit='days'
        )
        target_date = date(2026, 10, 8)
        now = timezone.now()
        # Seed 7 consecutive days
        for i in range(7):
            Attendance.objects.create(employee=self.emp1, date=target_date - timedelta(days=i), check_in=now)
            
        AlertEvaluationService.evaluate_employee_event(self.emp1, target_date)
        self.assertEqual(AlertInstance.objects.count(), 1)

    def test_late_start_evaluator(self):
        rule = AlertRule.objects.create(
            organization=self.org1, alert_type='late_start', name="Test Late", default_value=15, value_unit='minutes'
        )
        target_date = date(2026, 10, 8)
        
        # Late start depends on shift. If no shift, it should not trigger. Let's mock the service for this test.
        from unittest.mock import patch
        from apps.attendance.services import AttendanceCalculationService
        class DummyShift:
            start_time = (timezone.now() - timedelta(minutes=60)).time() # 60 minutes ago
            
        with patch.object(AttendanceCalculationService, 'resolve_scheduled_shift', return_value=DummyShift()):
            # Employee has NO check-in yet, and time is way past the 15-minute grace limit
            AlertEvaluationService.evaluate_employee_event(self.emp1, target_date)
            self.assertEqual(AlertInstance.objects.count(), 1)

    def test_employee_customization_disabled(self):
        # Already tested in test_employee_preference_validation, but adding specific bound edge cases
        rule = AlertRule.objects.create(
            organization=self.org1, alert_type='excessive_hours', name="Test", default_value=60, 
            minimum_value=30, maximum_value=120, employee_customization_allowed=True, value_unit='minutes'
        )
        
        # Exactly minimum
        pref1 = EmployeeAlertPreference.objects.create(employee=self.emp1, rule=rule, custom_value=30)
        self.assertEqual(pref1.custom_value, 30)
        
        # Exactly maximum
        pref1.custom_value = 120
        pref1.save()
        self.assertEqual(pref1.custom_value, 120)
        
        # Above maximum
        pref1.custom_value = 121
        with self.assertRaises(ValidationError):
            pref1.full_clean()
            
    def test_cron_idempotent_execution(self):
        # Create an instance that should be detected, run the evaluate_all multiple times
        rule = AlertRule.objects.create(
            organization=self.org1, alert_type='excessive_hours', name="Test", default_value=60, value_unit='minutes'
        )
        target_date = date(2026, 10, 8)
        now = timezone.now()
        att = Attendance.objects.create(employee=self.emp1, date=target_date, check_in=now - timedelta(minutes=120), check_out=now)
        
        AlertEvaluationService.evaluate_all(target_date)
        self.assertEqual(AlertInstance.objects.count(), 1)
        
        # Running it again should NOT create a duplicate
        AlertEvaluationService.evaluate_all(target_date)
        self.assertEqual(AlertInstance.objects.count(), 1)
