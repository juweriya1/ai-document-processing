from sqlalchemy.orm import Session
from passlib.context import CryptContext

from src.backend.db.models import Document, ExtractedField, User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_document(
    db: Session,
    filename: str,
    original_filename: str,
    file_type: str,
    file_size: int,
    uploaded_by: str | None = None,
) -> Document:
    doc = Document(
        filename=filename,
        original_filename=original_filename,
        file_type=file_type,
        file_size=file_size,
        uploaded_by=uploaded_by,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def get_document(db: Session, document_id: str) -> Document | None:
    return db.query(Document).filter(Document.id == document_id).first()


def list_documents(db: Session, skip: int = 0, limit: int = 100) -> list[Document]:
    return db.query(Document).offset(skip).limit(limit).all()


def store_extracted_fields(
    db: Session, document_id: str, fields: list[dict]
) -> list[ExtractedField]:
    stored = []
    for field_data in fields:
        field = ExtractedField(
            document_id=document_id,
            field_name=field_data["field_name"],
            field_value=field_data.get("field_value"),
            confidence=field_data.get("confidence"),
        )
        db.add(field)
        stored.append(field)
    db.commit()
    for f in stored:
        db.refresh(f)
    return stored


def create_user(
    db: Session,
    email: str,
    password: str,
    name: str,
    role: str = "enterprise_user",
) -> User:
    password_hash = pwd_context.hash(password)
    user = User(
        email=email,
        password_hash=password_hash,
        name=name,
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)
