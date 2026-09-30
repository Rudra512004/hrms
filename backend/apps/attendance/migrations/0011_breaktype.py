import django.db.models.deletion
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies=[('organization','0011_workingcalendarrule'),('attendance','0010_attendance_is_late')]
    operations=[migrations.CreateModel(name='BreakType',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('name',models.CharField(max_length=100)),('max_duration_minutes',models.PositiveIntegerField(blank=True,null=True)),('is_active',models.BooleanField(default=True)),('created_at',models.DateTimeField(auto_now_add=True)),('updated_at',models.DateTimeField(auto_now=True)),('organization',models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,related_name='break_types',to='organization.organization'))],options={'ordering':['name'],'unique_together':{('organization','name')}})]
