from os import getenv
from dotenv import load_dotenv
import hashlib

load_dotenv("config.env")

class Settings:
    # Server
    BASE_URL = getenv("BASE_URL", "http://127.0.0.1:8000").rstrip('/')
    PORT = int(getenv("PORT", "8000"))

    # Database
    MONGO_URI = getenv("MONGO_URI", "")

    # API
    TMDB_API_KEY = getenv("TMDB_API_KEY", "")

    # Admin Panel
    ADMIN_USERNAME = getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = getenv("ADMIN_PASSWORD", "admin")
    # A hashed version for secure comparison
    ADMIN_PASSWORD_HASH = hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()

# Create an instance of the settings
settings = Settings()
