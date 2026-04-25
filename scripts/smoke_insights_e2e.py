"""E2E smoke: hit every endpoint InsightsPage.js consumes."""
import sys
sys.path.insert(0, '.')

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.backend.auth.jwt_handler import create_access_token
from src.backend.config import TEST_DATABASE_URL
from src.backend.db.crud import create_user
from src.backend.db.database import get_db
from src.backend.db.models import Base
from src.backend.main import app

engine = create_engine(TEST_DATABASE_URL)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

def override_get_db():
    yield session

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

reviewer = create_user(session, email="r@e2e.com", password="x", name="R", role="reviewer")
token = create_access_token(data={"sub": reviewer.email, "role": reviewer.role, "user_id": reviewer.id})
auth = {"Authorization": f"Bearer {token}"}

endpoints = [
    "/api/analytics/dashboard",
    "/api/analytics/spend/by-vendor",
    "/api/analytics/spend/by-month?months=12",
    "/api/analytics/trust/overview",
    "/api/analytics/trust/flagged",
    "/api/analytics/vendor-risk",
    "/api/analytics/anomalies",
    "/api/analytics/predictions",
    "/api/analytics/widgets/preferences",
    "/api/analytics/widgets/catalog",
    "/api/bi/invoices.json",
]

fails = 0
for ep in endpoints:
    r = client.get(ep, headers=auth)
    ok = r.status_code == 200
    fails += not ok
    body_kind = type(r.json()).__name__ if ok else r.text[:120]
    print(f"{'OK  ' if ok else 'FAIL'} {r.status_code} {ep}  -> {body_kind}")

session.close()
Base.metadata.drop_all(engine)
sys.exit(1 if fails else 0)
