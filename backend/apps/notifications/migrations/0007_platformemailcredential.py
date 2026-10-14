"""
Migration for PlatformEmailCredential model.

Stores encrypted Gmail API OAuth2 refresh tokens in PostgreSQL
for persistent, secure platform email delivery.
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('notifications', '0006_phase7_announcement_acknowledgement'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlatformEmailCredential',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(help_text='The Gmail address authorized as the platform sender.', max_length=254)),
                ('encrypted_refresh_token', models.TextField(help_text='Fernet-encrypted OAuth2 refresh token.')),
                ('token_scope', models.CharField(default='https://www.googleapis.com/auth/gmail.send', help_text='OAuth scope granted during authorization.', max_length=255)),
                ('is_active', models.BooleanField(default=True, help_text='Whether this credential is the active platform sender.')),
                ('authorized_at', models.DateTimeField(blank=True, help_text='When the OAuth authorization was completed.', null=True)),
                ('last_used_at', models.DateTimeField(blank=True, help_text='When the credential was last used to send an email.', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('authorized_by', models.ForeignKey(
                    blank=True,
                    help_text='The superuser who completed the OAuth flow.',
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Platform Email Credential',
                'verbose_name_plural': 'Platform Email Credentials',
            },
        ),
    ]
