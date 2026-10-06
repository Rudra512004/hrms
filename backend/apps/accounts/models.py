from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager

class UserStatus(models.TextChoices):
    INVITED = 'invited', 'Invited'
    ACTIVE = 'active', 'Active'
    INACTIVE = 'inactive', 'Inactive'

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        extra_fields.setdefault('status', UserStatus.INVITED)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('status', UserStatus.ACTIVE)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True, db_index=True)
    google_subject_id = models.CharField(max_length=255, unique=True, null=True, blank=True, help_text="Google OAuth unique subject identifier")

    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)

    status = models.CharField(max_length=20, choices=UserStatus.choices, default=UserStatus.INVITED)

    is_staff = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    @property
    def is_active(self):
        return self.status == UserStatus.ACTIVE

    @property
    def employee(self):
        # Compatibility layer: returns the first employee profile.
        # This prevents 500+ references to `user.employee` from crashing immediately
        # after changing the Employee.user relationship to a ForeignKey.
        if not hasattr(self, '_employee_cache'):
            self._employee_cache = self.employee_profiles.first() if hasattr(self, 'employee_profiles') else None
            
        if self._employee_cache is None:
            raise AttributeError("User has no employee profile")
        return self._employee_cache

    def get_full_name(self):
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name if full_name else self.email

    def get_short_name(self):
        return self.first_name if self.first_name else self.email

    def __str__(self):
        return self.email


class TenantOwnerRegistration(models.Model):
    """A verified self-service account that may launch one tenant organization."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='tenant_owner_registration')
    verified_at = models.DateTimeField(null=True, blank=True)
    organization = models.OneToOneField(
        'organization.Organization', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='owner_registration'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def can_launch_organization(self):
        return self.verified_at is not None and self.organization_id is None
