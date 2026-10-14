"""
URL patterns for Gmail API OAuth endpoints.

These are registered under the auth namespace in config/urls.py:
    GET  /api/v1/auth/google/authorize/  — Initiate OAuth flow
    GET  /api/v1/auth/google/callback/   — Handle OAuth callback
"""

from django.urls import path
from apps.notifications.gmail_views import GmailAuthorizeView, GmailCallbackView

urlpatterns = [
    path('google/authorize/', GmailAuthorizeView.as_view(), name='gmail-authorize'),
    path('google/callback/', GmailCallbackView.as_view(), name='gmail-callback'),
]
