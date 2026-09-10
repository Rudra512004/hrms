"""
Data migration: seed payroll.view_reports into the Permission table.
"""
from django.db import migrations


REPORTING_PERMISSIONS = [
    {
        'name': 'View Payroll Reports',
        'codename': 'payroll.view_reports',
        'resource': 'payroll',
        'action': 'view_reports',
        'description': 'View aggregated payroll reports, reconciliation ledgers, and exceptions.',
    },
]


def seed_permissions(apps, schema_editor):
    Permission = apps.get_model('authorization', 'Permission')
    for perm in REPORTING_PERMISSIONS:
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
        codename__in=[p['codename'] for p in REPORTING_PERMISSIONS]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('payroll', '0004_seed_payslip_permissions'),
        ('authorization', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_permissions, reverse_code=unseed_permissions),
    ]
