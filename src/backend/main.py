from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.backend.api.routes_analytics import router as analytics_router
from src.backend.api.routes_auth import router as auth_router
from src.backend.api.routes_pipeline import router as pipeline_router
from src.backend.api.routes_upload import router as upload_router
from src.backend.api.routes_validation import router as validation_router
from src.backend.db.database import engine
from src.backend.db.models import Base

app = FastAPI(title="IDP Platform", version="0.1.0")


@app.on_event("startup")
def create_tables():
    Base.metadata.create_all(bind=engine)

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


@app.get("/health")
def health_check():
    return {"status": "healthy"}
