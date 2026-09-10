"""
Data migration: seed payslip permissions into the Permission table.
Follows the same pattern used by authorization and payroll apps.
"""
from django.db import migrations


PAYSLIP_PERMISSIONS = [
    {
        'name': 'View Payslips',
        'codename': 'payslip.view',
        'resource': 'payslip',
        'action': 'view',
        'description': 'View organization-wide employee payslips.',
    },
    {
        'name': 'Download Payslips',
        'codename': 'payslip.download',
        'resource': 'payslip',
        'action': 'download',
        'description': 'Download or export employee payslips.',
    },
]


def seed_permissions(apps, schema_editor):
    Permission = apps.get_model('authorization', 'Permission')
    for perm in PAYSLIP_PERMISSIONS:
        Permission.objects.get_or_create(
            codename=perm['codename'],
            defaults={
                'name': perm['name'],
                'resource': perm['resource'],
                'action': perm['action'],
                'description': perm['description'],
                'is_active': True,
            },
        )


def unseed_permissions(apps, schema_editor):
    Permission = apps.get_model('authorization', 'Permission')
    Permission.objects.filter(
        codename__in=[p['codename'] for p in PAYSLIP_PERMISSIONS]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('payroll', '0003_payslip'),
        ('authorization', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_permissions, reverse_code=unseed_permissions),
    ]
