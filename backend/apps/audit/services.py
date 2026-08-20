import logging
from django.utils import timezone
from .models import AuditLog

logger = logging.getLogger(__name__)

class AuditService:
    @staticmethod
    def log(action, actor=None, target_type='', target_id='', metadata=None, request=None):
        try:
            ip_address = None
            if request:
                ip_address = request.META.get('REMOTE_ADDR')
            
            AuditLog.objects.create(
                actor=actor,
                action=action,
                target_type=target_type,
                target_id=str(target_id),
                metadata=metadata or {},
                ip_address=ip_address
            )
        except Exception as e:
            logger.error(f"Failed to create audit log for {action}: {str(e)}")
