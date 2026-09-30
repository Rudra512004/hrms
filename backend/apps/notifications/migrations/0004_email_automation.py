import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('notifications', '0003_announcement')]

    operations = [
        migrations.CreateModel(name='OrganizationEmailSettings', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('sender_name', models.CharField(blank=True, max_length=120)),
            ('from_email', models.EmailField(blank=True, max_length=254)),
            ('reply_to_email', models.EmailField(blank=True, max_length=254)),
            ('automation_enabled', models.BooleanField(default=False)),
            ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)),
            ('organization', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='email_settings', to='organization.organization')),
        ]),
        migrations.CreateModel(name='EmailTemplate', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('event_type', models.CharField(choices=[('employee_onboarding','Employee onboarding'),('candidate_offer','Candidate offer'),('password_reset','Password reset'),('announcement_published','Announcement published'),('attendance_alert','Attendance alert'),('scheduled_report','Scheduled report')], max_length=40)),
            ('name', models.CharField(max_length=120)), ('subject', models.CharField(max_length=255)), ('body', models.TextField(max_length=10000)), ('is_active', models.BooleanField(default=True)), ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)),
            ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='email_templates', to='organization.organization')),
        ], options={'unique_together': {('organization','event_type','name')}}),
        migrations.CreateModel(name='EmailAutomationRule', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('name', models.CharField(max_length=120)), ('event_type', models.CharField(choices=[('employee_onboarding','Employee onboarding'),('candidate_offer','Candidate offer'),('password_reset','Password reset'),('announcement_published','Announcement published'),('attendance_alert','Attendance alert'),('scheduled_report','Scheduled report')], max_length=40)),
            ('recipient_mode', models.CharField(choices=[('event_recipient','Event recipient'),('organization_admins','Organization administrators')], default='event_recipient', max_length=30)), ('is_active', models.BooleanField(default=True)), ('created_at', models.DateTimeField(auto_now_add=True)), ('updated_at', models.DateTimeField(auto_now=True)),
            ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='email_automation_rules', to='organization.organization')),
        ], options={'unique_together': {('organization','event_type','name')}}),
        migrations.CreateModel(name='EmailDelivery', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')), ('event_type', models.CharField(max_length=40)), ('recipient_email', models.EmailField(max_length=254)), ('subject', models.CharField(max_length=255)), ('status', models.CharField(choices=[('sent','Sent'),('failed','Failed'),('suppressed','Suppressed')], max_length=16)), ('error_message', models.TextField(blank=True)), ('created_at', models.DateTimeField(auto_now_add=True)),
            ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='email_deliveries', to='organization.organization')),
        ], options={'ordering':['-created_at','-id']}),
        migrations.AddIndex(model_name='emaildelivery', index=models.Index(fields=['organization','event_type','-created_at'], name='email_delivery_org_event_idx')),
    ]
