"""
DashboardAggregationService executes pure database-level aggregations
for the HRMS Dashboard V2 without loading entire tables into memory.

Respects:
- Organization boundary isolation
- Dynamic RBAC permissions via AuthorizationService
- Safe handling of users without employee profiles
- Manager direct-report hierarchy
"""
import calendar
from datetime import timedelta, date
from django.utils import timezone
from django.db.models import Count, F, Q
from rest_framework.exceptions import PermissionDenied
from apps.authorization.services import AuthorizationService
from apps.attendance.models import Attendance, Holiday
from apps.leaves.models import LeaveBalance, LeaveRequest
from apps.employees.models import Employee, WFHRequest



class DashboardAggregationService:
    @classmethod
    def get_dashboard_overview(cls, user, branch_id=None):
        """
        Main entry point for retrieving Dashboard V2 metrics.
        Returns a structured dictionary with 'personal', 'team', and 'organization'.
        Raises PermissionDenied (HTTP 403) if a requested branch_id is unauthorized.
        """
        if branch_id:
            try:
                b_id = int(branch_id)
            except (ValueError, TypeError):
                raise PermissionDenied("You do not have permission to access this branch.")

            emp_branches = AuthorizationService.get_authorized_branches(user, 'employee.view')
            att_branches = AuthorizationService.get_authorized_branches(user, 'attendance.view_all')
            leave_branches = AuthorizationService.get_authorized_branches(user, 'leave.view')
            wfh_branches = AuthorizationService.get_authorized_branches(user, 'wfh.view')

            is_authorized = (
                emp_branches.filter(id=b_id).exists() or
                att_branches.filter(id=b_id).exists() or
                leave_branches.filter(id=b_id).exists() or
                wfh_branches.filter(id=b_id).exists()
            )
            if not is_authorized:
                raise PermissionDenied("You do not have permission to access this branch.")

        today = timezone.localdate()

        personal_data = cls.get_personal_data(user, today)
        team_data = cls.get_team_data(user, today)
        organization_data = cls.get_organization_data(user, today, branch_id)

        return {
            'personal': personal_data,
            'team': team_data,
            'organization': organization_data,
        }

    @classmethod
    def get_personal_data(cls, user, today):
        """
        Aggregates metrics for the caller's personal workspace.
        Returns None if user has no associated Employee profile.
        """
        if not hasattr(user, 'employee') or user.employee is None:
            return None

        employee = user.employee

        # 1. Today's attendance record
        att = Attendance.objects.filter(employee=employee, date=today).first()
        att_data = None
        if att:
            is_on_break = att.breaks.filter(ended_at__isnull=True).exists()
            total_break_sec = (
                int(att.total_break_duration.total_seconds())
                if att.total_break_duration
                else 0
            )
            productive_sec = (
                int(att.productive_work_duration.total_seconds())
                if att.productive_work_duration
                else 0
            )
            att_data = {
                'id': att.id,
                'date': str(att.date),
                'status': att.status,
                'check_in': att.check_in.isoformat() if att.check_in else None,
                'check_out': att.check_out.isoformat() if att.check_out else None,
                'is_on_break': is_on_break,
                'total_break_duration_seconds': total_break_sec,
                'productive_work_duration_seconds': productive_sec,
            }

        # 2. Leave balances
        balances = LeaveBalance.objects.filter(employee=employee).select_related('leave_type')
        balances_data = [
            {
                'leave_type_id': b.leave_type_id,
                'leave_type_name': b.leave_type.name,
                'allocated': b.allocated,
                'used': b.used,
                'remaining': b.remaining,
            }
            for b in balances
        ]

        # 3. Personal pending requests count
        pending_leaves_count = LeaveRequest.objects.filter(
            employee=employee, status='pending'
        ).count()
        pending_wfh_count = WFHRequest.objects.filter(
            employee=employee, status='pending'
        ).count()

        # 4. Upcoming holidays (max 3)
        upcoming_holidays = []
        if employee.branch_id:
            holidays = Holiday.objects.filter(
                branch_id=employee.branch_id,
                is_active=True,
                date__gte=today
            ).order_by('date')[:3]
            upcoming_holidays = [
                {'id': h.id, 'name': h.name, 'date': str(h.date)}
                for h in holidays
            ]

        return {
            'attendance_today': att_data,
            'leave_balances': balances_data,
            'my_pending_requests': {
                'leaves': pending_leaves_count,
                'wfh': pending_wfh_count,
                'total': pending_leaves_count + pending_wfh_count,
            },
            'upcoming_holidays': upcoming_holidays,
        }

    @classmethod
    def get_team_data(cls, user, today):
        """
        Aggregates metrics for managers who have direct reports.
        Returns None if user has no employee profile or 0 direct reports.
        """
        if not hasattr(user, 'employee') or user.employee is None:
            return None

        employee = user.employee
        team_qs = employee.direct_reports.filter(user__status='active')
        direct_reports_count = team_qs.count()

        if direct_reports_count == 0:
            return None

        # 1. Team Attendance Pulse today
        team_att = Attendance.objects.filter(employee__in=team_qs, date=today)
        present_emp_ids = set(team_att.filter(status='present').values_list('employee_id', flat=True))
        half_day_emp_ids = set(team_att.filter(status='half_day').values_list('employee_id', flat=True))
        on_break_count = team_att.filter(breaks__ended_at__isnull=True).distinct().count()

        now = timezone.now()
        leave_emp_ids = set(LeaveRequest.objects.filter(
            employee__in=team_qs,
            status='approved',
            start_date__lte=today,
            end_date__gte=today
        ).values_list('employee_id', flat=True))

        effective_on_leave_ids = leave_emp_ids - present_emp_ids - half_day_emp_ids
        on_leave_count = len(effective_on_leave_ids)
        present_count = len(present_emp_ids)
        half_day_count = len(half_day_emp_ids)

        on_wfh_count = WFHRequest.objects.filter(
            employee__in=team_qs,
            status='approved',
            start_at__lte=now,
            end_at__gte=now
        ).count()

        absent_count = max(0, direct_reports_count - (present_count + half_day_count + on_leave_count))

        # 2. Pending team approvals queue (leaves and WFH, max 5 items each)
        pending_leaves_qs = LeaveRequest.objects.filter(
            employee__in=team_qs,
            status='pending'
        ).select_related('employee__user', 'leave_type').order_by('-created_at')

        pending_leaves_count = pending_leaves_qs.count()
        pending_leaves_items = [
            {
                'id': l.id,
                'employee_id': l.employee_id,
                'employee_name': f"{l.employee.user.first_name} {l.employee.user.last_name}".strip() or l.employee.user.email,
                'leave_type': l.leave_type.name,
                'start_date': str(l.start_date),
                'end_date': str(l.end_date),
                'duration_days': l.duration_days,
                'reason': l.reason,
                'created_at': l.created_at.isoformat(),
            }
            for l in pending_leaves_qs[:5]
        ]

        pending_wfh_qs = WFHRequest.objects.filter(
            employee__in=team_qs,
            status='pending'
        ).select_related('employee__user').order_by('-requested_at')

        pending_wfh_count = pending_wfh_qs.count()
        pending_wfh_items = [
            {
                'id': w.id,
                'employee_id': w.employee_id,
                'employee_name': f"{w.employee.user.first_name} {w.employee.user.last_name}".strip() or w.employee.user.email,
                'start_at': w.start_at.isoformat(),
                'end_at': w.end_at.isoformat(),
                'reason': w.reason,
                'requested_at': w.requested_at.isoformat(),
            }
            for w in pending_wfh_qs[:5]
        ]

        return {
            'direct_reports_count': direct_reports_count,
            'attendance_today': {
                'present': present_count,
                'half_day': half_day_count,
                'absent': absent_count,
                'on_leave': on_leave_count,
                'on_wfh': on_wfh_count,
                'on_break': on_break_count,
            },
            'pending_approvals': {
                'leaves_count': pending_leaves_count,
                'wfh_count': pending_wfh_count,
                'leaves': pending_leaves_items,
                'wfh': pending_wfh_items,
            },
        }

    @classmethod
    def get_organization_data(cls, user, today, branch_id=None):
        """
        Aggregates organizational metrics.
        Gated by dynamic RBAC permissions:
        - employee.view -> workforce overview, department/branch breakdowns, recent hires
        - attendance.view_all -> org-wide attendance pulse
        - leave.view / wfh.view -> org-wide pending approvals counts

        Safely returns None if user has no organization context or lacks all permissions.
        """
        if not hasattr(user, 'employee') or not user.employee or not user.employee.organization_id:
            return None

        org_id = user.employee.organization_id

        emp_branches = AuthorizationService.get_authorized_branches(user, 'employee.view')
        att_branches = AuthorizationService.get_authorized_branches(user, 'attendance.view_all')
        leave_branches = AuthorizationService.get_authorized_branches(user, 'leave.view')
        wfh_branches = AuthorizationService.get_authorized_branches(user, 'wfh.view')

        has_emp_view = emp_branches.exists()
        has_att_view = att_branches.exists()
        has_leave_view = leave_branches.exists()
        has_wfh_view = wfh_branches.exists()

        if not (has_emp_view or has_att_view or has_leave_view or has_wfh_view):
            return None

        def filter_branches(allowed_branches):
            if not allowed_branches:
                return []
            if branch_id:
                return allowed_branches.filter(id=int(branch_id))
            return allowed_branches

        org_data = {}

        # 1. Workforce breakdown (employee.view)
        if has_emp_view:
            emp_qs = Employee.objects.filter(branch__in=filter_branches(emp_branches))
            total_active = emp_qs.filter(employment_status='active', user__status='active').count()
            total_onboarding = emp_qs.filter(employment_status='onboarding').count()
            total_on_notice = emp_qs.filter(employment_status='on_notice').count()

            by_department = list(
                emp_qs.filter(employment_status='active', department__isnull=False)
                .values(name=F('department__name'))
                .annotate(count=Count('id'))
                .order_by('-count')
            )

            by_branch = list(
                emp_qs.filter(employment_status='active', branch__isnull=False)
                .values(name=F('branch__name'))
                .annotate(count=Count('id'))
                .order_by('-count')
            )

            recent_hires = [
                {
                    'id': e.id,
                    'name': f"{e.user.first_name} {e.user.last_name}".strip() or e.user.email,
                    'department': e.department.name if e.department else None,
                    'designation': e.designation.name if e.designation else None,
                    'joining_date': str(e.joining_date) if e.joining_date else None,
                }
                for e in emp_qs.filter(user__status='active')
                .select_related('user', 'department', 'designation')
                .order_by('-joining_date', '-id')[:5]
            ]

            org_data['workforce'] = {
                'total_active': total_active,
                'total_onboarding': total_onboarding,
                'total_on_notice': total_on_notice,
                'by_department': by_department,
                'by_branch': by_branch,
                'recent_hires': recent_hires,
            }

        # 2. Org-wide attendance pulse (attendance.view_all)
        if has_att_view:
            emp_active_count = Employee.objects.filter(
                branch__in=filter_branches(att_branches),
                employment_status='active',
                user__status='active'
            ).count()

            org_att = Attendance.objects.filter(
                employee__branch__in=filter_branches(att_branches),
                employee__employment_status='active',
                employee__user__status='active',
                date=today
            )
            present_emp_ids = set(org_att.filter(status='present').values_list('employee_id', flat=True))
            half_day_emp_ids = set(org_att.filter(status='half_day').values_list('employee_id', flat=True))
            on_break_count = org_att.filter(breaks__ended_at__isnull=True).distinct().count()

            now = timezone.now()
            leave_emp_ids = set(LeaveRequest.objects.filter(
                employee__branch__in=filter_branches(att_branches),
                employee__employment_status='active',
                employee__user__status='active',
                status='approved',
                start_date__lte=today,
                end_date__gte=today
            ).values_list('employee_id', flat=True))

            # Disjoint state resolution:
            # If an employee attended (present or half_day), their actual presence takes precedence
            # over a scheduled leave, avoiding double-counting in workforce states.
            effective_on_leave_ids = leave_emp_ids - present_emp_ids - half_day_emp_ids
            on_leave_count = len(effective_on_leave_ids)
            present_count = len(present_emp_ids)
            half_day_count = len(half_day_emp_ids)

            on_wfh_count = WFHRequest.objects.filter(
                employee__branch__in=filter_branches(att_branches),
                employee__employment_status='active',
                employee__user__status='active',
                status='approved',
                start_at__lte=now,
                end_at__gte=now
            ).count()

            absent_count = max(0, emp_active_count - (present_count + half_day_count + on_leave_count))

            # Net Scheduled Attendance Rate:
            # expected_working = active workforce - approved leave
            # effective_present = present + (half_day * 0.5)
            # percentage = effective_present / expected_working * 100
            expected_working = max(0, emp_active_count - on_leave_count)
            effective_present = present_count + (half_day_count * 0.5)
            attendance_pct = (
                round((effective_present / expected_working) * 100, 1)
                if expected_working > 0
                else 0.0
            )

            org_data['attendance_today'] = {
                'expected_total': emp_active_count,
                'expected_working': expected_working,
                'present': present_count,
                'half_day': half_day_count,
                'absent': absent_count,
                'on_leave': on_leave_count,
                'on_wfh': on_wfh_count,
                'on_break': on_break_count,
                'attendance_percentage': attendance_pct,
            }

        # 3. Org-wide pending approvals summary (leave.view / wfh.view)
        if has_leave_view or has_wfh_view:
            pending_summary = {}
            if has_leave_view:
                pending_summary['leaves_count'] = LeaveRequest.objects.filter(
                    employee__branch__in=filter_branches(leave_branches),
                    status='pending'
                ).count()
            if has_wfh_view:
                pending_summary['wfh_count'] = WFHRequest.objects.filter(
                    employee__branch__in=filter_branches(wfh_branches),
                    status='pending'
                ).count()
            org_data['pending_approvals'] = pending_summary

        return org_data


