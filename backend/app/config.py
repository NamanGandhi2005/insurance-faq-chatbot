# app/config.py
import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # App Config
    APP_NAME: str = "Insurance FAQ Chatbot"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "your-super-secret-key-change-this"
    
    # Database (SQLite)
    SQLITE_DB_FILE: str = os.path.join(os.getcwd(), "../data/database.db")
    
    @property
    def DATABASE_URL(self) -> str:
        # The check_same_thread argument is needed only for SQLite.
        # It's a workaround for how FastAPI handles multithreading.
        return f"sqlite:///{self.SQLITE_DB_FILE}?check_same_thread=False"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    
    # AI Config
    EMBEDDING_MODEL: str = "intfloat/multilingual-e5-base"
    
    # Groq API Settings - Add your GROQ_API_KEY to a .env file
    GROQ_API_KEY: str 
    GROQ_MODEL: str = "llama-3.1-8b-instant"
    ADMIN_REGISTRATION_KEY: str = "admin@123"

    VECTOR_DB_PATH: str = os.path.join(os.getcwd(), "../data/vector_db")
    
    # File Paths
    PDF_UPLOAD_DIR: str = os.path.join(os.getcwd(), "../data/pdfs/uploads")
    PDF_PRELOAD_DIR: str = os.path.join(os.getcwd(), "../data/pdfs/preload")

    class Config:
        env_file = ".env"

settings = Settings()