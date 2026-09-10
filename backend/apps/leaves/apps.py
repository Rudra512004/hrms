from django.apps import AppConfig

class LeavesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.leaves'

    def ready(self):
        import apps.leaves.signals
