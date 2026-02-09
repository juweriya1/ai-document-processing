import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost:5433/idp_platform")
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql://localhost:5433/idp_platform_test")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-not-for-production")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
ALLOWED_FILE_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".doc", ".docx"}
