from datetime import timedelta
from django.utils import timezone
from apps.attendance.models import Attendance, AttendanceBreak, AttendanceProductivity

class BaseAlertEvaluator:
    def __init__(self, employee, rule, threshold, target_date):
        self.employee = employee
        self.rule = rule
        self.threshold = threshold
        self.target_date = target_date

    def evaluate(self):
        raise NotImplementedError

    def _trigger(self, occurrence_key, metric_value, message):
        from .services import AlertEvaluationService
        AlertEvaluationService.trigger_alert(
            employee=self.employee,
            rule=self.rule,
            occurrence_key=occurrence_key,
            metric_value=metric_value,
            target_date=self.target_date,
            message=message
        )

class ExcessiveHoursEvaluator(BaseAlertEvaluator):
    def evaluate(self):
        # Unit: minutes
        att = Attendance.objects.filter(employee=self.employee, date=self.target_date).first()
        if not att or not att.check_in:
            return
        
        end_time = att.check_out if att.check_out else timezone.now()
        duration = end_time - att.check_in
        if duration.total_seconds() / 60 > self.threshold:
            self._trigger(
                occurrence_key=f"{self.target_date}",
                metric_value=int(duration.total_seconds() / 60),
                message=f"Working session has exceeded the {self.threshold}-minute threshold."
            )

class LongSessionEvaluator(BaseAlertEvaluator):
    def evaluate(self):
        # Unit: minutes
        att = Attendance.objects.filter(employee=self.employee, date=self.target_date).first()
        if not att or not att.check_in:
            return
        
        last_break = att.breaks.filter(ended_at__isnull=False).order_by('-ended_at').first()
        session_start = last_break.ended_at if last_break else att.check_in
        end_time = att.check_out if att.check_out else timezone.now()
        
        duration = end_time - session_start
        if duration.total_seconds() / 60 > self.threshold:
            self._trigger(
                occurrence_key=f"{self.target_date}_{session_start.strftime('%H%M')}",
                metric_value=int(duration.total_seconds() / 60),
                message=f"You have been working continuously for over {self.threshold} minutes."
            )

class BreakReminderEvaluator(LongSessionEvaluator):
    def evaluate(self):
        # Same logic as LongSession but different message/severity
        att = Attendance.objects.filter(employee=self.employee, date=self.target_date).first()
        if not att or not att.check_in:
            return
        
        last_break = att.breaks.filter(ended_at__isnull=False).order_by('-ended_at').first()
        session_start = last_break.ended_at if last_break else att.check_in
        end_time = att.check_out if att.check_out else timezone.now()
        
        duration = end_time - session_start
        if duration.total_seconds() / 60 > self.threshold:
            self._trigger(
                occurrence_key=f"{self.target_date}_{session_start.strftime('%H%M')}",
                metric_value=int(duration.total_seconds() / 60),
                message=f"Break Reminder: You've been working continuously for {self.threshold} minutes."
            )

class ExcessiveBreakEvaluator(BaseAlertEvaluator):
    def evaluate(self):
        # Unit: minutes
        att = Attendance.objects.filter(employee=self.employee, date=self.target_date).first()
        if not att:
            return
        
        for brk in att.breaks.all():
            end_time = brk.ended_at if brk.ended_at else timezone.now()
            duration = end_time - brk.started_at
            if duration.total_seconds() / 60 > self.threshold:
                self._trigger(
                    occurrence_key=f"{self.target_date}_{brk.id}",
                    metric_value=int(duration.total_seconds() / 60),
                    message=f"Break duration has exceeded the {self.threshold}-minute threshold."
                )

class ProlongedIdleEvaluator(BaseAlertEvaluator):
    def evaluate(self):
        # Unit: minutes
        att = Attendance.objects.filter(employee=self.employee, date=self.target_date).first()
        if not att or not hasattr(att, 'productivity'):
            return
        
        prod = att.productivity
        if prod.idle_duration and prod.idle_duration.total_seconds() / 60 > self.threshold:
            self._trigger(
                occurrence_key=f"{self.target_date}",
                metric_value=int(prod.idle_duration.total_seconds() / 60),
                message=f"Idle duration has exceeded the {self.threshold}-minute threshold."
            )

