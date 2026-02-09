from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.backend.api.routes_auth import router as auth_router
from src.backend.api.routes_upload import router as upload_router

app = FastAPI(title="IDP Platform", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router)
app.include_router(upload_router)


@app.get("/health")
def health_check():
    return {"status": "healthy"}
