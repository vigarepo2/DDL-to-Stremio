from os import getenv
from dotenv import load_dotenv
import hashlib

load_dotenv("config.env")

class Settings:
    # Server configuration
    BASE_URL = getenv("BASE_URL", "http://127.0.0.1:8000").rstrip('/')
    PORT = int(getenv("PORT", "8000"))

    # Database connection
    MONGO_URI = getenv("MONGO_URI", "")
    DB_NAME = "ddl_stremio_premium"

    # API Keys
    TMDB_API_KEY = getenv("TMDB_API_KEY", "")

    # Admin Panel Credentials
    ADMIN_USERNAME = getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = getenv("ADMIN_PASSWORD", "admin")
    ADMIN_PASSWORD_HASH = hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()

settings = Settings()