class LowActiveEvaluator(BaseAlertEvaluator):
    def evaluate(self):
        """
        Unit: percentage
        Provisional Product Rule: A hardcoded 2-hour (120 minutes) grace period is enforced 
        from the start of the shift before evaluating low active time. This prevents false 
        positives early in the session when employees are just getting started.
        """
        att = Attendance.objects.filter(employee=self.employee, date=self.target_date).first()
        if not att or not hasattr(att, 'productivity') or not att.check_in:
            return
        end_time = att.check_out if att.check_out else timezone.now()
        duration_minutes = (end_time - att.check_in).total_seconds() / 60
        if duration_minutes < 120:
            return
            
        prod = att.productivity
        if prod.active_percent is not None and prod.active_percent < self.threshold:
            self._trigger(
                occurrence_key=f"{self.target_date}",
                metric_value=int(prod.active_percent),
                message=f"Active percentage has fallen below the {self.threshold}% threshold."
            )

class ConsecutiveDaysEvaluator(BaseAlertEvaluator):
    def evaluate(self):
        # Unit: days
        # Simple backward search of consecutive days with an attendance check-in
        count = 0
        current_date = self.target_date
        while Attendance.objects.filter(employee=self.employee, date=current_date, check_in__isnull=False).exists():
            count += 1
            current_date -= timedelta(days=1)
            
        if count > self.threshold:
            self._trigger(
                occurrence_key=f"{self.target_date}",
                metric_value=count,
                message=f"You have worked {count} consecutive days, exceeding the {self.threshold}-day threshold."
            )

class LateStartEvaluator(BaseAlertEvaluator):
    def evaluate(self):
        # Unit: minutes (grace period)
        # Evaluated daily typically via cron
        from apps.attendance.services import AttendanceCalculationService
        shift = AttendanceCalculationService.resolve_scheduled_shift(self.employee, self.target_date)
        if not shift:
            return
            
        # Check if they are absent so far
        if Attendance.objects.filter(employee=self.employee, date=self.target_date, check_in__isnull=False).exists():
            return
            
        shift_start_dt = timezone.make_aware(timezone.datetime.combine(self.target_date, shift.start_time))
        grace_limit = shift_start_dt + timedelta(minutes=self.threshold)
        
        if timezone.now() > grace_limit:
            self._trigger(
                occurrence_key=f"{self.target_date}",
                metric_value=self.threshold,
                message=f"Attendance Reminder: You have not checked in within the {self.threshold}-minute grace period."
            )

class HydrationEvaluator(BaseAlertEvaluator):
    def evaluate(self):
        # Unit: minutes
        # We trigger this multiple times a day by resetting the occurrence key per block of time
        att = Attendance.objects.filter(employee=self.employee, date=self.target_date).first()
        if not att or not att.check_in:
            return
            
        # Active session duration
        end_time = att.check_out if att.check_out else timezone.now()
        duration = end_time - att.check_in
        if att.total_break_duration:
            duration -= att.total_break_duration
            
        total_active_minutes = int(duration.total_seconds() / 60)
        
        # Determine which hydration block they are in
        block_number = total_active_minutes // self.threshold
        
        if block_number > 0:
            self._trigger(
                occurrence_key=f"{self.target_date}_block_{block_number}",
                metric_value=total_active_minutes,
                message=f"Hydration Reminder: You've been working actively for over {block_number * self.threshold} minutes. Consider a short break."
            )

EVALUATORS = {
    'excessive_hours': ExcessiveHoursEvaluator,
    'long_session': LongSessionEvaluator,
    'break_reminder': BreakReminderEvaluator,
    'excessive_break': ExcessiveBreakEvaluator,
    'prolonged_idle': ProlongedIdleEvaluator,
    'low_active': LowActiveEvaluator,
    'consecutive_days': ConsecutiveDaysEvaluator,
    'late_start': LateStartEvaluator,
    'hydration': HydrationEvaluator,
}

def get_evaluator(alert_type):
    return EVALUATORS.get(alert_type)
