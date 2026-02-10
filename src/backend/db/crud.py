from sqlalchemy.orm import Session
from passlib.context import CryptContext

from src.backend.db.models import Correction, Document, ExtractedField, LineItem, User

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


def get_extracted_fields(db: Session, document_id: str) -> list[ExtractedField]:
    return (
        db.query(ExtractedField)
        .filter(ExtractedField.document_id == document_id)
        .all()
    )


def get_field_by_id(db: Session, field_id: str) -> ExtractedField | None:
    return db.query(ExtractedField).filter(ExtractedField.id == field_id).first()


def update_field_value(
    db: Session, field_id: str, new_value: str
) -> ExtractedField | None:
    field = get_field_by_id(db, field_id)
    if field is None:
        return None
    field.field_value = new_value
    db.commit()
    db.refresh(field)
    return field


def update_field_validation_status(
    db: Session, field_id: str, status: str, error_message: str | None = None
) -> ExtractedField | None:
    field = get_field_by_id(db, field_id)
    if field is None:
        return None
    field.status = status
    field.error_message = error_message
    db.commit()
    db.refresh(field)
    return field


def create_correction(
    db: Session,
    document_id: str,
    field_id: str,
    original_value: str | None,
    corrected_value: str,
    reviewed_by: str | None = None,
) -> Correction:
    correction = Correction(
        document_id=document_id,
        field_id=field_id,
        original_value=original_value,
        corrected_value=corrected_value,
        reviewed_by=reviewed_by,
    )
    db.add(correction)
    db.commit()
    db.refresh(correction)
    return correction


def get_corrections_by_document(db: Session, document_id: str) -> list[Correction]:
    return (
        db.query(Correction)
        .filter(Correction.document_id == document_id)
        .all()
    )


def update_document_status(db: Session, document_id: str, status: str) -> Document | None:
    doc = get_document(db, document_id)
    if doc is None:
        return None
    doc.status = status
    db.commit()
    db.refresh(doc)
    return doc


def store_line_items(
    db: Session, document_id: str, items: list[dict]
) -> list[LineItem]:
    stored = []
    for item_data in items:
        item = LineItem(
            document_id=document_id,
            description=item_data.get("description"),
            quantity=item_data.get("quantity"),
            unit_price=item_data.get("unit_price"),
            total=item_data.get("total"),
        )
        db.add(item)
        stored.append(item)
    db.commit()
    for li in stored:
        db.refresh(li)
    return stored


def get_line_items(db: Session, document_id: str) -> list[LineItem]:
    return (
        db.query(LineItem)
        .filter(LineItem.document_id == document_id)
        .all()
    )
