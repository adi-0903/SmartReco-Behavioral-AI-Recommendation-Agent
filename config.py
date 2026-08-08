import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'smartreco.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Mesh API Configuration (Mandatory Hackathon Gateway)
    MESH_API_KEY = os.environ.get("MESH_API_KEY", "")
    MESH_BASE_URL = os.environ.get("MESH_BASE_URL", "https://api.meshapi.ai/v1")
    MESH_MODEL = os.environ.get("MESH_MODEL", "openai/gpt-4o")

    # NVIDIA NIM LLM Configuration (High-Performance Endpoint Option)
    NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY")
    NVIDIA_BASE_URL = os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
    NVIDIA_MODEL = os.environ.get("NVIDIA_MODEL", "meta/llama-3.1-8b-instruct")

    # Email Configuration
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER")

    # ChromaDB Vector Store directory
    CHROMA_PERSIST_DIR = str(BASE_DIR / "chroma_db")

    # Recommendation Caching & Trigger thresholds
    RECOMMENDATION_MIN_EVENTS_TRIGGER = 2
    RECOMMENDATION_TTL_SECONDS = 300  # 5 minutes cache TTL

    # Admin Credentials (set via environment variables)
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@smartreco.com")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

    # Redis Configuration
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    # Rate Limiting - use in-memory fallback if Redis unavailable
    RATELIMIT_STORAGE_URL = os.environ.get("RATELIMIT_STORAGE_URL", "memory://")
    RATELIMIT_DEFAULT = os.environ.get("RATELIMIT_DEFAULT", "200 per minute")

    # Flask Environment
    FLASK_ENV = os.environ.get("FLASK_ENV", "development")
    DEBUG = os.environ.get("DEBUG", "false").lower() == "true"
