"""
Database configuration
"""

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load environment variables
from dotenv import load_dotenv

load_dotenv(BASE_DIR / ".env")

# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "ecommerce_db"),
        "USER": os.getenv("DB_USER", "ecommerce_user"),
        "PASSWORD": os.getenv("ecommerce", ""),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5432"),
        "CONN_MAX_AGE": 600,  # Keep connections alive for 10 minutes
        "OPTIONS": {
            "connect_timeout": 10,
        },
    }
}

# For development, you can keep SQLite as fallback
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'db.sqlite3',
#     }
# }
