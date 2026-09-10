from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Notification
from .serializers import NotificationSerializer

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
