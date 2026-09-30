from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class NotificationService:
    @staticmethod
    def send_tenant_owner_verification_email(recipient_email, first_name, uid, token):
        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')
        activation_link = f"{frontend_url}/activate?uid={uid}&token={token}"
        try:
            send_mail(
                'Verify your BeyondSure HRMS account',
                f"Hello {first_name},\n\nVerify your email and set your password to start your organization setup:\n{activation_link}\n\nDo not share this link.",
                settings.DEFAULT_FROM_EMAIL,
                [recipient_email],
                fail_silently=False,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send tenant owner verification email to {recipient_email}: {str(e)}")
            return False

    @staticmethod
    def send_employee_onboarding_email(recipient_email, first_name, employee_code, uid, token):
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
                [recipient_email],
                fail_silently=False,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send onboarding email to {recipient_email}: {str(e)}")
            return False

    @staticmethod
    def send_candidate_offer_email(candidate_email, candidate_name, organization_name, offer_letter_body, onboarding_link):
        """Send offer letter and onboarding portal access link to a candidate."""
        subject = f'Your Offer Letter from {organization_name}'
        message = (
            f"Dear {candidate_name},\n\n"
            f"We are pleased to extend you an offer to join {organization_name}.\n\n"
            f"--- OFFER LETTER ---\n\n"
            f"{offer_letter_body}\n\n"
            f"--- END OF OFFER LETTER ---\n\n"
            f"To complete your onboarding, please click the link below to activate your account "
            f"and access the onboarding portal:\n"
            f"{onboarding_link}\n\n"
            f"Please do not share this link with anyone. It will expire shortly.\n\n"
            f"Regards,\nHR Team – {organization_name}"
        )
        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [candidate_email],
                fail_silently=False,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send candidate offer email to {candidate_email}: {str(e)}")
            return False


    @staticmethod
    def send_password_reset_email(email, first_name, uid, token):
        subject = 'HRMS - Password Reset Request'
        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')
        reset_link = f"{frontend_url}/reset-password?uid={uid}&token={token}"

        message = (
            f"Hello {first_name},\n\n"
            f"We received a request to reset the password for your HRMS account.\n\n"
            f"To reset your password, please click the link below:\n"
            f"{reset_link}\n\n"
            f"If you did not request this, please ignore this email. This link will expire shortly.\n\n"
            f"Regards,\nHR Team"
        )

        try:
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send password reset email to {email}: {str(e)}")
            return False

    @staticmethod
    def create_in_app_notification(recipient, organization, notification_type, title, message, reference_id=''):
        from .models import Notification
        
        # Validation
        if not recipient or not organization:
            logger.error("Failed to create in-app notification: recipient and organization are required.")
            return None
            
        try:
            notification = Notification.objects.create(
                recipient=recipient,
                organization=organization,
                notification_type=notification_type,
                title=title,
                message=message,
                reference_id=reference_id
            )
            return notification
        except Exception as e:
            logger.error(f"Failed to create in-app notification for {getattr(recipient, 'email', 'Unknown')}: {str(e)}")
            # Do not raise the exception so business flows are not interrupted
            return None
