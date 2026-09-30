from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('notifications', '0004_email_automation')]

    operations = [
        migrations.DeleteModel(name='EmailDelivery'),
        migrations.DeleteModel(name='EmailAutomationRule'),
        migrations.DeleteModel(name='EmailTemplate'),
        migrations.DeleteModel(name='OrganizationEmailSettings'),
    ]
