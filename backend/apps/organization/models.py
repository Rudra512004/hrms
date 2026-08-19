from django.db import models

class Organization(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
    name = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

import ipaddress
from django.core.exceptions import ValidationError

def validate_network(value):
    try:
        ipaddress.ip_network(value, strict=False)
    except ValueError:
        raise ValidationError("Invalid CIDR network")

class OfficeNetwork(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='office_networks')
    name = models.CharField(max_length=255)
    network = models.CharField(max_length=45, validators=[validate_network], help_text="e.g., 203.0.113.0/24")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('organization', 'network')

    def __str__(self):
        return f"{self.name} ({self.network})"
