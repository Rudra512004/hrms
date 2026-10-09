"""
Data migration: seed tax rule configuration and calculation permissions.
"""
from django.db import migrations


ADDITIONAL_TAX_PERMISSIONS = [
    {
        'name': 'Configure Tax Rules and Slabs',
        'codename': 'payroll.tax_configure',
        'resource': 'payroll',
        'action': 'tax_configure',
        'description': 'Configure versioned tax rules, slabs, deductions, and regime applicability.',
    },
    {
        'name': 'Calculate and Preview Tax TDS',
        'codename': 'payroll.tax_calculate',
        'resource': 'payroll',
        'action': 'tax_calculate',
        'description': 'Perform and preview annual tax projection and monthly TDS calculations.',
    },
]


def seed_permissions(apps, schema_editor):
    Permission = apps.get_model('authorization', 'Permission')
    for perm in ADDITIONAL_TAX_PERMISSIONS:
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
        codename__in=[p['codename'] for p in ADDITIONAL_TAX_PERMISSIONS]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('payroll', '0016_payrollrecord_tax_calculation_snapshot_and_more'),
        ('authorization', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_permissions, unseed_permissions),
    ]
