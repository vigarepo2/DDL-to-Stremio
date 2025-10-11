from os import getenv
from dotenv import load_dotenv
import hashlib

# Load environment variables from a file named 'config.env'
load_dotenv("config.env")

class Settings:
    # Server configuration
    BASE_URL = getenv("BASE_URL", "http://127.0.0.1:8000").rstrip('/')
    PORT = int(getenv("PORT", "8000"))

    # Database connection string
    MONGO_URI = getenv("MONGO_URI", "")

    # The Movie Database (TMDb) API Key
    TMDB_API_KEY = getenv("TMDB_API_KEY", "")

    # Admin Panel credentials
    ADMIN_USERNAME = getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = getenv("ADMIN_PASSWORD", "admin")
    ADMIN_PASSWORD_HASH = hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()

# Create a single instance of the settings to be used across the app
settings = Settings()
