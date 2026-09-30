from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Notification, Announcement
from .serializers import NotificationSerializer, AnnouncementSerializer
from apps.authorization.permissions import require_permission
from apps.audit.services import AuditService

class NotificationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    API endpoint that allows users to view and interact with their notifications.
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        
        # Follow existing project behavior: if user has no org context, return none.
        if not hasattr(user, 'employee') or not user.employee.organization_id:
            return Notification.objects.none()
            
        return Notification.objects.filter(
            recipient=user,
            organization_id=user.employee.organization_id
        )

    @action(detail=True, methods=['post'], url_path='read')
    def mark_read(self, request, pk=None):
        """Mark a single notification as read."""
        notification = self.get_object()
        
        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=['is_read'])
            
        return Response({'detail': 'Notification marked as read.'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='read-all')
    def mark_all_read(self, request):
        """Mark all unread notifications as read for the current user."""
        queryset = self.get_queryset().filter(is_read=False)
        updated_count = queryset.update(is_read=True)
        return Response(
            {'detail': f'Marked {updated_count} notifications as read.', 'updated_count': updated_count},
            status=status.HTTP_200_OK
        )

    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        """Get the count of unread notifications for the current user."""
        count = self.get_queryset().filter(is_read=False).count()
        return Response({'unread_count': count}, status=status.HTTP_200_OK)


class AnnouncementViewSet(viewsets.ModelViewSet):
    serializer_class = AnnouncementSerializer

    def get_permissions(self):
        permission = 'announcement.view' if self.action in ['list', 'retrieve'] else 'announcement.manage'
        return [IsAuthenticated(), require_permission(permission)()]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Announcement.objects.all()
        employee = getattr(user, 'employee', None)
        if not employee or not employee.organization_id:
            return Announcement.objects.none()
        queryset = Announcement.objects.filter(organization_id=employee.organization_id)
        if not self.request.user or not self.request.user.is_superuser:
            now = timezone.now()
            queryset = queryset.filter(Q(is_published=True), Q(expires_at__isnull=True) | Q(expires_at__gt=now))
            if employee.branch_id:
                queryset = queryset.filter(Q(branch__isnull=True) | Q(branch_id=employee.branch_id))
            else:
                queryset = queryset.filter(branch__isnull=True)
        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        employee = getattr(user, 'employee', None)
        organization = serializer.validated_data.get('organization') if user.is_superuser else getattr(employee, 'organization', None)
        if not organization:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'organization': 'Organization context is required.'})
        instance = serializer.save(
            organization=organization,
            created_by=user,
            published_at=timezone.now() if serializer.validated_data.get('is_published') else None,
        )
        AuditService.log('announcement_created', user, 'announcement', instance.id, {'published': instance.is_published}, self.request, organization)

    def perform_update(self, serializer):
        was_published = serializer.instance.is_published
        becomes_published = serializer.validated_data.get('is_published', was_published)
        instance = serializer.save(published_at=timezone.now() if becomes_published and not was_published else serializer.instance.published_at)
        AuditService.log('announcement_updated', self.request.user, 'announcement', instance.id, {'published': instance.is_published}, self.request, instance.organization)
