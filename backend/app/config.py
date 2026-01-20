# app/config.py
import os
from pydantic_settings import BaseSettings

# Get the project root directory (insurance-faq-chatbot)
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class Settings(BaseSettings):
    # App Config
    APP_NAME: str = "Insurance FAQ Chatbot"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "your-super-secret-key-change-this"
    
    # Database (PostgreSQL)
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "root123"
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: str = "5432"
    POSTGRES_DB: str = "insurance_bot"
    
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    
    # AI Config
    EMBEDDING_MODEL: str = "intfloat/multilingual-e5-base"

    # Groq API Config (fast cloud inference)
    GROQ_API_KEY: str = ""  # Set via environment variable or .env file
    GROQ_MODEL: str = "llama-3.1-8b-instant"  # Fast model with good quality

    # Legacy Ollama Config (kept for reference)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:3b"
    VECTOR_DB_PATH: str = os.path.join(_BASE_DIR, "data/vector_db")

    # File Paths
    PDF_UPLOAD_DIR: str = os.path.join(_BASE_DIR, "data/pdfs/uploads")
    PDF_PRELOAD_DIR: str = os.path.join(_BASE_DIR, "data/pdfs/preload")

    class Config:
        env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")

settings = Settings()