import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "smartreco-dev-secret-key-987654321")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'smartreco.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # NVIDIA NIM LLM Configuration (Llama 3.1 70B & 8B Instruct)
    NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "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")
    NVIDIA_BASE_URL = os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
    NVIDIA_MODEL = os.environ.get("NVIDIA_MODEL", "meta/llama-3.1-70b-instruct")

    # ChromaDB Vector Store directory
    CHROMA_PERSIST_DIR = str(BASE_DIR / "chroma_db")
    
    # Recommendation Caching & Trigger thresholds
    RECOMMENDATION_MIN_EVENTS_TRIGGER = 2
    RECOMMENDATION_TTL_SECONDS = 300  # 5 minutes cache TTL
    
    # Admin Credentials
    ADMIN_EMAIL = "admin@smartreco.com"
    ADMIN_PASSWORD = "admin"
