from django.contrib import admin
from .models import AssetCategory, Asset, AssetAssignment


@admin.register(AssetCategory)
class AssetCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'organization', 'is_active', 'created_at')
    list_filter = ('organization', 'is_active')
    search_fields = ('name', 'code')


class AssetAssignmentInline(admin.TabularInline):
    model = AssetAssignment
    extra = 0
    readonly_fields = ('allocated_at', 'returned_at', 'is_active')


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ('asset_tag', 'name', 'category', 'organization', 'branch', 'status', 'created_at')
    list_filter = ('organization', 'status', 'category')
    search_fields = ('asset_tag', 'name', 'serial_number', 'model_number')
    inlines = [AssetAssignmentInline]


@admin.register(AssetAssignment)
class AssetAssignmentAdmin(admin.ModelAdmin):
    list_display = ('asset', 'employee', 'allocated_at', 'returned_at', 'is_active')
    list_filter = ('is_active', 'allocated_at')
    search_fields = ('asset__asset_tag', 'employee__employee_code', 'employee__user__first_name', 'employee__user__last_name')
