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
    def is_authenticated(self):
        """
        Ensure inactive/deactivated accounts are strictly treated as unauthenticated.
        This forces the DRF authentication and permission layers to produce 401 Unauthorized
        instead of allowing an inactive user to reach the authorization layer and get 403.
        """
        return super().is_authenticated and self.is_active

    def __str__(self):
        return self.email
