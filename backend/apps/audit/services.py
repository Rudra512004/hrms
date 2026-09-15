import logging
from django.utils import timezone
from .models import AuditLog

logger = logging.getLogger(__name__)

class AuditService:
    @staticmethod
    def log(action, actor=None, target_type='', target_id='', metadata=None, request=None, organization=None):
        try:
            ip_address = None
            if request:
                x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
                if x_forwarded_for:
                    ip_address = x_forwarded_for.split(',')[0].strip()
                else:
                    ip_address = request.META.get('REMOTE_ADDR')
            
            org = organization
            if org is None:
                if request and hasattr(request, 'user') and getattr(request.user, 'is_authenticated', False):
                    emp = getattr(request.user, 'employee', None)
                    if emp and emp.organization_id:
                        org = emp.organization
                if org is None and actor and getattr(actor, 'is_authenticated', False):
                    emp = getattr(actor, 'employee', None)
                    if emp and emp.organization_id:
                        org = emp.organization

            AuditLog.objects.create(
                organization=org,
                actor=actor,
                action=action,
                target_type=target_type,
                target_id=str(target_id),
                metadata=metadata or {},
                ip_address=ip_address
            )
        except Exception as e:
            logger.error(f"Failed to create audit log for {action}: {str(e)}")
