"""DEPRECATED test module — legacy stack retired 2026-04-24.

Legacy orchestrator-backed route retired; /api/documents/{id}/process is now a
proxy to /api/agentic/{id}/process. See tests/unit/test_routes_agentic.py.
"""
import pytest

pytest.skip(
    "Legacy pipeline module retired; superseded by the agentic pipeline tests.",
    allow_module_level=True,
)

# =============================================================================
# Original content preserved below as comments for reference.
# =============================================================================

# import pytest
# from fastapi.testclient import TestClient
# from sqlalchemy import create_engine
# from sqlalchemy.orm import sessionmaker
#
# from src.backend.auth.jwt_handler import create_access_token
# from src.backend.config import TEST_DATABASE_URL
# from src.backend.db.crud import create_document, update_document_status
# from src.backend.db.database import get_db
# from src.backend.db.models import Base
# from src.backend.main import app
#
#
# @pytest.fixture
# def test_db():
#     engine = create_engine(TEST_DATABASE_URL)
#     Base.metadata.create_all(engine)
#     Session = sessionmaker(bind=engine)
#     session = Session()
#     yield session
#     session.rollback()
#     session.close()
#     Base.metadata.drop_all(engine)
#     engine.dispose()
#
#
# @pytest.fixture
# def client(test_db):
#     def override_get_db():
#         yield test_db
#     app.dependency_overrides[get_db] = override_get_db
#     yield TestClient(app)
#     app.dependency_overrides.clear()
#
#
# @pytest.fixture
# def auth_token():
#     return create_access_token(
#         data={"sub": "user@test.com", "role": "enterprise_user", "user_id": "usr_test01"}
#     )
#
#
# @pytest.fixture
# def test_document(test_db):
#     return create_document(
#         test_db,
#         filename="pipeline_test.pdf",
#         original_filename="pipeline_test.pdf",
#         file_type="application/pdf",
#         file_size=2048,
#     )
#
#
# class TestProcessDocument:
#     def test_process_success(self, client, auth_token, test_document):
#         resp = client.post(
#             f"/api/documents/{test_document.id}/process",
#             headers={"Authorization": f"Bearer {auth_token}"},
#         )
#         assert resp.status_code == 200
#         data = resp.json()
#         assert data["document_id"] == test_document.id
#         assert data["status"] == "review_pending"
#         assert data["fields_extracted"] == 4
#         assert data["line_items_extracted"] == 3
#
#     def test_process_not_found(self, client, auth_token):
#         resp = client.post(
#             "/api/documents/doc_nonexist/process",
#             headers={"Authorization": f"Bearer {auth_token}"},
#         )
#         assert resp.status_code == 400
#
#     def test_process_already_processed(self, client, auth_token, test_document, test_db):
#         update_document_status(test_db, test_document.id, "review_pending")
#         resp = client.post(
#             f"/api/documents/{test_document.id}/process",
#             headers={"Authorization": f"Bearer {auth_token}"},
#         )
#         assert resp.status_code == 400
#
#     def test_process_no_auth(self, client, test_document):
#         resp = client.post(f"/api/documents/{test_document.id}/process")
#         assert resp.status_code == 401
#
#
# class TestGetStatus:
#     def test_get_status_success(self, client, auth_token, test_document):
#         resp = client.get(
#             f"/api/documents/{test_document.id}/status",
#             headers={"Authorization": f"Bearer {auth_token}"},
#         )
#         assert resp.status_code == 200
#         data = resp.json()
#         assert data["document_id"] == test_document.id
#         assert data["status"] == "uploaded"
#
#     def test_get_status_not_found(self, client, auth_token):
#         resp = client.get(
#             "/api/documents/doc_nonexist/status",
#             headers={"Authorization": f"Bearer {auth_token}"},
#         )
#         assert resp.status_code == 404
