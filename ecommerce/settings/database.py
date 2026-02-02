"""
Database configuration
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


from dotenv import load_dotenv

load_dotenv(BASE_DIR / ".env")


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "ecommerce_db"),
        "USER": os.getenv("DB_USER", "ecommerce_user"),
        "PASSWORD": os.getenv("ecommerce", ""),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5432"),
        "CONN_MAX_AGE": 600,
        "OPTIONS": {
            "connect_timeout": 10,
        },
    }
}
