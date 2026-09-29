from django.db import migrations

ATTENDANCE_PERMISSIONS = [
    {
        'name': 'View Shift Assignments',
        'codename': 'shift_assignment.view',
        'resource': 'shift_assignment',
        'action': 'view',
        'description': 'View employee shift assignments for the organization.',
    },
    {
        'name': 'Manage Shift Assignments',
        'codename': 'shift_assignment.manage',
        'resource': 'shift_assignment',
        'action': 'manage',
        'description': 'Create, update, and delete employee shift assignments.',
    },
]

def seed_permissions(apps, schema_editor):
    Permission = apps.get_model('authorization', 'Permission')
    for perm in ATTENDANCE_PERMISSIONS:
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
        codename__in=[p['codename'] for p in ATTENDANCE_PERMISSIONS]
    ).delete()

class Migration(migrations.Migration):
    dependencies = [
        ('attendance', '0005_shift_full_day_hours_shift_half_day_hours_and_more'),
        ('authorization', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_permissions, reverse_code=unseed_permissions),
    ]
