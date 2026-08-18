from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'status', 'is_staff')
    search_fields = ('email', 'first_name', 'last_name', 'google_subject_id')
    ordering = ('email',)
    list_filter = ('status', 'is_staff', 'is_superuser')
    fieldsets = (
        (None, {'fields': ('email', 'password', 'google_subject_id')}),
        ('Personal info', {'fields': ('first_name', 'last_name')}),
        ('Status', {'fields': ('status',)}),
        ('Permissions', {'fields': ('is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login',)}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password', 'status'),
        }),
    )

admin.site.register(User, CustomUserAdmin)
