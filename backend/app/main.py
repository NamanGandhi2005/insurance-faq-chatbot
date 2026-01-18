# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database.connection import engine, Base
from app.services.startup_processor import run_startup_processing
from app.database.connection import SessionLocal
from app.utils.limiter import limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded 

# --- CHANGE START ---
# Import from the package (app.models) to ensure all classes are registered
from app.models import Product, PDFDocument, AuditLog 
# --- CHANGE END ---

from app.api.routes import chat, products, admin , auth

# Create Tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.APP_NAME)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routes
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(products.router, prefix="/api/products", tags=["Products"]) # <--- Register
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])       # <--- Register
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])


@app.on_event("startup")
def startup_event():
    db = SessionLocal()
    try:
        run_startup_processing(db)
    finally:
        db.close()


@app.get("/")
def health_check():
    return {"status": "healthy"}