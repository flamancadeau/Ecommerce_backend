import os
import sys

sys.path.insert(0, os.getcwd())

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ecommerce.settings")

import django

django.setup()

from django.conf import settings

print("Database settings:")
print(f"  ENGINE: {settings.DATABASES['default']['ENGINE']}")
print(f"  NAME: {settings.DATABASES['default']['NAME']}")
print(f"  USER: {settings.DATABASES['default']['USER']}")
print(f"  HOST: {settings.DATABASES['default']['HOST']}")
print(f"  PORT: {settings.DATABASES['default']['PORT']}")
print(
    f"  PASSWORD: {'*' * len(settings.DATABASES['default']['PASSWORD']) if settings.DATABASES['default']['PASSWORD'] else '(empty)'}"
)
