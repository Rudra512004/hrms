import ipaddress
from django.utils import timezone
from apps.organization.models import OfficeNetwork
from apps.employees.models import WFHRequest

class NetworkAccessService:
    @staticmethod
    def get_client_ip(request):
        # Do NOT blindly trust X-Forwarded-For from an arbitrary client.
        # For direct requests, use the appropriate server-derived address.
        return request.META.get('REMOTE_ADDR')

    @staticmethod
    def is_office_network_allowed(ip_address, organization=None):
        if not ip_address:
            return False
        try:
            client_ip = ipaddress.ip_address(ip_address)
        except ValueError:
            return False

        qs = OfficeNetwork.objects.filter(is_active=True)
        if organization:
            qs = qs.filter(organization=organization)

        for office_net in qs:
            try:
                network = ipaddress.ip_network(office_net.network, strict=False)
                if client_ip in network:
                    return True
            except ValueError:
                continue
        return False

    @staticmethod
    def is_wfh_active(employee):
        if not employee:
            return False
        now = timezone.now()
        return WFHRequest.objects.filter(
            employee=employee,
            status='approved',
            start_at__lte=now,
            end_at__gte=now
        ).exists()

    @staticmethod
    def is_remote_access_allowed(request, user):
        if not user.is_authenticated or not user.is_active:
            return False

        if getattr(user, 'is_superuser', False):
            return True

        ip = NetworkAccessService.get_client_ip(request)
        employee = getattr(user, 'employee', None)

        if NetworkAccessService.is_office_network_allowed(ip):
            return True

        if employee and NetworkAccessService.is_wfh_active(employee):
            return True

        return False
