from .env import env
from .internationalization import TIME_ZONE

CELERY_BROKER_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

CELERY_BEAT_SCHEDULE = {
    "expire-reservations-every-minute": {
        "task": "apps.orders.tasks.expire_old_reservations",
        "schedule": 60.0,
    },
    "update-product-cache-every-30-minutes": {
        "task": "apps.catalog.tasks.update_product_cache",
        "schedule": 1800.0,
    },
    "process-inbound-receipts-every-hour": {
        "task": "apps.inventory.tasks.process_inbound_receipts",
        "schedule": 3600.0,
    },
    "update-stock-cache-every-10-minutes": {
        "task": "apps.inventory.tasks.update_stock_levels_cache",
        "schedule": 600.0,
    },
    "check-campaign-activation-every-minute": {
        "task": "apps.promotions.tasks.check_campaign_activations",
        "schedule": 60.0,
    },
}

SAFE_DELETE_INTERPRET_UNDELETED_OBJECTS_AS_CREATED = True
