from .base import *
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ecommerce.settings")
