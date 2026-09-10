"""
Data migration: seed payroll permissions into the Permission table.
Follows the same pattern used by authorization app.
"""
from django.db import migrations


PAYROLL_PERMISSIONS = [
    {
        'name': 'View Payroll',
        'codename': 'payroll.view',
        'resource': 'payroll',
        'action': 'view',
        'description': 'View payroll periods and records for the organization.',
    },
    {
        'name': 'Generate Payroll',
        'codename': 'payroll.generate',
        'resource': 'payroll',
        'action': 'generate',
        'description': 'Create payroll periods and trigger payroll generation.',
    },
    {
        'name': 'Approve Payroll',
        'codename': 'payroll.approve',
        'resource': 'payroll',
        'action': 'approve',
        'description': 'Approve a generated payroll period, locking records.',
    },
    {
        'name': 'View Sensitive Payroll Data',
        'codename': 'payroll.view_sensitive',
        'resource': 'payroll',
        'action': 'view_sensitive',
        'description': 'View gross/net salary amounts in payroll records.',
    },
    {
        'name': 'Manage Compensation',
        'codename': 'payroll.manage_compensation',
        'resource': 'payroll',
        'action': 'manage_compensation',
        'description': 'Create and update employee salary (CompensationHistory).',
    },
]


def seed_permissions(apps, schema_editor):
    Permission = apps.get_model('authorization', 'Permission')
    for perm in PAYROLL_PERMISSIONS:
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
        codename__in=[p['codename'] for p in PAYROLL_PERMISSIONS]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('payroll', '0001_initial'),
        ('authorization', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_permissions, reverse_code=unseed_permissions),
    ]
