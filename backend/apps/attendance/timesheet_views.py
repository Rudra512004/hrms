from datetime import date,timedelta
from django.utils import timezone
from rest_framework import viewsets,status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError,PermissionDenied
from apps.authorization.permissions import require_permission
from apps.authorization.services import AuthorizationService
from apps.audit.services import AuditService
from .models import TimesheetPolicy,Project,Timesheet,TimeEntry
from .serializers import TimesheetPolicySerializer,ProjectSerializer,TimesheetSerializer,TimeEntrySerializer

def org(user):
 e=getattr(user,'employee',None); return e.organization if e and e.organization_id else None
class TimesheetPolicyViewSet(viewsets.GenericViewSet):
 serializer_class=TimesheetPolicySerializer
 def get_permissions(self):return [IsAuthenticated(),require_permission('attendance.view_all' if self.action in ['retrieve','current'] and self.request.method=='GET' else 'shift.manage')()]
 def retrieve(self,request,pk=None):
  o=org(request.user)
  if request.user.is_superuser and pk: from apps.organization.models import Organization; o=Organization.objects.get(pk=pk)
  if not o: raise ValidationError({'organization':'Organization context is required.'})
  policy,_=TimesheetPolicy.objects.get_or_create(organization=o);return Response(self.get_serializer(policy).data)
 def update(self,request,pk=None):
  o=org(request.user)
  if not o: raise ValidationError({'organization':'Organization context is required.'})
  policy,_=TimesheetPolicy.objects.get_or_create(organization=o);s=self.get_serializer(policy,data=request.data,partial=True);s.is_valid(raise_exception=True);s.save();AuditService.log('timesheet_policy_updated',request.user,'timesheet_policy',policy.id,{'fields':sorted(s.validated_data)},request,o);return Response(s.data)
 partial_update=update
 @action(detail=False,methods=['get','patch'],url_path='current')
 def current(self,request):
  o=org(request.user)
  if not o:raise ValidationError({'organization':'Organization context is required.'})
  policy,_=TimesheetPolicy.objects.get_or_create(organization=o)
  if request.method=='GET':return Response(self.get_serializer(policy).data)
  s=self.get_serializer(policy,data=request.data,partial=True);s.is_valid(raise_exception=True);s.save()
  AuditService.log('timesheet_policy_updated',request.user,'timesheet_policy',policy.id,{'fields':sorted(s.validated_data)},request,o)
  return Response(s.data)
class ProjectViewSet(viewsets.ModelViewSet):
 serializer_class=ProjectSerializer
 def get_permissions(self):
  # Project names/codes are required by employee time entry. Writes remain
  # restricted to scheduling administrators.
  return [IsAuthenticated()] if self.action in ['list','retrieve'] else [IsAuthenticated(),require_permission('shift.manage')()]
 def get_queryset(self):
  return Project.objects.all() if self.request.user.is_superuser else Project.objects.filter(organization=org(self.request.user))
 def perform_create(self,s):
  o=org(self.request.user)
  if not o:raise ValidationError({'organization':'Organization context is required.'})
  x=s.save(organization=o);AuditService.log('project_created',self.request.user,'project',x.id,request=self.request,organization=o)
class TimesheetViewSet(viewsets.ModelViewSet):
 serializer_class=TimesheetSerializer
 def get_queryset(self):
  u=self.request.user
  if u.is_superuser:return Timesheet.objects.all().select_related('employee__user')
  e=getattr(u,'employee',None)
  if not e:return Timesheet.objects.none()
  scoped=Timesheet.objects.filter(employee__organization=e.organization).select_related('employee__user').prefetch_related('entries__project')
  if AuthorizationService.has_permission(u,'attendance.view_all'):
   return scoped
  return scoped.filter(employee=e)
 def create(self,request,*a,**k):
  e=getattr(request.user,'employee',None)
  if not e:raise ValidationError({'employee':'Employee profile required.'})
  organization=org(request.user)
  if not organization:raise ValidationError({'organization':'Organization context is required.'})
  p,_=TimesheetPolicy.objects.get_or_create(organization=organization)
  start=date.fromisoformat(request.data.get('period_start',str(date.today())));end=start if p.cadence=='daily' else start+timedelta(days=6)
  x,_=Timesheet.objects.get_or_create(employee=e,period_start=start,period_end=end);return Response(self.get_serializer(x).data,status=201)
 @action(detail=True,methods=['post'])
 def submit(self,request,pk=None):
  x=self.get_object();
  if x.status!='draft':raise ValidationError({'detail':'Only draft timesheets can be submitted.'})
  if not x.entries.exists():raise ValidationError({'detail':'Add at least one time entry before submission.'})
  policy,_=TimesheetPolicy.objects.get_or_create(organization=x.employee.organization)
  x.status='submitted' if policy.requires_manager_approval else 'approved';x.submitted_at=timezone.now();x.save()
  action_name='timesheet_submitted' if policy.requires_manager_approval else 'timesheet_auto_approved'
  AuditService.log(action_name,request.user,'timesheet',x.id,request=request,organization=org(request.user));return Response(self.get_serializer(x).data)
 @action(detail=True,methods=['post'])
 def review(self,request,pk=None):
  if not require_permission('attendance.view_all')().has_permission(request,self):raise PermissionDenied()
  qs=Timesheet.objects.select_related('employee__user','employee__organization')
  if not request.user.is_superuser:
   organization=org(request.user)
   if not organization:raise PermissionDenied()
   qs=qs.filter(employee__organization=organization)
  try:x=qs.get(pk=pk)
  except Timesheet.DoesNotExist:raise ValidationError({'detail':'Timesheet not found in your organization.'})
  decision=request.data.get('decision');
  if decision not in ['approved','rejected','reopened']:raise ValidationError({'decision':'Use approved, rejected, or reopened.'})
  policy,_=TimesheetPolicy.objects.get_or_create(organization=x.employee.organization)
  if decision=='reopened' and not policy.manager_can_reopen:raise ValidationError({'decision':'This organization does not allow managers to reopen timesheets.'})
  if decision!='reopened' and x.status!='submitted':raise ValidationError({'detail':'Only submitted timesheets can be approved or rejected.'})
  x.status='draft' if decision=='reopened' else decision;x.reviewed_by=request.user;x.reviewed_at=timezone.now();x.reviewer_comment=request.data.get('comment','');x.save();AuditService.log('timesheet_'+decision,request.user,'timesheet',x.id,request=request,organization=x.employee.organization);return Response(self.get_serializer(x).data)
 @action(detail=True,methods=['post'],url_path='entries')
 def add_entry(self,request,pk=None):
  x=self.get_object()
  policy,_=TimesheetPolicy.objects.get_or_create(organization=x.employee.organization)
  if x.status!='draft' and (x.status!='submitted' or policy.lock_on_submit):raise ValidationError({'detail':'This timesheet is locked for editing.'})
  s=TimeEntrySerializer(data=request.data);s.is_valid(raise_exception=True);project=s.validated_data['project']
  if project.organization_id!=x.employee.organization_id:raise ValidationError({'project':'Project belongs to another organization.'})
  if not(x.period_start<=s.validated_data['work_date']<=x.period_end):raise ValidationError({'work_date':'Date is outside the timesheet period.'})
  entry=s.save(timesheet=x);return Response(TimeEntrySerializer(entry).data,status=201)
