import django.db.models.deletion
from django.db import migrations,models
class Migration(migrations.Migration):
 dependencies=[('organization','0011_workingcalendarrule'),('attendance','0012_attendancebreak_break_type')]
 operations=[migrations.CreateModel(name='TimesheetPolicy',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('cadence',models.CharField(choices=[('daily','Daily'),('weekly','Weekly')],default='weekly',max_length=10)),('requires_manager_approval',models.BooleanField(default=True)),('lock_on_submit',models.BooleanField(default=True)),('manager_can_reopen',models.BooleanField(default=True)),('updated_at',models.DateTimeField(auto_now=True)),('organization',models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,related_name='timesheet_policy',to='organization.organization'))])]
