from .env import env

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME", default="ecommerce"),
        "USER": env("DB_USER", default="ecommerce_user"),
        "PASSWORD": env("DB_PASSWORD", default="ecommerce_pass"),
        "HOST": env("DB_HOST", default="localhost"),
        "PORT": env("DB_PORT", default="5432"),
    }
}
