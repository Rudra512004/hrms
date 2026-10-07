import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from apps.data_import.registry import TEMPLATE_REGISTRY

for key, t in TEMPLATE_REGISTRY.items():
    print(f'\n--- {key} ---')
    print(f'Count: {len(t["headers"])}')
    print(','.join(t['headers']))
