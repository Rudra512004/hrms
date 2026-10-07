from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from apps.authorization.permissions import require_permission
from apps.authorization.services import AuthorizationService
from apps.audit.services import AuditService
from .models import ReviewCycle,PerformanceReview
from .serializers import ReviewCycleSerializer,PerformanceReviewSerializer
class ReviewCycleViewSet(viewsets.ModelViewSet):
 serializer_class=ReviewCycleSerializer
 def get_permissions(self):return [IsAuthenticated(),require_permission('employee.view' if self.action in ['list','retrieve'] else 'employee.update')()]
 def get_queryset(self):
  u=self.request.user
  org = AuthorizationService.get_primary_organization(u)
  return ReviewCycle.objects.filter(organization=org) if org else ReviewCycle.objects.none()
 def perform_create(self,s):
  org = AuthorizationService.get_primary_organization(self.request.user)
  if not org:raise ValidationError({'organization':'Organization context required.'})
  x=s.save(organization=org);AuditService.log('review_cycle_created',self.request.user,'review_cycle',x.id,request=self.request,organization=org)
class PerformanceReviewViewSet(viewsets.ModelViewSet):
 serializer_class=PerformanceReviewSerializer
 def get_queryset(self):
  u=self.request.user
  org = AuthorizationService.get_primary_organization(u)
  if not org:return PerformanceReview.objects.none()
  # Employees see their own review. People administrators can also act on
  # direct reports, but never on another organization's review records.
  qs=PerformanceReview.objects.filter(employee__organization=org).select_related('employee__user','reviewer__user')
  if AuthorizationService.has_permission(u,'employee.update'):
   return qs.filter(employee=e) | qs.filter(employee__reporting_manager=e)
  return qs.filter(employee=e)
 def get_permissions(self):
  permission='employee.view' if self.action in ['list','retrieve','acknowledge'] else 'employee.update'
  return [IsAuthenticated(),require_permission(permission)()]
 def perform_create(self,s):
  e=getattr(self.request.user,'employee',None); employee=s.validated_data['employee']
  org = AuthorizationService.get_primary_organization(self.request.user)
  if not org or employee.organization_id!=org.id:raise ValidationError({'employee':'Employee must be in your organization.'})
  if not e or (employee.id!=e.id and employee.reporting_manager_id!=e.id):
   if not AuthorizationService.has_permission(self.request.user, 'employee.update', global_only=True):
    raise ValidationError({'employee':'You can create reviews only for yourself or your direct reports.'})
  x=s.save(reviewer=e);AuditService.log('performance_review_created',self.request.user,'performance_review',x.id,request=self.request,organization=employee.organization)
 @action(detail=True,methods=['post'])
 def submit(self,request,pk=None):
  x=self.get_object()
  if not getattr(request.user,'employee',None) or x.reviewer_id!=request.user.employee.id:raise ValidationError({'detail':'Only the assigned reviewer can submit this review.'})
  if x.status!='draft':raise ValidationError({'detail':'Only draft reviews can be submitted.'})
  x.status='submitted';x.submitted_at=timezone.now();x.save();AuditService.log('performance_review_submitted',request.user,'performance_review',x.id,request=request,organization=x.employee.organization);return Response(self.get_serializer(x).data)
 @action(detail=True,methods=['post'])
 def acknowledge(self,request,pk=None):
  x=self.get_object();
  if not hasattr(request.user,'employee') or x.employee_id!=request.user.employee.id:raise ValidationError({'detail':'Only the reviewed employee can acknowledge.'})
  if x.status!='submitted':raise ValidationError({'detail':'Only submitted reviews can be acknowledged.'})
  x.status='acknowledged';x.save();AuditService.log('performance_review_acknowledged',request.user,'performance_review',x.id,request=request,organization=x.employee.organization);return Response(self.get_serializer(x).data)
