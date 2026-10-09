"""
Data migration: seed tax declaration permissions into the Permission table.
"""
from django.db import migrations


TAX_PERMISSIONS = [
    {
        'name': 'Submit Tax Declarations',
        'codename': 'payroll.tax_declare',
        'resource': 'payroll',
        'action': 'tax_declare',
        'description': 'Submit, update, and upload investment declarations and proofs.',
    },
    {
        'name': 'View Tax Declarations',
        'codename': 'payroll.tax_view',
        'resource': 'payroll',
        'action': 'tax_view',
        'description': 'View organization-wide employee tax declarations and investment summaries.',
    },
    {
        'name': 'Review and Verify Tax Declarations',
        'codename': 'payroll.tax_review',
        'resource': 'payroll',
        'action': 'tax_review',
        'description': 'Review, verify, and reject tax declarations and investment proofs.',
    },
]


def seed_permissions(apps, schema_editor):
    Permission = apps.get_model('authorization', 'Permission')
    for perm in TAX_PERMISSIONS:
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
        codename__in=[p['codename'] for p in TAX_PERMISSIONS]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('payroll', '0014_investmentdeclaration_financialyear_investmentproof_and_more'),
        ('authorization', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_permissions, reverse_code=unseed_permissions),
    ]
