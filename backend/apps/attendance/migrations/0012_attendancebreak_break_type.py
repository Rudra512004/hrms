import django.db.models.deletion
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies=[('attendance','0011_breaktype')]
    operations=[migrations.AddField(model_name='attendancebreak',name='break_type',field=models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.SET_NULL,related_name='breaks',to='attendance.breaktype'))]
