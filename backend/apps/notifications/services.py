from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class NotificationService:
    @staticmethod
    def send_employee_onboarding_email(personal_email, first_name, employee_code, uid, token):
        subject = 'Welcome to HRMS - Your account is ready'
        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')
        activation_link = f"{frontend_url}/activate?uid={uid}&token={token}"
        
        message = (
            f"Hello {first_name},\n\n"
            f"Welcome to the team! Your employee profile (Code: {employee_code}) has been created.\n\n"
            f"To activate your account and establish your password, please click the link below:\n"
            f"{activation_link}\n\n"
            f"Please note: For security reasons, do not share this link with anyone. "
            f"This activation link will expire shortly.\n\n"
            f"Regards,\nHR Team"
        )
        
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [personal_email],
                fail_silently=False,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send onboarding email to {personal_email}: {str(e)}")
            return False