class DashboardTrendsService:
    """
    Computes batched historical trends for Dashboard V2:
    - 7-day attendance trend (Net Scheduled Attendance Rate, present, half-day, on_leave, absent, on_wfh, weekends/holidays)
    - 6-month workforce trend (monthly active headcounts, new hires, exits, net growth, turnover rate)
    """

    @classmethod
    def get_trends(cls, user, window: str, branch_id=None):
        """
        Main entry point for historical trends.
        Gated by organization isolation and granular dynamic RBAC permissions:
        - window='7d': requires attendance.view_all
        - window='6m': requires employee.view
        Raises PermissionDenied (HTTP 403) if a requested branch_id is unauthorized.
        """
        if branch_id:
            try:
                b_id = int(branch_id)
            except (ValueError, TypeError):
                raise PermissionDenied("You do not have permission to access this branch.")

            if window == '7d':
                att_branches = AuthorizationService.get_authorized_branches(user, 'attendance.view_all')
                if not att_branches.filter(id=b_id).exists():
                    raise PermissionDenied("You do not have permission to access attendance trends for this branch.")
            elif window == '6m':
                emp_branches = AuthorizationService.get_authorized_branches(user, 'employee.view')
                if not emp_branches.filter(id=b_id).exists():
                    raise PermissionDenied("You do not have permission to access workforce trends for this branch.")

        if not hasattr(user, 'employee') or not user.employee or not user.employee.organization_id:
            return {
                'window': window,
                'attendance_trend': None,
                'workforce_trend': None,
            }

        org_id = user.employee.organization_id
        today = timezone.localdate()

        has_att_view = AuthorizationService.has_permission(user, 'attendance.view_all')
        has_emp_view = AuthorizationService.has_permission(user, 'employee.view')

        attendance_trend = None
        workforce_trend = None

        if window == '7d':
            if has_att_view:
                attendance_trend = cls.get_7d_attendance_trend(org_id, today, branch_id, user)
        elif window == '6m':
            if has_emp_view:
                workforce_trend = cls.get_6m_workforce_trend(org_id, today, branch_id, user)

        return {
            'window': window,
            'attendance_trend': attendance_trend,
            'workforce_trend': workforce_trend,
        }

    @staticmethod
    def _get_join_date(emp: dict) -> date | None:
        join_d = emp.get('joining_date')
        if not join_d and emp.get('created_at'):
            join_d = emp['created_at'].date()
        return join_d

    @classmethod
    def _is_employee_active_on_date(cls, emp: dict, d: date) -> bool:
        """
        Determines if an employee is part of the active workforce on calendar day d.
        Uses joining_date and exit_date boundaries.
        Fallback to created_at date if joining_date is null.
        """
        join_d = cls._get_join_date(emp)
        if not join_d or join_d > d:
            return False

        exit_d = emp.get('exit_date')
        if exit_d and exit_d <= d:
            return False

        if not exit_d:
            status = emp.get('employment_status')
            user_status = emp.get('user__status')
            if status in ('inactive', 'exited') or user_status == 'inactive':
                return False

        return True


    @classmethod
    def get_7d_attendance_trend(cls, org_id: int, today: date, branch_id, user):
        """
        Calculates 7-day attendance trend ending on today.
        Batches data collection into 5 indexed queries (zero N+1 queries).
        """
        start_date = today - timedelta(days=6)
        end_date = today

        att_branches = AuthorizationService.get_authorized_branches(user, 'attendance.view_all')
        if branch_id:
            att_branches = att_branches.filter(id=branch_id)

        # 1. Employees query (batch)
        employees_list = list(
            Employee.objects.filter(
                branch__in=att_branches
            ).filter(
                Q(exit_date__isnull=True) | Q(exit_date__gte=start_date)
            ).filter(
                Q(joining_date__isnull=True) | Q(joining_date__lte=end_date)
            ).values('id', 'joining_date', 'exit_date', 'employment_status', 'user__status', 'created_at')
        )

        # 2. Attendance records query (batch)
        att_records = Attendance.objects.filter(
            employee__branch__in=att_branches,
            date__range=(start_date, end_date)
        ).values('employee_id', 'date', 'status')
        att_map = {(r['date'], r['employee_id']): r['status'] for r in att_records}

        # 3. Approved leaves query (batch)
        leaves_list = list(
            LeaveRequest.objects.filter(
                employee__branch__in=att_branches,
                status='approved',
                start_date__lte=end_date,
                end_date__gte=start_date
            ).values('employee_id', 'start_date', 'end_date')
        )

        # 4. Holidays query (batch)
        holidays_set = set(
            Holiday.objects.filter(
                branch__in=att_branches,
                is_active=True,
                date__range=(start_date, end_date)
            ).values_list('date', flat=True)
        )

        # 5. Approved WFH query (batch)
        wfh_records = list(
            WFHRequest.objects.filter(
                employee__branch__in=att_branches,
                status='approved',
                start_at__date__lte=end_date,
                end_at__date__gte=start_date
            ).values('employee_id', 'start_at', 'end_at')
        )

        trend_items = []
        for i in range(7):
            d = start_date + timedelta(days=i)
            is_weekend = d.weekday() >= 5
            is_holiday = d in holidays_set
            is_working_day = not (is_weekend or is_holiday)

            active_emp_ids = {
                emp['id'] for emp in employees_list
                if cls._is_employee_active_on_date(emp, d)
            }
            active_count = len(active_emp_ids)

            if not is_working_day:
                present_count = sum(1 for emp_id in active_emp_ids if att_map.get((d, emp_id)) == 'present')
                half_day_count = sum(1 for emp_id in active_emp_ids if att_map.get((d, emp_id)) == 'half_day')
                trend_items.append({
                    'date': str(d),
                    'day_name': d.strftime('%A'),
                    'is_working_day': False,
                    'expected_total': active_count,
                    'expected_working': 0,
                    'present': present_count,
                    'half_day': half_day_count,
                    'absent': 0,
                    'on_leave': 0,
                    'on_wfh': 0,
                    'attendance_percentage': None,
                })
            else:
                present_ids = {emp_id for emp_id in active_emp_ids if att_map.get((d, emp_id)) == 'present'}
                half_day_ids = {emp_id for emp_id in active_emp_ids if att_map.get((d, emp_id)) == 'half_day'}

                raw_leave_ids = {
                    l['employee_id'] for l in leaves_list
                    if l['employee_id'] in active_emp_ids and l['start_date'] <= d <= l['end_date']
                }

                # Attendance presence takes precedence over scheduled leave
                effective_leave_ids = raw_leave_ids - present_ids - half_day_ids

                present_count = len(present_ids)
                half_day_count = len(half_day_ids)
                on_leave_count = len(effective_leave_ids)

                absent_count = max(0, active_count - (present_count + half_day_count + on_leave_count))
                expected_working = max(0, active_count - on_leave_count)
                effective_present = present_count + (half_day_count * 0.5)

                attendance_pct = (
                    round((effective_present / expected_working) * 100, 1)
                    if expected_working > 0
                    else 0.0
                )

                # Approved WFH is an overlay
                wfh_ids = {
                    w['employee_id'] for w in wfh_records
                    if w['employee_id'] in active_emp_ids and w['start_at'].date() <= d <= w['end_at'].date()
                }
                on_wfh_count = len(wfh_ids)

                trend_items.append({
                    'date': str(d),
                    'day_name': d.strftime('%A'),
                    'is_working_day': True,
                    'expected_total': active_count,
                    'expected_working': expected_working,
                    'present': present_count,
                    'half_day': half_day_count,
                    'absent': absent_count,
                    'on_leave': on_leave_count,
                    'on_wfh': on_wfh_count,
                    'attendance_percentage': attendance_pct,
                })

        return trend_items

    @classmethod
    def get_6m_workforce_trend(cls, org_id: int, today: date, branch_id, user):
        """
        Calculates 6-month workforce and headcount trend ending in current month.
        Single batched query for all employee records (zero N+1 queries).
        """
        emp_branches = AuthorizationService.get_authorized_branches(user, 'employee.view')
        if branch_id:
            emp_branches = emp_branches.filter(id=branch_id)

        employees_list = list(
            Employee.objects.filter(
                branch__in=emp_branches
            ).values('id', 'joining_date', 'exit_date', 'employment_status', 'user__status', 'created_at')
        )

        workforce_items = []
        # Calculate 6 calendar months in chronological order
        for i in range(5, -1, -1):
            total_months = today.year * 12 + (today.month - 1) - i
            y = total_months // 12
            m = (total_months % 12) + 1

            start_date = date(y, m, 1)
            days_in_month = calendar.monthrange(y, m)[1]
            calendar_end = date(y, m, days_in_month)
            point_in_time_end = calendar_end if (y, m) != (today.year, today.month) else today

            # Starting headcount: active prior to start of month
            start_headcount = sum(
                1 for emp in employees_list
                if cls._get_join_date(emp) is not None
                and cls._get_join_date(emp) < start_date
                and (emp.get('exit_date') is None or emp['exit_date'] >= start_date)
            )

            # Ending headcount: active at end of month (or point in time today)
            end_headcount = sum(
                1 for emp in employees_list
                if cls._is_employee_active_on_date(emp, point_in_time_end)
            )

            # New hires in this period (up to point_in_time_end)
            new_hires = sum(
                1 for emp in employees_list
                if cls._get_join_date(emp) is not None
                and start_date <= cls._get_join_date(emp) <= point_in_time_end
            )

            # Exits in this period (up to point_in_time_end)
            exits = sum(
                1 for emp in employees_list
                if emp.get('exit_date')
                and start_date <= emp['exit_date'] <= point_in_time_end
            )


            net_growth = new_hires - exits

            avg_headcount = (start_headcount + end_headcount) / 2.0
            turnover_rate = (
                round((exits / avg_headcount) * 100, 1)
                if avg_headcount > 0
                else 0.0
            )

            workforce_items.append({
                'period': f"{y}-{m:02d}",
                'year': y,
                'month': m,
                'month_name': calendar.month_name[m],
                'start_headcount': start_headcount,
                'end_headcount': end_headcount,
                'new_hires': new_hires,
                'exits': exits,
                'net_growth': net_growth,
                'turnover_rate': turnover_rate,
            })

        return workforce_items

