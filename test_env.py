import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

print("Environment variables:")
print(f"  DB_NAME: {os.getenv('DB_NAME')}")
print(f"  DB_USER: {os.getenv('DB_USER')}")
print(
    f"  DB_PASSWORD: {'*' * len(os.getenv('DB_PASSWORD', '')) if os.getenv('DB_PASSWORD') else '(empty)'}"
)
print(f"  DB_HOST: {os.getenv('DB_HOST')}")
print(f"  DB_PORT: {os.getenv('DB_PORT')}")
