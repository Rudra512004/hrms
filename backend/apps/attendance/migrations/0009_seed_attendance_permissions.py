from django.db import migrations

ATTENDANCE_PERMISSIONS = [
    {
        'name': 'View All Attendance',
        'codename': 'attendance.view_all',
        'resource': 'attendance',
        'action': 'view_all',
        'description': 'View organization, branch, or team attendance records.',
    },
    {
        'name': 'View Holidays',
        'codename': 'holiday.view',
        'resource': 'holiday',
        'action': 'view',
        'description': 'View holidays for branches.',
    },
    {
        'name': 'Manage Holidays',
        'codename': 'holiday.manage',
        'resource': 'holiday',
        'action': 'manage',
        'description': 'Create, update, and delete holidays for branches.',
    },
    {
        'name': 'View Shifts',
        'codename': 'shift.view',
        'resource': 'shift',
        'action': 'view',
        'description': 'View shifts for branches.',
    },
    {
        'name': 'Manage Shifts',
        'codename': 'shift.manage',
        'resource': 'shift',
        'action': 'manage',
        'description': 'Create, update, and delete shifts for branches.',
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
        ('attendance', '0008_alter_holiday_unique_together_and_more'),
        ('authorization', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_permissions, reverse_code=unseed_permissions),
    ]
