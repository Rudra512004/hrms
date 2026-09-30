from django.core.mail import EmailMultiAlternatives, send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class NotificationService:
    @staticmethod
    def send_announcement_email(announcement):
        """Optional broadcast: publication sends only when its event rule is enabled."""
        from apps.employees.models import Employee
        employees = Employee.objects.filter(organization=announcement.organization, user__status='active').select_related('user')
        from .models import EmailAutomationRule
        rule = EmailAutomationRule.objects.filter(
            organization=announcement.organization,
            event_type='announcement_published',
            is_active=True,
        ).order_by('id').first()
        if rule and rule.recipient_mode == 'organization_admins':
            employees = employees.filter(user__is_staff=True)
        if announcement.branch_id:
            employees = employees.filter(branch_id=announcement.branch_id)
        for employee in employees:
            NotificationService.send_automated_email(
                announcement.organization, 'announcement_published', employee.user.email,
                {'first_name': employee.user.first_name or 'Team member', 'title': announcement.title, 'body': announcement.body, 'organization_name': announcement.organization.name},
                '{title} — {organization_name}', 'Hello {first_name},\n\n{body}',
            )

    @staticmethod
    def send_automated_email(organization, event_type, recipient_email, context, fallback_subject, fallback_body, force=False):
        """Deliver an enabled, audited event email using an org template if present."""
        from .models import EmailAutomationRule, EmailDelivery, EmailTemplate, OrganizationEmailSettings
        settings_row, _ = OrganizationEmailSettings.objects.get_or_create(organization=organization)
        rule_enabled = EmailAutomationRule.objects.filter(organization=organization, event_type=event_type, is_active=True).exists()
        required_event = event_type in {'employee_onboarding', 'candidate_offer', 'password_reset'}
        if not force and not required_event and (not settings_row.automation_enabled or not rule_enabled):
            EmailDelivery.objects.create(organization=organization, event_type=event_type, recipient_email=recipient_email, subject=fallback_subject, status='suppressed', error_message='Automation is disabled or no active rule exists.')
            return False
        template = EmailTemplate.objects.filter(organization=organization, event_type=event_type, is_active=True).order_by('id').first() if settings_row.automation_enabled else None
        subject = (template.subject if template else fallback_subject).format(**context)
        body = (template.body if template else fallback_body).format(**context)
        from_email = settings_row.from_email or settings.DEFAULT_FROM_EMAIL
        if settings_row.sender_name:
            from_email = f'{settings_row.sender_name} <{from_email}>'
        try:
            message = EmailMultiAlternatives(subject, body, from_email, [recipient_email], reply_to=[settings_row.reply_to_email] if settings_row.reply_to_email else None)
            message.send(fail_silently=False)
            EmailDelivery.objects.create(organization=organization, event_type=event_type, recipient_email=recipient_email, subject=subject, status='sent')
            return True
        except Exception as exc:
            logger.error('Automated email failed for %s: %s', recipient_email, exc)
            EmailDelivery.objects.create(organization=organization, event_type=event_type, recipient_email=recipient_email, subject=subject, status='failed', error_message=str(exc)[:2000])
            return False

    @staticmethod
    def send_employee_onboarding_email(personal_email, first_name, employee_code, uid, token, organization=None):
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

        if organization:
            return NotificationService.send_automated_email(organization, 'employee_onboarding', personal_email, {'first_name': first_name, 'employee_code': employee_code, 'activation_link': activation_link}, subject, message)
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

    @staticmethod
    def send_candidate_offer_email(candidate_email, candidate_name, organization_name, offer_letter_body, onboarding_link, organization=None):
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
        if organization:
            return NotificationService.send_automated_email(organization, 'candidate_offer', candidate_email, {'candidate_name': candidate_name, 'organization_name': organization_name, 'offer_letter_body': offer_letter_body, 'onboarding_link': onboarding_link}, subject, message)
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
    def send_password_reset_email(email, first_name, uid, token, organization=None):
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

        if organization:
            return NotificationService.send_automated_email(organization, 'password_reset', email, {'first_name': first_name, 'reset_link': reset_link}, subject, message)
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
