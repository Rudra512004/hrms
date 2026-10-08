from datetime import date
from django.utils import timezone
from apps.alerts.models import AlertRule, EmployeeAlertPreference, AlertInstance
from apps.employees.models import Employee
from apps.notifications.services import NotificationService
from .evaluators import get_evaluator

class AlertEvaluationService:
    @staticmethod
    def _employee_in_scope(employee: Employee, rule: AlertRule) -> bool:
        if not rule.applicable_branches.exists() and \
           not rule.applicable_departments.exists() and \
           not rule.applicable_teams.exists():
            return True

        if rule.applicable_branches.filter(id=employee.branch_id).exists():
            return True

        if employee.department_id and rule.applicable_departments.filter(id=employee.department_id).exists():
            return True

        if employee.team_id and rule.applicable_teams.filter(id=employee.team_id).exists():
            return True

        return False

    @staticmethod
    def resolve_employee_threshold(employee: Employee, rule: AlertRule):
        if not rule.is_enabled:
            return None
        if not AlertEvaluationService._employee_in_scope(employee, rule):
            return None
            
        if rule.employee_customization_allowed:
            pref = EmployeeAlertPreference.objects.filter(employee=employee, rule=rule).first()
            if pref:
                if not pref.is_enabled:
                    return None
                if pref.custom_value is not None:
                    return pref.custom_value
        
        return rule.default_value

    @classmethod
    def evaluate_all(cls, target_date=None):
        if target_date is None:
            target_date = timezone.now().date()
            
        rules = AlertRule.objects.filter(is_enabled=True).prefetch_related(
            'applicable_branches', 'applicable_departments', 'applicable_teams'
        )

        for rule in rules:
            evaluator_cls = get_evaluator(rule.alert_type)
            if not evaluator_cls:
                continue
            
            from django.db.models import Q
            if not rule.applicable_branches.exists() and not rule.applicable_departments.exists() and not rule.applicable_teams.exists():
                employees = Employee.objects.filter(organization=rule.organization, user__status='active')
            else:
                q = Q(branch__in=rule.applicable_branches.all()) | \
                    Q(department__in=rule.applicable_departments.all()) | \
                    Q(team__in=rule.applicable_teams.all())
                employees = Employee.objects.filter(Q(organization=rule.organization, user__status='active') & q)

            for employee in employees:
                threshold = cls.resolve_employee_threshold(employee, rule)
                if threshold is None:
                    continue
                
                evaluator = evaluator_cls(employee, rule, threshold, target_date)
                evaluator.evaluate()

    @classmethod
    def evaluate_employee_event(cls, employee: Employee, target_date=None):
        """Called synchronously when an employee performs an action (check-in, break, checkout)"""
        if target_date is None:
            target_date = timezone.now().date()
            
        rules = AlertRule.objects.filter(organization=employee.organization_id, is_enabled=True).prefetch_related(
            'applicable_branches', 'applicable_departments', 'applicable_teams'
        )

        for rule in rules:
            threshold = cls.resolve_employee_threshold(employee, rule)
            if threshold is None:
                continue
                
            evaluator_cls = get_evaluator(rule.alert_type)
            if evaluator_cls:
                evaluator = evaluator_cls(employee, rule, threshold, target_date)
                evaluator.evaluate()

    @classmethod
    def trigger_alert(cls, employee: Employee, rule: AlertRule, occurrence_key: str, metric_value: int, target_date: date, message: str):
        # Deterministic deduplication
        if AlertInstance.objects.filter(rule=rule, employee=employee, occurrence_key=occurrence_key).exists():
            return

        instance = AlertInstance.objects.create(
            employee=employee,
            rule=rule,
            occurrence_key=occurrence_key,
            reference_date=target_date,
            metric_value_at_trigger=metric_value,
            status='detected'
        )

        if rule.notification_enabled:
            # Reusing existing NotificationService
            NotificationService.create_in_app_notification(
                recipient=employee.user,
                organization=rule.organization,
                notification_type='WORK_HEALTH_ALERT',
                title=f"Alert: {rule.name}",
                message=message,
                reference_id=f"alert_{instance.id}"
            )
            instance.status = 'notified'
            instance.save()
