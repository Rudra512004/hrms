from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from apps.authorization.permissions import require_permission
from apps.authorization.services import AuthorizationService
from apps.audit.services import AuditService
from apps.organization.context import get_current_employee
from .models import ReviewCycle,PerformanceReview
from .serializers import ReviewCycleSerializer,PerformanceReviewSerializer
class ReviewCycleViewSet(viewsets.ModelViewSet):
 serializer_class=ReviewCycleSerializer
 def get_permissions(self):return [IsAuthenticated(),require_permission('employee.view' if self.action in ['list','retrieve'] else 'employee.update')()]
 def get_queryset(self):
  u=self.request.user
  if u.is_superuser:return ReviewCycle.objects.all()
  try: e=get_current_employee(self.request)
  except Exception: e=None
  return ReviewCycle.objects.filter(organization=e.organization) if e and e.organization_id else ReviewCycle.objects.none()
 def perform_create(self,s):
  try: e=get_current_employee(self.request)
  except Exception: e=None
  if not e:raise ValidationError({'organization':'Organization context required.'})
  x=s.save(organization=e.organization);AuditService.log('review_cycle_created',self.request.user,'review_cycle',x.id,request=self.request,organization=e.organization)
class PerformanceReviewViewSet(viewsets.ModelViewSet):
 serializer_class=PerformanceReviewSerializer
 def get_queryset(self):
  u=self.request.user
  if u.is_superuser:return PerformanceReview.objects.all().select_related('employee__user','reviewer__user')
  try: e=get_current_employee(self.request)
  except Exception: e=None
  if not e:return PerformanceReview.objects.none()
  # Employees see their own review. People administrators can also act on
  # direct reports, but never on another organization's review records.
  qs=PerformanceReview.objects.filter(employee__organization=e.organization).select_related('employee__user','reviewer__user')
  if AuthorizationService.has_permission(u,'employee.update'):
   return qs.filter(employee=e) | qs.filter(employee__reporting_manager=e)
  return qs.filter(employee=e)
 def get_permissions(self):
  permission='employee.view' if self.action in ['list','retrieve','acknowledge'] else 'employee.update'
  return [IsAuthenticated(),require_permission(permission)()]
 def perform_create(self,s):
  try: e=get_current_employee(self.request)
  except Exception: e=None
  employee=s.validated_data['employee']
  if not self.request.user.is_superuser:
   if not e or employee.organization_id!=e.organization_id:raise ValidationError({'employee':'Employee must be in your organization.'})
   if employee.id!=e.id and employee.reporting_manager_id!=e.id:raise ValidationError({'employee':'You can create reviews only for yourself or your direct reports.'})
  x=s.save(reviewer=e);AuditService.log('performance_review_created',self.request.user,'performance_review',x.id,request=self.request,organization=employee.organization)
 @action(detail=True,methods=['post'])
 def submit(self,request,pk=None):
  x=self.get_object()
  try: e=get_current_employee(request)
  except Exception: e=None
  if not e or x.reviewer_id!=e.id:raise ValidationError({'detail':'Only the assigned reviewer can submit this review.'})
  if x.status!='draft':raise ValidationError({'detail':'Only draft reviews can be submitted.'})
  x.status='submitted';x.submitted_at=timezone.now();x.save();AuditService.log('performance_review_submitted',request.user,'performance_review',x.id,request=request,organization=x.employee.organization);return Response(self.get_serializer(x).data)
 @action(detail=True,methods=['post'])
 def acknowledge(self,request,pk=None):
  x=self.get_object();
  try: e=get_current_employee(request)
  except Exception: e=None
  if not e or x.employee_id!=e.id:raise ValidationError({'detail':'Only the reviewed employee can acknowledge.'})
  if x.status!='submitted':raise ValidationError({'detail':'Only submitted reviews can be acknowledged.'})
  x.status='acknowledged';x.save();AuditService.log('performance_review_acknowledged',request.user,'performance_review',x.id,request=request,organization=x.employee.organization);return Response(self.get_serializer(x).data)
