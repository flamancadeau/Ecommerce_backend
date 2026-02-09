import os
import sys
import logging
import django
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("infrastructure.setup")


def verify_environment():
    """Configures Django and verifies DB connectivity info."""
    sys.path.insert(0, os.getcwd())
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ecommerce.settings")

    try:
        django.setup()
        db_config = settings.DATABASES.get("default", {})

        engine = db_config.get("ENGINE", "NOT_SET")
        host = db_config.get("HOST", "localhost")
        user = db_config.get("USER", "NOT_SET")

        logger.info("Django environment initialized successfully.")
        logger.info(
            "Database Configuration: Engine=%s, Host=%s, User=%s", engine, host, user
        )

    except ImproperlyConfigured as e:
        logger.error("Django configuration error: %s", e)
    except Exception:
        logger.exception("An unexpected error occurred during setup.")


if __name__ == "__main__":
    verify_environment()
