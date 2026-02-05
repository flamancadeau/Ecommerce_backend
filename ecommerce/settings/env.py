import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

try:
    import environ

    env = environ.Env()
    environ.Env.read_env(os.path.join(BASE_DIR, ".env"))
except Exception:

    from dotenv import load_dotenv

    load_dotenv(os.path.join(BASE_DIR, ".env"))

    class SimpleEnv:
        def __call__(self, key, default=None):
            return os.getenv(key, default)

        def bool(self, key, default=False):
            val = os.getenv(key)
            if val is None:
                return default
            return str(val).lower() in ("1", "true", "yes", "on")

        def list(self, key, default=None):
            val = os.getenv(key)
            if val is None:
                return default or []
            return [i.strip() for i in val.split(",") if i.strip()]

    env = SimpleEnv()
