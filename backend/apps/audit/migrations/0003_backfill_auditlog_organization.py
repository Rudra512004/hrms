from django.db import migrations


def backfill_auditlog_organization(apps, schema_editor):
    AuditLog = apps.get_model('audit', 'AuditLog')
    Employee = apps.get_model('employees', 'Employee')
    Asset = apps.get_model('assets', 'Asset')

    # Pre-map user_id to organization_id via Employee
    user_org_map = dict(
        Employee.objects.filter(organization__isnull=False).values_list('user_id', 'organization_id')
    )
    # Pre-map employee id to organization_id
    emp_org_map = dict(
        Employee.objects.filter(organization__isnull=False).values_list('id', 'organization_id')
    )
    # Pre-map asset id to organization_id
    asset_org_map = dict(
        Asset.objects.filter(organization__isnull=False).values_list('id', 'organization_id')
    )

    updates = []
    # Only evaluate logs where organization is not yet set
    for log in AuditLog.objects.filter(organization__isnull=True).iterator():
        target_org_id = None

        # 1. If actor is an authenticated employee with an organization
        if log.actor_id and log.actor_id in user_org_map:
            target_org_id = user_org_map[log.actor_id]
        # 2. If target is an employee
        elif log.target_type == 'employee' and log.target_id:
            try:
                emp_id = int(log.target_id)
                target_org_id = emp_org_map.get(emp_id)
            except (ValueError, TypeError):
                pass
        # 3. If target is an asset
        elif log.target_type == 'asset' and log.target_id:
            try:
                asset_id = int(log.target_id)
                target_org_id = asset_org_map.get(asset_id)
            except (ValueError, TypeError):
                pass

        # If a genuine, verified organization was found, update it.
        # Otherwise, preserve historical truth: leave as NULL (system/anonymous event).
        if target_org_id:
            log.organization_id = target_org_id
            updates.append(log)

    if updates:
        AuditLog.objects.bulk_update(updates, ['organization_id'], batch_size=500)


def reverse_backfill(apps, schema_editor):
    # Reversible: set all organization_id back to null
    AuditLog = apps.get_model('audit', 'AuditLog')
    AuditLog.objects.all().update(organization=None)


class Migration(migrations.Migration):

    dependencies = [
        ('audit', '0002_auditlog_organization'),
        ('employees', '0003_employee_personal_email'),
        ('assets', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(backfill_auditlog_organization, reverse_backfill),
    ]
