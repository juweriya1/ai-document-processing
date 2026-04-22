from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from src.backend.api.routes_admin import router as admin_router
from src.backend.api.routes_analytics import router as analytics_router
from src.backend.api.routes_auth import router as auth_router
from src.backend.api.routes_pipeline import router as pipeline_router
from src.backend.api.routes_upload import router as upload_router
from src.backend.api.routes_validation import router as validation_router
from src.backend.db.database import engine
from src.backend.db.models import Base

import logging

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="IDP Platform", version="0.1.0")


@app.on_event("startup")
def create_tables():
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        conn.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
            "is_active BOOLEAN NOT NULL DEFAULT true"
        ))
        conn.commit()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router)
app.include_router(upload_router)
app.include_router(validation_router)
app.include_router(pipeline_router)
app.include_router(analytics_router)
app.include_router(admin_router)


@app.get("/health")
def health_check():
    return {"status": "healthy"}
