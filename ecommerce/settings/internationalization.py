from .env import env

LANGUAGE_CODE = "en-us"
TIME_ZONE = env("TIME_ZONE", default="Africa/Kigali")
USE_I18N = True
USE_TZ = True
