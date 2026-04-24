from sqlalchemy.orm import Session, joinedload
from passlib.context import CryptContext

from sqlalchemy import func

from src.backend.db.models import (
    AnalyticsSummary,
    Batch,
    Correction,
    Document,
    ExtractedField,
    LineItem,
    SupplierMetric,
    User,
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_document(
    db: Session,
    filename: str,
    original_filename: str,
    file_type: str,
    file_size: int,
    uploaded_by: str | None = None,
    batch_id: str | None = None,
) -> Document:
    doc = Document(
        filename=filename,
        original_filename=original_filename,
        file_type=file_type,
        file_size=file_size,
        uploaded_by=uploaded_by,
        batch_id=batch_id,
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


def list_all_users(db: Session) -> list[User]:
    return db.query(User).all()


def get_user_by_id(db: Session, user_id: str) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def update_user(
    db: Session,
    user_id: str,
    name: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
) -> User | None:
    user = get_user_by_id(db, user_id)
    if user is None:
        return None
    if name is not None:
        user.name = name
    if role is not None:
        user.role = role
    if is_active is not None:
        user.is_active = is_active
    db.commit()
    db.refresh(user)
    return user


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


def get_spend_by_vendor(db: Session) -> list[dict]:
    docs = db.query(Document).all()
    vendor_data: dict[str, dict] = {}
    for doc in docs:
        fields = get_extracted_fields(db, doc.id)
        vendor_field = next(
            (f for f in fields if f.field_name == "vendor_name"), None
        )
        amount_field = next(
            (f for f in fields if f.field_name == "total_amount"), None
        )
        if not vendor_field or not vendor_field.field_value:
            continue
        vendor = vendor_field.field_value
        amount = 0.0
        if amount_field and amount_field.field_value:
            try:
                amount = float(amount_field.field_value)
            except (ValueError, TypeError):
                pass
        if vendor not in vendor_data:
            vendor_data[vendor] = {"total_spend": 0.0, "document_count": 0}
        vendor_data[vendor]["total_spend"] += amount
        vendor_data[vendor]["document_count"] += 1
    return [
        {
            "vendor_name": vendor,
            "total_spend": data["total_spend"],
            "document_count": data["document_count"],
        }
        for vendor, data in vendor_data.items()
    ]


def get_spend_by_month(db: Session) -> list[dict]:
    rows = (
        db.query(Document)
        .filter(Document.status.in_(["approved", "review_pending", "rejected"]))
        .all()
    )
    monthly: dict[str, float] = {}
    for doc in rows:
        month_key = doc.uploaded_at.strftime("%Y-%m") if doc.uploaded_at else "unknown"
        amount_field = (
            db.query(ExtractedField)
            .filter(
                ExtractedField.document_id == doc.id,
                ExtractedField.field_name == "total_amount",
            )
            .first()
        )
        amount = 0.0
        if amount_field and amount_field.field_value:
            try:
                amount = float(amount_field.field_value)
            except (ValueError, TypeError):
                pass
        monthly[month_key] = monthly.get(month_key, 0.0) + amount
    return [
        {"month": k, "total_spend": v}
        for k, v in sorted(monthly.items())
    ]


def get_all_supplier_metrics(db: Session) -> list[SupplierMetric]:
    return db.query(SupplierMetric).all()


def upsert_supplier_metric(
    db: Session,
    supplier_name: str,
    total_documents: int,
    avg_confidence: float | None = None,
    risk_score: float | None = None,
) -> SupplierMetric:
    existing = (
        db.query(SupplierMetric)
        .filter(SupplierMetric.supplier_name == supplier_name)
        .first()
    )
    if existing:
        existing.total_documents = total_documents
        existing.avg_confidence = avg_confidence
        existing.risk_score = risk_score
    else:
        existing = SupplierMetric(
            supplier_name=supplier_name,
            total_documents=total_documents,
            avg_confidence=avg_confidence,
            risk_score=risk_score,
        )
        db.add(existing)
    db.commit()
    db.refresh(existing)
    return existing


def upsert_analytics_summary(
    db: Session,
    metric_name: str,
    metric_value: float,
    period: str | None = None,
) -> AnalyticsSummary:
    existing = (
        db.query(AnalyticsSummary)
        .filter(
            AnalyticsSummary.metric_name == metric_name,
            AnalyticsSummary.period == period,
        )
        .first()
    )
    if existing:
        existing.metric_value = metric_value
    else:
        existing = AnalyticsSummary(
            metric_name=metric_name,
            metric_value=metric_value,
            period=period,
        )
        db.add(existing)
    db.commit()
    db.refresh(existing)
    return existing


def get_analytics_summaries(
    db: Session, metric_name: str | None = None
) -> list[AnalyticsSummary]:
    query = db.query(AnalyticsSummary)
    if metric_name:
        query = query.filter(AnalyticsSummary.metric_name == metric_name)
    return query.all()


def get_documents_with_confidence_stats(db: Session) -> list[dict]:
    docs = db.query(Document).all()
    results = []
    for doc in docs:
        fields = get_extracted_fields(db, doc.id)
        confidences = [f.confidence for f in fields if f.confidence is not None]
        avg_conf = sum(confidences) / len(confidences) if confidences else None
        total_field = next(
            (f for f in fields if f.field_name == "total_amount"), None
        )
        total_amount = None
        if total_field and total_field.field_value:
            try:
                total_amount = float(total_field.field_value)
            except (ValueError, TypeError):
                pass
        corrections = get_corrections_by_document(db, doc.id)
        results.append({
            "document_id": doc.id,
            "filename": doc.original_filename,
            "status": doc.status,
            "avg_confidence": avg_conf,
            "total_amount": total_amount,
            "correction_count": len(corrections),
            "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
        })
    return results


def get_processing_stats(db: Session) -> dict:
    rows = (
        db.query(Document.status, func.count(Document.id))
        .group_by(Document.status)
        .all()
    )
    return {status: count for status, count in rows}


# --- Batch upload CRUD ------------------------------------------------------

def create_batch(
    db: Session,
    created_by: str | None,
    total_documents: int,
    status: str = "processing",
) -> Batch:
    batch = Batch(
        created_by=created_by,
        total_documents=total_documents,
        status=status,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


def get_batch(db: Session, batch_id: str) -> Batch | None:
    return db.query(Batch).filter(Batch.id == batch_id).first()


def get_batch_with_documents(db: Session, batch_id: str) -> Batch | None:
    """Eager-load documents in one query to avoid N+1 on status polls."""
    return (
        db.query(Batch)
        .options(joinedload(Batch.documents))
        .filter(Batch.id == batch_id)
        .first()
    )


def list_batches_for_user(
    db: Session, user_id: str | None, limit: int = 5, include_all: bool = False
) -> list[Batch]:
    query = db.query(Batch)
    if not include_all and user_id is not None:
        query = query.filter(Batch.created_by == user_id)
    return query.order_by(Batch.created_at.desc()).limit(limit).all()


def update_batch_status(db: Session, batch_id: str, status: str) -> Batch | None:
    batch = get_batch(db, batch_id)
    if batch is None:
        return None
    batch.status = status
    db.commit()
    db.refresh(batch)
    return batch
